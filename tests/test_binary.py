"""Binary discovery, validation and capability detection against real executables."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

import binwalk
from binwalk._binary import (
    BINARY_ENV_VAR,
    MANIFEST_PATH,
    BinaryInfo,
    bundled_binary_path,
    discover_binary,
    parse_long_options,
    parse_version,
    probe_binary,
)

IS_WINDOWS_X64 = platform.system() == "Windows" and platform.machine().lower() in {
    "amd64",
    "x86_64",
}


def _write_fake_v2(directory: Path) -> Path:
    if os.name == "nt":
        script = directory / "binwalk.cmd"
        script.write_text("@echo off\r\necho Binwalk v2.3.4\r\n", encoding="ascii")
    else:
        script = directory / "binwalk"
        script.write_text("#!/bin/sh\necho 'Binwalk v2.3.4'\n", encoding="ascii")
        script.chmod(0o755)
    return script


@pytest.mark.skipif(not IS_WINDOWS_X64, reason="the bundled executable ships for Windows x64 only")
def test_bundled_binary_matches_manifest() -> None:
    bundled = bundled_binary_path()
    assert bundled is not None, "Windows x64 install is missing binwalk_windows_x64.exe"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert hashlib.sha256(bundled.read_bytes()).hexdigest() == manifest["sha256"]
    assert bundled.stat().st_size == manifest["size"]
    completed = subprocess.run(
        [str(bundled), "--version"], capture_output=True, text=True, check=True
    )
    assert completed.stdout.strip() == f"binwalk {manifest['binwalk_version']}"
    assert (
        binwalk.__binwalk_core_version__
        == f"{manifest['binwalk_version']}+{manifest['upstream_commit'][:7]}"
    )


@pytest.mark.skipif(not IS_WINDOWS_X64, reason="the bundled executable ships for Windows x64 only")
def test_discovery_prefers_bundled_binary() -> None:
    found = discover_binary()
    assert found.binary is not None
    assert found.binary.source == "bundled"
    assert Path(found.binary.path) == bundled_binary_path()


def test_real_binary_reports_v3_and_needed_options(binary: BinaryInfo) -> None:
    assert binary.version[0] == 3
    for option in (
        "--log",
        "--quiet",
        "--extract",
        "--matryoshka",
        "--directory",
        "--include",
        "--exclude",
    ):
        assert binary.supports(option), option
    assert not binary.supports("--not-an-option")


def test_parsers_read_real_help_and_version_output(binary: BinaryInfo) -> None:
    help_text = subprocess.run(
        [binary.path, "--help"], capture_output=True, text=True, check=True
    ).stdout
    version_text = subprocess.run(
        [binary.path, "--version"], capture_output=True, text=True, check=True
    ).stdout
    assert parse_long_options(help_text) == binary.options
    assert parse_version(version_text) == binary.version
    assert parse_version("Binwalk v2.3.4\nCraig Heffner") == (2, 3, 4)
    assert parse_version("no version here") is None


def test_v2_executable_is_rejected(tmp_path: Path) -> None:
    fake = _write_fake_v2(tmp_path)
    assert (
        subprocess.run([str(fake)], capture_output=True, text=True, check=True).stdout.strip()
        == "Binwalk v2.3.4"
    )
    assert probe_binary(fake) is None


def test_file_that_is_not_a_program_is_rejected(tmp_path: Path) -> None:
    garbage = tmp_path / ("binwalk.exe" if os.name == "nt" else "binwalk")
    garbage.write_bytes(b"this is not an executable image")
    garbage.chmod(0o755)
    assert probe_binary(garbage) is None
    assert probe_binary(tmp_path / "missing-binwalk") is None


def test_program_that_exits_with_an_error_is_rejected(tmp_path: Path) -> None:
    if os.name == "nt":
        script = tmp_path / "binwalk.cmd"
        script.write_text("@echo off\r\necho binwalk 3.1.1\r\nexit /b 3\r\n", encoding="ascii")
    else:
        script = tmp_path / "binwalk"
        script.write_text("#!/bin/sh\necho 'binwalk 3.1.1'\nexit 3\n", encoding="ascii")
        script.chmod(0o755)
    completed = subprocess.run([str(script)], capture_output=True, text=True, check=False)
    assert (completed.returncode, completed.stdout.strip()) == (3, "binwalk 3.1.1")
    assert probe_binary(script) is None


@pytest.mark.skipif(IS_WINDOWS_X64, reason="Windows x64 uses the bundled executable before PATH")
def test_discovery_falls_back_to_path() -> None:
    found = discover_binary()
    assert found.binary is not None, found.tried
    assert found.binary.source == "path"
    assert Path(found.binary.path).name in {"binwalk", "binwalk3"}
    assert found.tried[0].startswith("bundled: none for ")


def test_env_override_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, binary: BinaryInfo
) -> None:
    copy = tmp_path / Path(binary.path).name
    shutil.copy2(binary.path, copy)
    monkeypatch.setenv(BINARY_ENV_VAR, str(copy))
    binwalk.reset_backend()
    backend = binwalk.get_backend()
    assert backend.available
    assert backend.info is not None
    assert backend.info.source == "env"
    assert Path(backend.binary_path) == copy.resolve()


def test_bad_env_override_does_not_fall_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(BINARY_ENV_VAR, str(_write_fake_v2(tmp_path)))
    binwalk.reset_backend()
    backend = binwalk.get_backend()
    assert not backend.available
    assert BINARY_ENV_VAR in backend.unavailable_reason()
    with pytest.raises(binwalk.ModuleException, match="not available"):
        binwalk.scan(str(Path(__file__)))


def test_missing_binary_still_allows_entropy_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(BINARY_ENV_VAR, str(tmp_path / "does-not-exist.exe"))
    binwalk.reset_backend()
    target = tmp_path / "data.bin"
    target.write_bytes(bytes(range(256)) * 8)
    modules = binwalk.scan(str(target), entropy=True)
    assert [module.name for module in modules] == ["Entropy"]
    assert modules[0].results[0].entropy == pytest.approx(1.0)
