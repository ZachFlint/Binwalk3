"""Binwalk v3 with v2-compatible Python API.

This package provides a drop-in replacement for binwalk v2, using the
faster binwalk v3 Rust binary under the hood while maintaining full
API compatibility.

Basic Usage:
    >>> import binwalk
    >>> results = binwalk.scan('firmware.bin')
    >>> for module in results:
    ...     for result in module:
    ...         print(f"Found {result.description} at offset {result.offset:#x}")

Advanced Usage:
    >>> from binwalk import Modules
    >>> modules = Modules()
    >>> results = modules.execute('firmware.bin', extract=True, entropy=True)

The package automatically finds and uses the bundled binwalk v3 binary
on Windows x64 systems, or falls back to system-installed binwalk.
"""

from .__version__ import __api_version__, __binwalk_core_version__, __version__
from ._v3_backend import get_backend
from .core.module import Module, ModuleException, Modules, Result


def scan(*files: str, **kwargs) -> list[Module]:
    """Scan files for embedded files and signatures.

    This is the primary interface for binwalk, providing a simple
    function call that returns scan results. It maintains full
    compatibility with binwalk v2's scan() function.

    Args:
        *files: One or more file paths to scan
        **kwargs: Scan options:
            - signature (bool): Enable signature scanning (default True)
            - quiet (bool): Suppress output (default True)
            - extract (bool): Extract identified files
            - directory (str): Directory for extraction
            - entropy (bool): Calculate entropy
            - matryoshka (bool): Recursive scanning
            - verbose (bool): Verbose output
            - threads (int): Number of threads to use

    Returns:
        List of Module objects containing scan results, one per file

    Raises:
        ModuleException: If scan fails
        RuntimeError: If binwalk binary not available

    Examples:
        Basic scan:
        >>> results = binwalk.scan('firmware.bin')

        Extract files:
        >>> results = binwalk.scan('firmware.bin', extract=True)

        Multiple files with entropy:
        >>> results = binwalk.scan('file1.bin', 'file2.bin', entropy=True)

        Custom extraction directory:
        >>> results = binwalk.scan('firmware.bin', extract=True,
        ...                         directory='/tmp/extracted')
    """
    return Modules().execute(*files, **kwargs)


__all__ = [
    "scan",
    "Modules",
    "Module",
    "Result",
    "ModuleException",
    "__version__",
    "__api_version__",
    "__binwalk_core_version__",
]
