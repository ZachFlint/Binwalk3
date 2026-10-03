"""Run binwalk v3 from Python through the binwalk v2 API.

>>> import binwalk
>>> for module in binwalk.scan("firmware.bin", signature=True, quiet=True):
...     for result in module.results:
...         print(f"{result.offset:#x} {result.description}")
"""

from __future__ import annotations

from binwalk.__version__ import __api_version__, __binwalk_core_version__, __version__
from binwalk._errors import ModuleException
from binwalk._options import UnknownOptionWarning, UnsupportedOptionWarning, parse_request
from binwalk._v3_backend import (
    V3Extraction,
    V3ModuleResult,
    V3ScanResult,
    get_backend,
    reset_backend,
)
from binwalk.core.module import (
    ExtractDetails,
    ExtractInfo,
    Extractor,
    FilePath,
    Module,
    Modules,
    Result,
    build_modules,
)


def scan(*args: object, **kwargs: object) -> list[Module]:
    """Scan files and return their results.

    Accepts binwalk v2 calling styles, including command line options as strings
    (``scan("--signature", "-e", "fw.bin")``) and option keywords (``scan("fw.bin",
    extract=True, directory="out")``). Raises ModuleException if no files were given, an
    option is invalid, or the scan cannot run.

    Args:
        *args: Files to scan and binwalk v2 command line options.
        **kwargs: Options such as ``signature``, ``extract``, ``directory``, ``matryoshka``,
            ``entropy``, ``carve``, ``include``, ``exclude``, ``threads``, ``signatures``,
            ``exclude_signatures``, ``search_all`` and ``timeout``.

    Returns:
        For each file, a Signature module and, if entropy was requested, an Entropy module.
    """
    with Modules(*args, **kwargs) as modules:
        return modules.execute()


def execute(*args: object, **kwargs: object) -> list[Module]:
    """Alias of ``scan``, as in binwalk v2. Raises the same exceptions as ``scan``.

    Args:
        *args: Files and command line options.
        **kwargs: Keyword options.

    Returns:
        The same as ``scan``.
    """
    return scan(*args, **kwargs)


def scan_bytes(data: bytes, name: str = "stdin", **kwargs: object) -> list[Module]:
    """Scan in-memory data.

    Args:
        data: Bytes to scan.
        name: Name used as the result file and for extraction output.
        **kwargs: The same keyword options as ``scan``.

    Returns:
        A Signature module and, if entropy was requested, an Entropy module.

    Raises:
        ModuleException: If an option is invalid or the scan fails.
    """
    options = parse_request((), kwargs).options
    try:
        scanned = get_backend().scan_bytes(data, name, **kwargs)
    except ModuleException:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        message = f"Scan failed: {exc}"
        raise ModuleException(message) from exc
    return build_modules(name, scanned, signature=options.runs_signature, entropy=options.entropy)


__all__ = [
    "ExtractDetails",
    "ExtractInfo",
    "Extractor",
    "FilePath",
    "Module",
    "ModuleException",
    "Modules",
    "Result",
    "UnknownOptionWarning",
    "UnsupportedOptionWarning",
    "V3Extraction",
    "V3ModuleResult",
    "V3ScanResult",
    "__api_version__",
    "__binwalk_core_version__",
    "__version__",
    "execute",
    "get_backend",
    "reset_backend",
    "scan",
    "scan_bytes",
]
