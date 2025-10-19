"""Binwalk core module compatibility layer.

This module provides the v2-compatible interface for binwalk,
exposing the same classes and functions that users expect from
binwalk v2, while using the faster v3 backend internally.
"""

from .module import Module, ModuleException, Modules, Result

__all__ = ["Modules", "Module", "Result", "ModuleException"]
