"""Shared fixtures: real binwalk executables."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

import binwalk
from binwalk._binary import BinaryInfo, probe_binary
from tests.helpers import LEGACY_ENV_VAR

if TYPE_CHECKING:
    from binwalk._v3_backend import BinwalkV3Backend


@pytest.fixture(autouse=True)
def _fresh_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BINWALK3_BINARY", raising=False)
    binwalk.reset_backend()


@pytest.fixture
def backend() -> BinwalkV3Backend:
    """Return the backend the package would use, failing if no binwalk 3.x is available.

    Returns:
        The shared backend.
    """
    instance = binwalk.get_backend()
    if not instance.available:
        pytest.fail(instance.unavailable_reason())
    return instance


@pytest.fixture
def binary(backend: BinwalkV3Backend) -> BinaryInfo:
    """Return the validated executable used by the backend.

    Args:
        backend: The shared backend.

    Returns:
        Its BinaryInfo.
    """
    assert backend.info is not None
    return backend.info


@pytest.fixture
def legacy_binary() -> BinaryInfo:
    """Return a binwalk 3.1.0 executable named by ``BINWALK3_LEGACY_BINARY``.

    Returns:
        The legacy executable's BinaryInfo.
    """
    location = os.environ.get(LEGACY_ENV_VAR)
    if not location:
        pytest.skip(f"{LEGACY_ENV_VAR} is not set; legacy-binary tests need a binwalk 3.1.0 build")
    info = probe_binary(location)
    if info is None or info.version != (3, 1, 0):
        pytest.fail(f"{LEGACY_ENV_VAR}={location} is not a working binwalk 3.1.0")
    return info
