"""Helpers shared by the test modules."""

from __future__ import annotations

import gzip
import os
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LEGACY_ENV_VAR = "BINWALK3_LEGACY_BINARY"
NESTED_TEXT = b"binwalk3 nested payload\n" * 64


def write_nested_gzip(path: Path, levels: int) -> Path:
    """Write ``NESTED_TEXT`` gzip-compressed ``levels`` times.

    Args:
        path: Output file.
        levels: Number of gzip layers.

    Returns:
        The written path.
    """
    data = NESTED_TEXT
    for _ in range(levels):
        data = gzip.compress(data, mtime=0)
    path.write_bytes(data)
    return path


SEVEN_ZIP = "7z" if os.name == "nt" else "7zz"


def require_7z() -> None:
    """Skip the calling test when the 7-Zip program binwalk calls is not on PATH."""
    if shutil.which(SEVEN_ZIP) is None:
        pytest.skip(f"{SEVEN_ZIP} is not on PATH; ZIP extraction uses 7-Zip")
