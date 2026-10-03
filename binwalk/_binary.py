"""Locate a binwalk v3 executable and detect what it supports."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import cast

BINARY_ENV_VAR = "BINWALK3_BINARY"
BUNDLED_DIR = Path(__file__).resolve().parent / "binwalk_bin"
MANIFEST_PATH = BUNDLED_DIR / "manifest.json"
PATH_NAMES = ("binwalk3", "binwalk")

_BUNDLED_NAMES: dict[tuple[str, str], str] = {
    ("windows", "amd64"): "binwalk_windows_x64.exe",
    ("windows", "x86_64"): "binwalk_windows_x64.exe",
}
_VERSION_RE = re.compile(r"\bbinwalk\s+v?(\d+)\.(\d+)\.(\d+)", re.IGNORECASE)
_LONG_OPTION_RE = re.compile(r"(?<![\w-])--([a-z][a-z0-9-]*)")
_PROBE_TIMEOUT = 30.0
_REQUIRED_MAJOR = 3
_CREATE_NO_WINDOW = 0x08000000


def subprocess_flags() -> int:
    """Return process creation flags that keep console windows hidden on Windows.

    Returns:
        ``CREATE_NO_WINDOW`` on Windows, otherwise 0.
    """
    return _CREATE_NO_WINDOW if os.name == "nt" else 0


def parse_version(text: str) -> tuple[int, int, int] | None:
    """Extract a ``major.minor.patch`` binwalk version from command output.

    Args:
        text: Output of ``binwalk --version`` or a v2 usage banner.

    Returns:
        The version tuple, or None if no version string is present.
    """
    match = _VERSION_RE.search(text)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def parse_long_options(help_text: str) -> frozenset[str]:
    """Collect the long option names listed in ``binwalk --help`` output.

    Args:
        help_text: Output of ``binwalk --help``.

    Returns:
        Option names including the leading dashes, for example ``--directory``.
    """
    return frozenset(f"--{name}" for name in _LONG_OPTION_RE.findall(help_text))


@dataclass(frozen=True)
class BinaryInfo:
    """A validated binwalk v3 executable.

    Attributes:
        path: Absolute path to the executable.
        version: Version reported by ``--version``.
        options: Long options listed by ``--help``.
        source: How the executable was found: ``env``, ``bundled``, ``path`` or ``explicit``.
    """

    path: str
    version: tuple[int, int, int]
    options: frozenset[str] = field(default_factory=frozenset)
    source: str = "explicit"

    @property
    def version_string(self) -> str:
        """Return the version as ``major.minor.patch``.

        Returns:
            The dotted version string.
        """
        return ".".join(str(part) for part in self.version)

    def supports(self, option: str) -> bool:
        """Report whether the executable accepts a long option.

        Args:
            option: Long option name including dashes, for example ``--carve``.

        Returns:
            True if the option appears in ``--help``.
        """
        return option in self.options


def _run_probe(path: str, argument: str) -> str | None:
    try:
        completed = subprocess.run(
            [path, argument],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_PROBE_TIMEOUT,
            check=False,
            creationflags=subprocess_flags(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout + completed.stderr


@lru_cache(maxsize=32)
def _probe_cached(
    path: str, mtime_ns: int, size: int
) -> tuple[tuple[int, int, int], frozenset[str]] | None:
    del mtime_ns, size
    version_text = _run_probe(path, "--version")
    if version_text is None:
        return None
    version = parse_version(version_text)
    if version is None or version[0] != _REQUIRED_MAJOR:
        return None
    help_text = _run_probe(path, "--help") or ""
    return version, parse_long_options(help_text)


def probe_binary(path: str | os.PathLike[str], source: str = "explicit") -> BinaryInfo | None:
    """Run an executable and accept it only if it is binwalk 3.x.

    Results are cached per path, modification time and size, so a rebuilt binary is re-probed.

    Args:
        path: Executable path or a bare command name resolvable on PATH.
        source: Label recorded in the returned BinaryInfo.

    Returns:
        BinaryInfo for a working binwalk 3.x executable, otherwise None.
    """
    resolved = shutil.which(os.fspath(path))
    if resolved is None:
        return None
    resolved = str(Path(resolved).resolve())
    try:
        stat = Path(resolved).stat()
    except OSError:
        return None
    probed = _probe_cached(resolved, stat.st_mtime_ns, stat.st_size)
    if probed is None:
        return None
    version, options = probed
    return BinaryInfo(path=resolved, version=version, options=options, source=source)


def bundled_binary_path() -> Path | None:
    """Return the bundled executable for this platform if the wheel includes one.

    Returns:
        Path to the bundled executable, or None if this platform has none or it is missing.
    """
    name = _BUNDLED_NAMES.get((platform.system().lower(), platform.machine().lower()))
    if name is None:
        return None
    candidate = BUNDLED_DIR / name
    return candidate if candidate.is_file() else None


@dataclass
class Discovery:
    """Outcome of searching for a binwalk v3 executable.

    Attributes:
        binary: The executable that will be used, or None if none qualified.
        tried: Human-readable notes on each candidate that was checked.
    """

    binary: BinaryInfo | None
    tried: list[str] = field(default_factory=list[str])


def discover_binary() -> Discovery:
    """Find the binwalk v3 executable to use.

    Search order: the ``BINWALK3_BINARY`` environment variable, the bundled executable, then
    ``binwalk3`` and ``binwalk`` on PATH. When the environment variable is set, no other
    location is tried, so a misconfigured override fails loudly instead of being bypassed.

    Returns:
        Discovery describing the chosen executable and every candidate checked.
    """
    tried: list[str] = []
    override = os.environ.get(BINARY_ENV_VAR)
    if override:
        info = probe_binary(override, source="env")
        tried.append(
            f"{BINARY_ENV_VAR}={override}: {'ok' if info else 'not a working binwalk 3.x'}"
        )
        return Discovery(info, tried)

    bundled = bundled_binary_path()
    if bundled is not None:
        info = probe_binary(bundled, source="bundled")
        tried.append(f"bundled {bundled}: {'ok' if info else 'failed to run'}")
        if info is not None:
            return Discovery(info, tried)
    else:
        tried.append(f"bundled: none for {platform.system()} {platform.machine()}")

    for name in PATH_NAMES:
        location = shutil.which(name)
        if location is None:
            tried.append(f"{name} on PATH: not found")
            continue
        info = probe_binary(location, source="path")
        tried.append(f"{name} on PATH ({location}): {'ok' if info else 'not binwalk 3.x'}")
        if info is not None:
            return Discovery(info, tried)
    return Discovery(None, tried)


def read_manifest() -> dict[str, object]:
    """Read the build manifest that ships next to the bundled executable.

    Returns:
        The manifest contents, or an empty dict if there is no readable manifest.
    """
    try:
        loaded: object = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    entries = cast("dict[object, object]", loaded)
    return {str(key): value for key, value in entries.items()}
