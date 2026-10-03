"""Wheels and sdist built from this source tree with the hooks in setup.py."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BUNDLED_EXE = REPO / "binwalk" / "binwalk_bin" / "binwalk_windows_x64.exe"
EXE_MEMBER = "binwalk/binwalk_bin/binwalk_windows_x64.exe"
MANIFEST_MEMBER = "binwalk/binwalk_bin/manifest.json"
IS_WINDOWS_X64 = platform.system() == "Windows" and platform.machine().lower() in {
    "amd64",
    "x86_64",
}


def _build(out: Path, *flags: str, pure: bool) -> list[Path]:
    env = dict(os.environ)
    if pure:
        env["BINWALK3_PURE_WHEEL"] = "1"
    else:
        env.pop("BINWALK3_PURE_WHEEL", None)
    completed = subprocess.run(
        [sys.executable, "-m", "build", *flags, "--no-isolation", "--outdir", str(out), str(REPO)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout[-2000:] + completed.stderr[-2000:]
    return sorted(out.iterdir())


def _wheel_metadata(names: list[str], archive: zipfile.ZipFile) -> str:
    (wheel_file,) = [name for name in names if name.endswith(".dist-info/WHEEL")]
    return archive.read(wheel_file).decode("utf-8")


def test_pure_wheel_leaves_out_executable_left_in_build_directory(tmp_path: Path) -> None:
    stale = REPO / "build" / "lib" / "binwalk" / "binwalk_bin"
    stale.mkdir(parents=True, exist_ok=True)
    (stale / "binwalk_windows_x64.exe").write_bytes(b"MZ stale executable from an earlier build")
    (stale / "manifest.json").write_text("{}", encoding="utf-8")
    (wheel,) = _build(tmp_path, "--wheel", pure=True)
    assert wheel.name.endswith("-py3-none-any.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "Root-Is-Purelib: true" in _wheel_metadata(names, archive)
    assert EXE_MEMBER not in names
    assert MANIFEST_MEMBER not in names
    assert {"binwalk/_v3_backend.py", "binwalk/py.typed", "binwalk/binwalk_bin/__init__.py"} <= set(
        names
    )


@pytest.mark.skipif(not IS_WINDOWS_X64, reason="the bundled executable ships for Windows x64 only")
def test_windows_wheel_bundles_the_built_executable(tmp_path: Path) -> None:
    (wheel,) = _build(tmp_path, "--wheel", pure=False)
    assert wheel.name.endswith("-py3-none-win_amd64.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "Root-Is-Purelib: false" in _wheel_metadata(names, archive)
        executable = archive.read(EXE_MEMBER)
        manifest = json.loads(archive.read(MANIFEST_MEMBER))
    assert executable == BUNDLED_EXE.read_bytes()
    assert manifest["sha256"] == hashlib.sha256(executable).hexdigest()


def test_sdist_has_no_build_outputs_and_builds_a_pure_wheel(tmp_path: Path) -> None:
    artifacts = _build(tmp_path, pure=False)
    (sdist,) = [path for path in artifacts if path.name.endswith(".tar.gz")]
    (wheel,) = [path for path in artifacts if path.suffix == ".whl"]
    assert len(artifacts) == 2
    with tarfile.open(sdist) as archive:
        names = [name.split("/", 1)[1] for name in archive.getnames() if "/" in name]
    assert not [name for name in names if name.endswith(".exe")]
    assert MANIFEST_MEMBER not in names
    assert not [name for name in names if name.startswith(("tests/", "vendor/", "patches/"))]
    assert {"README.md", "LICENSE", "CHANGELOG.md", "docs/BUILDING.md", "setup.py"} <= set(names)
    assert wheel.name.endswith("-py3-none-any.whl")
    with zipfile.ZipFile(wheel) as archive:
        assert EXE_MEMBER not in archive.namelist()
