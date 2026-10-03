"""Extraction, recursion and carving with the real binwalk v3 executable."""

from __future__ import annotations

import gzip
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import binwalk
from binwalk._v3_backend import BinwalkV3Backend
from tests.helpers import FIXTURES, NESTED_TEXT, SEVEN_ZIP, require_7z, write_nested_gzip

if TYPE_CHECKING:
    from binwalk._binary import BinaryInfo


@pytest.mark.usefixtures("backend")
def test_gzip_extraction_populates_v2_extractor_output(tmp_path: Path) -> None:
    target = write_nested_gzip(tmp_path / "single.gz", levels=1)
    out = tmp_path / "out"
    (module,) = binwalk.scan(str(target), signature=True, extract=True, directory=str(out))
    (result,) = module.results
    assert result.name == "gzip"
    assert result.extraction is not None
    assert result.extraction.success
    assert result.extraction.extractor == "gzip_built_in"
    assert len(result.extraction.files) == 1
    assert Path(result.extraction.files[0]).read_bytes() == NESTED_TEXT
    info = module.extractor.output[str(target.resolve())]
    assert info.extracted[0].files == list(result.extraction.files)
    assert info.extracted[0].command == "gzip_built_in"
    assert info.directory == str(out.resolve() / "single.gz.extracted")
    assert module.extractor.enabled
    assert module.extractor.directory == str(out.resolve())


@pytest.mark.usefixtures("backend")
def test_matryoshka_reports_nested_results_with_depth(tmp_path: Path) -> None:
    target = write_nested_gzip(tmp_path / "triple.gz", levels=3)
    out = tmp_path / "out"
    (module,) = binwalk.scan(str(target), extract=True, matryoshka=True, directory=str(out))
    assert [(result.name, result.depth) for result in module] == [
        ("gzip", 0),
        ("gzip", 1),
        ("gzip", 2),
    ]
    assert module.results[0].file == str(target)
    for nested in module.results[1:]:
        assert nested.file is not None
        assert Path(nested.file.path).is_relative_to(out.resolve())
    innermost = module.results[2].extraction
    assert innermost is not None
    assert Path(innermost.files[0]).read_bytes() == NESTED_TEXT
    assert set(module.extractor.output) == {
        str(target.resolve()),
        *(r.file.path for r in module.results[1:] if r.file),
    }


@pytest.mark.usefixtures("backend")
def test_matryoshka_depth_limit(tmp_path: Path) -> None:
    target = write_nested_gzip(tmp_path / "triple.gz", levels=3)
    (module,) = binwalk.scan(str(target), "-e", "-M", "--depth", "1", directory=str(tmp_path / "a"))
    assert [result.depth for result in module] == [0, 1]
    (module,) = binwalk.scan(str(target), extract=True, matryoshka=2, directory=str(tmp_path / "b"))
    assert [result.depth for result in module] == [0, 1, 2]


@pytest.mark.usefixtures("backend")
def test_without_matryoshka_only_top_level(tmp_path: Path) -> None:
    target = write_nested_gzip(tmp_path / "triple.gz", levels=3)
    (module,) = binwalk.scan(str(target), extract=True, directory=str(tmp_path / "out"))
    assert [result.depth for result in module] == [0]


@pytest.mark.usefixtures("backend")
def test_rescan_into_same_directory_reuses_link(tmp_path: Path) -> None:
    target = write_nested_gzip(tmp_path / "data.gz", levels=1)
    out = str(tmp_path / "out")
    first = binwalk.scan(str(target), extract=True, directory=out)[0]
    second = binwalk.scan(str(target), extract=True, directory=out)[0]
    assert first.errors == second.errors == []
    assert [r.offset for r in first] == [r.offset for r in second] == [0]
    extraction = second.results[0].extraction
    assert extraction is not None
    assert extraction.success
    assert [Path(name).read_bytes() for name in extraction.files] == [NESTED_TEXT]


@pytest.mark.usefixtures("backend")
def test_different_file_with_same_name_is_refused(tmp_path: Path) -> None:
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()
    first = write_nested_gzip(first_dir / "fw.bin", levels=1)
    second = second_dir / "fw.bin"
    second.write_bytes(gzip.compress(b"different contents", mtime=0))
    out = str(tmp_path / "out")
    binwalk.scan(str(first), extract=True, directory=out)
    with pytest.raises(binwalk.ModuleException, match="already exists and is a different file"):
        binwalk.scan(str(second), extract=True, directory=out)


def _other_volume_dir() -> Path | None:
    if os.name != "nt":
        return None
    here = Path(__file__).resolve().drive.lower()
    temp = Path(tempfile.gettempdir()).resolve()
    return temp if temp.drive.lower() != here else None


@pytest.mark.usefixtures("backend")
def test_cross_volume_extraction() -> None:
    other = _other_volume_dir()
    if other is None:
        pytest.skip("needs the system temp directory on a different drive than the repository")
    source_dir = Path(tempfile.mkdtemp(prefix="binwalk3-src-", dir=other))
    build_dir = Path(__file__).resolve().parent.parent / "build"
    build_dir.mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="cross-", dir=build_dir))
    try:
        target = write_nested_gzip(source_dir / "cross.gz", levels=1)
        (module,) = binwalk.scan(str(target), extract=True, directory=str(out))
        assert module.errors == []
        (result,) = module.results
        assert result.extraction is not None
        assert result.extraction.success
        assert Path(result.extraction.files[0]).read_bytes() == NESTED_TEXT
        assert (out / "cross.gz").read_bytes() == target.read_bytes()
    finally:
        shutil.rmtree(out)
        shutil.rmtree(source_dir)


@pytest.mark.usefixtures("backend")
def test_carve_writes_raw_files(tmp_path: Path) -> None:
    source = FIXTURES / "embedded_512.bin"
    target = tmp_path / "embedded_512.bin"
    shutil.copy2(source, target)
    out = tmp_path / "out"
    (module,) = binwalk.scan(str(target), carve=True, directory=str(out))
    assert module.errors == []
    (result,) = module.results
    assert result.carved is not None
    data = source.read_bytes()
    assert Path(result.carved).read_bytes() == data[512 : 512 + 126]
    assert module.extractor.output[str(target.resolve())].carved == {512: result.carved}


@pytest.mark.usefixtures("backend")
def test_zip_extraction_uses_7z(tmp_path: Path) -> None:
    require_7z()
    (module,) = binwalk.scan(str(FIXTURES / "nested.bin"), extract=True, directory=str(tmp_path))
    (result,) = module.results
    assert result.extraction is not None
    assert result.extraction.extractor == SEVEN_ZIP
    assert result.extraction.success
    assert [Path(name).name for name in result.extraction.files] == ["test.txt"]


@pytest.mark.usefixtures("backend")
def test_extraction_warnings_surface_without_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "")
    (module,) = binwalk.scan(str(FIXTURES / "nested.bin"), extract=True, directory=str(tmp_path))
    (result,) = module.results
    assert result.extraction is not None
    assert not result.extraction.success
    assert module.errors == []
    assert any(
        "program not found" in warning or "external extractor" in warning
        for warning in module.warnings
    )


def test_legacy_binary_extraction_and_recursion(tmp_path: Path, legacy_binary: BinaryInfo) -> None:
    backend = BinwalkV3Backend(legacy_binary.path)
    target = write_nested_gzip(tmp_path / "triple.gz", levels=3)
    (scanned,) = backend.scan(
        str(target), extract=True, matryoshka=True, directory=str(tmp_path / "out")
    )
    assert scanned.errors == []
    assert [result.depth for result in scanned] == [0, 1, 2]
