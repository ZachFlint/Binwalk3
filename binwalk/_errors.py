"""Exception types shared by every module in the package."""

from __future__ import annotations


class ModuleException(Exception):
    """Raised when a scan cannot be configured or run.

    The name matches ``binwalk.core.exceptions.ModuleException`` from binwalk v2.
    """
