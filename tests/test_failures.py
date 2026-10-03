"""Failure handling: what a caller sees when binwalk or the environment misbehaves."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import binwalk
from binwalk._binary import BINARY_ENV_VAR
from binwalk._v3_backend import BinwalkV3Backend
from tests.helpers import FIXTURES, write_nested_gzip

if TYPE_CHECKING:
    from collections.abc import Generator

    from binwalk._binary import BinaryInfo

REPO = Path(__file__).resolve().parent.parent

if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def _unreadable(path: Path) -> Generator[None, None, None]:
        with path.open("r+b") as handle:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, path.stat().st_size)
            yield

else:

    @contextmanager
    def _unreadable(path: Path) -> Generator[None, None, None]:
        path.chmod(0)
        if os.access(path, os.R_OK):
            pytest.skip("running as a user that can read files without read permission")
        yield


@pytest.mark.usefixtures("backend")
def test_timeout_is_reported_in_errors() -> None:
    (module,) = binwalk.scan(str(FIXTURES / "multi_signatures.bin"), timeout=0.0001)
    assert module.errors == ["binwalk timed out after 0.0001 seconds"]
    assert module.results == []


@pytest.mark.usefixtures("backend")
def test_no_timeout_still_scans() -> None:
    (module,) = binwalk.scan(str(FIXTURES / "multi_signatures.bin"), timeout=None)
    assert [result.offset for result in module] == [0, 638, 1276]


def test_binary_removed_after_validation_is_reported(tmp_path: Path, binary: BinaryInfo) -> None:
    copy = tmp_path / Path(binary.path).name
    shutil.copy2(binary.path, copy)
    backend = BinwalkV3Backend(str(copy))
    assert backend.available
    copy.unlink()
    (scanned,) = backend.scan(str(FIXTURES / "simple.zip"))
    assert scanned.results == []
    (error,) = scanned.errors
    assert error.startswith(f"Failed to run {copy.resolve()}: ")


@pytest.mark.usefixtures("backend")
def test_nonzero_exit_is_reported_with_binwalk_message(tmp_path: Path) -> None:
    target = write_nested_gzip(tmp_path / "data.gz", levels=1)
    not_a_directory = tmp_path / "occupied"
    not_a_directory.write_bytes(b"this is a file, so binwalk cannot create its output here")
    (module,) = binwalk.scan(str(target), extract=True, directory=str(not_a_directory))
    (error,) = module.errors
    assert error.startswith("binwalk exited with code ")
    assert "ERROR" in error
    assert not (tmp_path / "occupied").is_dir()


def test_unreadable_file_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "locked.bin"
    target.write_bytes(bytes(4096))
    with _unreadable(target):
        (module,) = binwalk.scan(str(target), entropy=True)
    (error,) = module.errors
    assert error.startswith(f"Error scanning {target}: ")
    assert module.results == []


def test_scan_bytes_without_binary_raises_module_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(BINARY_ENV_VAR, str(tmp_path / "does-not-exist.exe"))
    binwalk.reset_backend()
    expected = "Scan failed: Binwalk v3 binary not available"
    with pytest.raises(binwalk.ModuleException, match=expected):
        binwalk.scan_bytes(b"PK\x03\x04 not scanned")
    (module,) = binwalk.scan_bytes(bytes(range(256)) * 8, entropy=True)
    assert module.name == "Entropy"
    assert module.results[0].entropy == pytest.approx(1.0)


def test_scan_bytes_capability_error_is_not_rewrapped(backend: BinwalkV3Backend) -> None:
    info = backend.info
    assert info is not None
    backend.info = type(info)(info.path, info.version, info.options - {"--extract"}, info.source)
    try:
        expected = r"^binwalk .* does not support --extract"
        with pytest.raises(binwalk.ModuleException, match=expected):
            binwalk.scan_bytes(b"data", extract=True)
    finally:
        backend.info = info


@pytest.mark.usefixtures("backend")
def test_same_size_different_content_in_extraction_directory_is_refused(tmp_path: Path) -> None:
    target = write_nested_gzip(tmp_path / "fw.gz", levels=1)
    out = tmp_path / "out"
    out.mkdir()
    (out / "fw.gz").write_bytes(bytes(target.stat().st_size))
    with pytest.raises(binwalk.ModuleException, match="already exists and is a different file"):
        binwalk.scan(str(target), extract=True, directory=str(out))


@pytest.mark.usefixtures("backend")
def test_identical_copy_in_extraction_directory_is_accepted(tmp_path: Path) -> None:
    target = write_nested_gzip(tmp_path / "fw.gz", levels=1)
    out = tmp_path / "out"
    out.mkdir()
    shutil.copy2(target, out / "fw.gz")
    (module,) = binwalk.scan(str(target), extract=True, directory=str(out))
    assert module.errors == []
    (result,) = module.results
    assert result.extraction is not None
    assert result.extraction.success
    assert result.file == str(target)


def test_save_plot_without_matplotlib_names_the_extra(tmp_path: Path) -> None:
    target = tmp_path / "data.bin"
    target.write_bytes(bytes(2048))
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(REPO)!r})\n"
        "import binwalk\n"
        "try:\n"
        f"    binwalk.scan({str(target)!r}, entropy=True, save=True)\n"
        "except binwalk.ModuleException as exc:\n"
        "    print(f'ModuleException: {exc}')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", script], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == (
        "ModuleException: Saving entropy plots requires matplotlib: pip install binwalk3[plot]"
    )
    assert not target.with_name("data.bin.png").exists()
