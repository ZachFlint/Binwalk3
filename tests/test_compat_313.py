"""Behavior that binwalk3 3.1.3 callers depend on."""

from __future__ import annotations

from pathlib import Path

import pytest

import binwalk
from binwalk import V3ModuleResult, V3ScanResult
from binwalk._v3_backend import BinwalkV3Backend
from binwalk.core import Module, ModuleException, Modules, Result
from binwalk.core.module import FilePath
from tests.helpers import FIXTURES

SIMPLE = str(FIXTURES / "simple.zip")
MULTI = str(FIXTURES / "multi_signatures.bin")


@pytest.mark.usefixtures("backend")
def test_one_module_per_file_in_order() -> None:
    modules = Modules().execute(MULTI, SIMPLE)
    assert [type(module) for module in modules] == [Module, Module]
    assert [module.file for module in modules] == [MULTI, SIMPLE]
    assert [len(module) for module in modules] == [3, 1]
    assert [result.offset for result in modules[0]] == [0, 638, 1276]


def test_result_positional_constructor() -> None:
    result = Result(0x1000, "Test signature", 100, 0.5, "x.bin", "zip")
    assert (result.offset, result.description, result.size, result.entropy) == (
        0x1000,
        "Test signature",
        100,
        0.5,
    )
    assert result.file == "x.bin"
    assert result.module == "zip"
    assert repr(result) == "<Result: offset=0x1000, description='Test signature'>"
    assert vars(Result(extra_attribute=7))["extra_attribute"] == 7


def test_v3_dataclasses_keep_313_fields() -> None:
    item = V3ScanResult(16, "desc", 4, 0.25, "f.bin", "entropy")
    assert repr(item) == "<V3ScanResult: offset=0x10, description='desc', size=4, entropy=0.25>"
    container = V3ModuleResult()
    container.results.append(item)
    assert list(container) == [item]
    assert len(container) == 1
    assert container.errors == []


def test_reprs_and_file_path_helpers(tmp_path: Path) -> None:
    assert repr(V3ScanResult(255, "plain")) == "<V3ScanResult: offset=0xff, description='plain'>"
    (module,) = binwalk.scan(str(tmp_path / "absent.bin"), entropy=True)
    assert repr(module) == (
        f"<Module Entropy: file='{tmp_path / 'absent.bin'}', results=0, errors=1>"
    )
    assert FilePath(str(tmp_path / "absent.bin")).size == 0
    present = tmp_path / "present.bin"
    present.write_bytes(bytes(300))
    (module,) = binwalk.scan(str(present), entropy=True)
    file = module.results[0].file
    assert file is not None
    assert (file.basename, file.size, file.path) == ("present.bin", 300, str(present.resolve()))


def test_backend_scan_returns_v3_module_results(backend: BinwalkV3Backend) -> None:
    scanned = backend.scan(SIMPLE, str(Path(SIMPLE).with_name("absent.bin")))
    assert [type(item) for item in scanned] == [V3ModuleResult, V3ModuleResult]
    assert [(result.offset, result.module, result.file) for result in scanned[0]] == [
        (0, "zip", SIMPLE)
    ]
    assert scanned[1].errors == [f"File not found: {Path(SIMPLE).with_name('absent.bin')}"]
    with pytest.raises(ValueError, match="No files specified"):
        backend.scan()


def test_backend_singleton_and_reset() -> None:
    first = binwalk.get_backend()
    assert binwalk.get_backend() is first
    binwalk.reset_backend()
    assert binwalk.get_backend() is not first


def test_explicit_binary_path_is_validated(tmp_path: Path) -> None:
    missing = BinwalkV3Backend(str(tmp_path / "nope.exe"))
    assert not missing.available
    assert missing.binary_path == str(tmp_path / "nope.exe")
    with pytest.raises(RuntimeError, match="not available"):
        missing.scan(SIMPLE)


def test_entropy_never_runs_the_binary_plot(tmp_path: Path) -> None:
    target = tmp_path / "e.bin"
    target.write_bytes(bytes(range(256)) * 16)
    before = set(Path.cwd().iterdir())
    modules = binwalk.scan(str(target), entropy=True)
    assert set(Path.cwd().iterdir()) == before
    assert modules[0].plot is None


def test_module_exception_on_failure_is_module_exception() -> None:
    with pytest.raises(ModuleException):
        Modules().execute()
