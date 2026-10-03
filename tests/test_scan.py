"""Signature scanning with the real binwalk v3 executable."""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import binwalk
from tests.helpers import FIXTURES, NESTED_TEXT

if TYPE_CHECKING:
    from binwalk._v3_backend import BinwalkV3Backend

ZIP_DESCRIPTION = "ZIP archive, version: 2.0, file count: 1, total size: 126 bytes"


def _offsets(path: Path, **kwargs: object) -> list[int]:
    return [result.offset for result in binwalk.scan(str(path), **kwargs)[0]]


@pytest.mark.usefixtures("backend")
@pytest.mark.parametrize(
    ("name", "offsets"),
    [
        ("simple.zip", [0]),
        ("multi_signatures.bin", [0, 638, 1276]),
        ("embedded_256.bin", [256]),
        ("embedded_512.bin", [512]),
        ("embedded_1024.bin", [1024]),
        ("embedded_4096.bin", [4096]),
        ("sig_at_end.bin", [5000]),
        ("empty.bin", []),
        ("zeros_1kb.bin", []),
        ("truncated.zip", []),
    ],
)
def test_signature_offsets(name: str, offsets: list[int]) -> None:
    modules = binwalk.scan(str(FIXTURES / name))
    assert len(modules) == 1
    assert modules[0].name == "Signature"
    assert modules[0].errors == []
    assert [result.offset for result in modules[0]] == offsets


@pytest.mark.usefixtures("backend")
def test_result_fields_come_from_binwalk() -> None:
    (result,) = binwalk.scan(str(FIXTURES / "simple.zip"))[0].results
    assert result.description == ZIP_DESCRIPTION
    assert result.size == 126
    assert result.name == "zip"
    assert result.module == "zip"
    assert result.confidence is not None
    assert result.confidence > 0
    assert result.id
    assert result.depth == 0
    assert result.extraction is None


@pytest.mark.usefixtures("backend")
@pytest.mark.parametrize("name", ["test dir with spaces/test file.zip", "测试目录/test文件.zip"])
def test_paths_with_spaces_and_unicode(name: str) -> None:
    path = str(FIXTURES / name)
    (result,) = binwalk.scan(path)[0].results
    assert result.offset == 0
    assert result.file == path


@pytest.mark.usefixtures("backend")
def test_missing_file_is_reported_not_raised(tmp_path: Path) -> None:
    missing = str(tmp_path / "absent.bin")
    modules = binwalk.scan(missing, str(FIXTURES / "simple.zip"))
    assert modules[0].errors == [f"File not found: {missing}"]
    assert modules[0].results == []
    assert [result.offset for result in modules[1]] == [0]


@pytest.mark.usefixtures("backend")
def test_description_regex_filters_match_v2_semantics() -> None:
    path = FIXTURES / "multi_signatures.bin"
    assert _offsets(path, include="zip archive") == [0, 638, 1276]
    assert _offsets(path, include="ZIP ARCHIVE") == []
    assert _offsets(path, include=["gzip", "zip"]) == [0, 638, 1276]
    assert _offsets(path, include="gzip") == []
    assert _offsets(path, exclude="zip") == []
    assert _offsets(path, exclude="gzip") == [0, 638, 1276]
    assert _offsets(path, include="zip", exclude="version: 2") == []


@pytest.mark.usefixtures("backend")
def test_v3_signature_name_filters() -> None:
    path = FIXTURES / "multi_signatures.bin"
    assert _offsets(path, signatures=["zip"]) == [0, 638, 1276]
    assert _offsets(path, signatures="gzip,png") == []
    assert _offsets(path, exclude_signatures=["zip"]) == []


@pytest.mark.usefixtures("backend")
def test_threads_and_search_all_are_passed_through() -> None:
    path = FIXTURES / "multi_signatures.bin"
    assert _offsets(path, threads=1) == [0, 638, 1276]
    assert _offsets(path, search_all=True)[:3] == [0, 638, 1276]
    with pytest.raises(binwalk.ModuleException, match="threads must be at least 1"):
        binwalk.scan(str(path), threads=0)


def test_scan_bytes_uses_given_name(backend: BinwalkV3Backend) -> None:
    data = (FIXTURES / "embedded_512.bin").read_bytes()
    (module,) = binwalk.scan_bytes(data, name="memory.bin")
    assert [(result.offset, str(result.file)) for result in module] == [(512, "memory.bin")]
    raw = backend.scan_bytes(data, name="memory.bin")
    assert raw.file == "memory.bin"
    assert [result.offset for result in raw] == [512]


@pytest.mark.usefixtures("backend")
def test_scan_bytes_extracts_through_a_temporary_file(tmp_path: Path) -> None:
    data = gzip.compress(NESTED_TEXT, mtime=0)
    out = tmp_path / "out"
    (module,) = binwalk.scan_bytes(data, name="blob.gz", extract=True, directory=str(out))
    assert module.errors == []
    (result,) = module.results
    assert str(result.file) == "blob.gz"
    assert result.extraction is not None
    assert result.extraction.success
    (extracted,) = result.extraction.files
    assert Path(extracted).read_bytes() == NESTED_TEXT
    assert Path(extracted).is_relative_to(out.resolve())


@pytest.mark.usefixtures("backend")
def test_scan_bytes_with_signature_and_entropy() -> None:
    data = (FIXTURES / "embedded_512.bin").read_bytes()
    signature, entropy = binwalk.scan_bytes(data, name="memory.bin", signature=True, entropy=True)
    assert (signature.name, entropy.name) == ("Signature", "Entropy")
    assert [result.offset for result in signature] == [512]
    assert entropy.results[0].offset == 0
    assert entropy.file == "memory.bin"


def test_capability_check_names_missing_option(backend: BinwalkV3Backend) -> None:
    info = backend.info
    assert info is not None
    reduced = type(info)(info.path, info.version, info.options - {"--carve"}, info.source)
    backend.info = reduced
    try:
        with pytest.raises(binwalk.ModuleException, match="does not support --carve"):
            backend.scan(str(FIXTURES / "simple.zip"), carve=True)
    finally:
        backend.info = info
