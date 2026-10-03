"""binwalk v2 compatible core classes."""

from __future__ import annotations

from binwalk.core.exceptions import ModuleException
from binwalk.core.module import (
    ExtractDetails,
    ExtractInfo,
    Extractor,
    FilePath,
    Module,
    Modules,
    Result,
)

__all__ = [
    "ExtractDetails",
    "ExtractInfo",
    "Extractor",
    "FilePath",
    "Module",
    "ModuleException",
    "Modules",
    "Result",
]
