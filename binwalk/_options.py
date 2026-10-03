"""Translate binwalk v2 and binwalk3 arguments into scan options."""

from __future__ import annotations

import argparse
import os
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

from binwalk._errors import ModuleException

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

DEFAULT_TIMEOUT = 600.0
V2_MATRYOSHKA_DEPTH = 8


class UnsupportedOptionWarning(UserWarning):
    """Issued when a binwalk v2 option has no equivalent in binwalk v3 and is ignored."""


class UnknownOptionWarning(UserWarning):
    """Issued when a keyword argument is not a known binwalk v2 or binwalk3 option."""


@dataclass(frozen=True)
class _V2Option:
    short: str | None
    long: str
    takes: str | None = None
    repeat: bool = False
    supported: bool = True


_V2_OPTIONS: tuple[_V2Option, ...] = (
    _V2Option("B", "signature"),
    _V2Option("e", "extract"),
    _V2Option("M", "matryoshka"),
    _V2Option("d", "depth", "int"),
    _V2Option("C", "directory", "str"),
    _V2Option("z", "carve"),
    _V2Option("E", "entropy"),
    _V2Option("F", "fast"),
    _V2Option("J", "save"),
    _V2Option("Q", "nlegend"),
    _V2Option("N", "nplot"),
    _V2Option("H", "high", "float"),
    _V2Option("L", "low", "float"),
    _V2Option("K", "block", "int"),
    _V2Option("q", "quiet"),
    _V2Option("v", "verbose"),
    _V2Option("t", "term"),
    _V2Option("c", "csv"),
    _V2Option("x", "exclude", "str", repeat=True),
    _V2Option("y", "include", "str", repeat=True),
    _V2Option("X", "deflate", supported=False),
    _V2Option("Z", "lzma", supported=False),
    _V2Option("P", "partial", supported=False),
    _V2Option("S", "stop", supported=False),
    _V2Option("Y", "disasm", supported=False),
    _V2Option("T", "minsn", "int", supported=False),
    _V2Option("k", "continue", supported=False),
    _V2Option("D", "dd", "str", repeat=True, supported=False),
    _V2Option("j", "size", "int", supported=False),
    _V2Option("n", "count", "int", supported=False),
    _V2Option("0", "run-as", "str", supported=False),
    _V2Option("u", "limit", "int", supported=False),
    _V2Option("1", "preserve-symlinks", supported=False),
    _V2Option("r", "rm", supported=False),
    _V2Option("V", "subdirs", supported=False),
    _V2Option("l", "length", "int", supported=False),
    _V2Option("o", "offset", "int", supported=False),
    _V2Option("O", "base", "int", supported=False),
    _V2Option("g", "swap", "int", supported=False),
    _V2Option("f", "log", "str", supported=False),
    _V2Option("a", "finclude", "str", supported=False),
    _V2Option("p", "fexclude", "str", supported=False),
    _V2Option("s", "status", "int", supported=False),
    _V2Option("W", "hexdump", supported=False),
    _V2Option("G", "green", supported=False),
    _V2Option("i", "red", supported=False),
    _V2Option("U", "blue", supported=False),
    _V2Option(None, "similar", supported=False),
    _V2Option("w", "terse", supported=False),
    _V2Option("R", "raw", "str", repeat=True, supported=False),
    _V2Option("A", "opcodes", supported=False),
    _V2Option("m", "magic", "str", repeat=True, supported=False),
    _V2Option("b", "dumb", supported=False),
    _V2Option("I", "invalid", supported=False),
)
_V2_BY_LONG = {option.long: option for option in _V2_OPTIONS}
_V2_BY_SHORT = {option.short: option for option in _V2_OPTIONS if option.short}
_BINWALK3_KWARGS = frozenset(
    {"threads", "search_all", "signatures", "exclude_signatures", "timeout", "plot_directory"}
)


@dataclass(frozen=True)
class ScanOptions:
    """Everything that controls one scan.

    Attributes:
        signature: Run signature scanning explicitly (``-B``).
        extract: Extract identified data (``-e``).
        carve: Carve identified and unidentified data to ``.raw`` files (``-z``).
        matryoshka_depth: Maximum recursion depth for extracted files; 0 disables recursion.
        directory: Extraction directory; None uses binwalk v3's default ``./extractions``.
        entropy: Run entropy analysis (``-E``).
        use_zlib: Use the zlib compression ratio for entropy (``-F``).
        save_plot: Save the entropy graph as ``<name>.png`` (``-J``).
        show_legend: Draw signature markers on the entropy graph (disabled by ``-Q``).
        trigger_high: Rising-edge entropy threshold (``-H``).
        trigger_low: Falling-edge entropy threshold (``-L``).
        block_size: Entropy block size in bytes (``-K``); None uses the v2 default.
        quiet: Accepted for compatibility; output is always captured.
        verbose: Mark every entropy block for display instead of only edges.
        include: Regexes a result description must match (``-y``).
        exclude: Regexes that remove matching results (``-x``).
        signatures: binwalk v3 signature names to scan for exclusively (``--include``).
        exclude_signatures: binwalk v3 signature names to skip (``--exclude``).
        search_all: Search every offset for every signature (``--search-all``).
        threads: Worker thread count for binwalk v3.
        timeout: Seconds before the binwalk process is killed; None waits indefinitely.
        plot_directory: Directory for saved entropy plots; None uses the working directory.
    """

    signature: bool = False
    extract: bool = False
    carve: bool = False
    matryoshka_depth: int = 0
    directory: str | None = None
    entropy: bool = False
    use_zlib: bool = False
    save_plot: bool = False
    show_legend: bool = True
    trigger_high: float = 0.95
    trigger_low: float = 0.85
    block_size: int | None = None
    quiet: bool = True
    verbose: bool = False
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    signatures: tuple[str, ...] = ()
    exclude_signatures: tuple[str, ...] = ()
    search_all: bool = False
    threads: int | None = None
    timeout: float | None = DEFAULT_TIMEOUT
    plot_directory: str | None = None

    @property
    def runs_signature(self) -> bool:
        """Report whether the binwalk v3 binary needs to run.

        Signature scanning runs when requested, when extraction or carving needs it, or when
        no entropy-only scan was asked for, matching binwalk v2's default.

        Returns:
            True if the binary must be run.
        """
        return self.signature or self.extract or self.carve or not self.entropy


@dataclass(frozen=True)
class ParsedRequest:
    """Files and options parsed from a scan call.

    Attributes:
        files: Target file paths in the order given.
        options: Scan options.
    """

    files: tuple[str, ...]
    options: ScanOptions = field(default_factory=ScanOptions)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        detail = f"Invalid usage: {message}"
        raise ModuleException(detail)


def _build_parser() -> _Parser:
    parser = _Parser(add_help=False, allow_abbrev=False, prog="binwalk")
    converters = {"int": int, "float": float, "str": str}
    for option in _V2_OPTIONS:
        flags = [f"-{option.short}"] if option.short else []
        flags.append(f"--{option.long}")
        dest = option.long.replace("-", "_")
        if option.takes is None:
            parser.add_argument(*flags, dest=dest, action="store_true")
        elif option.repeat:
            parser.add_argument(*flags, dest=dest, action="append", type=converters[option.takes])
        else:
            parser.add_argument(*flags, dest=dest, type=converters[option.takes])
    return parser


def _sequence_items(value: object) -> tuple[object, ...] | None:
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(cast("Iterable[object]", value))
    return None


def path_text(value: object) -> str:
    """Convert a path-like or plain argument to text.

    Args:
        value: A str, bytes, os.PathLike or any other object.

    Returns:
        The path as a string; other objects are converted with ``str()``.
    """
    if isinstance(value, os.PathLike):
        value = os.fspath(cast("os.PathLike[str] | os.PathLike[bytes]", value))
    if isinstance(value, bytes):
        return os.fsdecode(value)
    return str(value)


def _kwarg_to_argv(key: str, value: object) -> list[str]:
    flag = f"-{key}" if len(key) == 1 else f"--{key.replace('_', '-')}"
    if value is None or value is False:
        return []
    if value is True:
        return [flag]
    items = _sequence_items(value)
    argv: list[str] = []
    for item in items if items is not None else (value,):
        argv.extend((flag, path_text(item)))
    return argv


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part for part in value.split(",") if part)
    items = _sequence_items(value)
    if items is not None:
        return tuple(str(item) for item in items)
    message = f"{name} must be a string or a sequence of strings"
    raise ModuleException(message)


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        message = f"{name} must be an integer"
        raise ModuleException(message)
    try:
        number = int(value)
    except ValueError as exc:
        message = f"{name} must be an integer"
        raise ModuleException(message) from exc
    if number < 1:
        message = f"{name} must be at least 1"
        raise ModuleException(message)
    return number


def _optional_float(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        message = f"{name} must be a number"
        raise ModuleException(message)
    try:
        number = float(value)
    except ValueError as exc:
        message = f"{name} must be a number"
        raise ModuleException(message) from exc
    if number <= 0:
        message = f"{name} must be positive"
        raise ModuleException(message)
    return number


def _check_regex(pattern: str) -> str:
    try:
        re.compile(pattern)
    except re.error as exc:
        message = f"Invalid include/exclude regex {pattern!r}: {exc}"
        raise ModuleException(message) from exc
    return pattern


def _validate_regexes(patterns: Sequence[str]) -> tuple[str, ...]:
    return tuple(_check_regex(pattern) for pattern in patterns)


def _matryoshka_kwarg(value: object) -> list[str]:
    if value is True:
        return ["--matryoshka"]
    if value is None or value is False:
        return []
    if isinstance(value, int):
        return ["--matryoshka", "--depth", str(value)] if value > 0 else []
    message = "matryoshka must be a bool or a positive int depth"
    raise ModuleException(message)


def _split_kwargs(kwargs: Mapping[str, object]) -> tuple[list[str], dict[str, object]]:
    argv: list[str] = []
    extras: dict[str, object] = {}
    for key, value in kwargs.items():
        normalized = key.lstrip("-")
        long_name = normalized.replace("_", "-")
        if normalized in _BINWALK3_KWARGS:
            extras[normalized] = value
        elif long_name == "matryoshka":
            argv.extend(_matryoshka_kwarg(value))
        elif long_name in _V2_BY_LONG or (len(normalized) == 1 and normalized in _V2_BY_SHORT):
            argv.extend(_kwarg_to_argv(normalized, value))
        elif value is not None and value is not False:
            warnings.warn(
                f"Ignoring unknown option {key!r}",
                UnknownOptionWarning,
                stacklevel=4,
            )
    return argv, extras


def _warn_unsupported(namespace: argparse.Namespace) -> None:
    for option in _V2_OPTIONS:
        if option.supported:
            continue
        value: object = getattr(namespace, option.long.replace("-", "_"), None)
        if value not in (None, False):
            warnings.warn(
                f"binwalk v2 option --{option.long} has no binwalk v3 equivalent and was ignored",
                UnsupportedOptionWarning,
                stacklevel=4,
            )


def _namespace_value(namespace: argparse.Namespace, name: str) -> object:
    value: object = getattr(namespace, name, None)
    return value


def _namespace_strings(namespace: argparse.Namespace, name: str) -> tuple[str, ...]:
    items = _sequence_items(_namespace_value(namespace, name))
    return tuple(str(item) for item in items) if items is not None else ()


def _flag(namespace: argparse.Namespace, name: str) -> bool:
    return _namespace_value(namespace, name) is True


def parse_request(arguments: Sequence[object], kwargs: Mapping[str, object]) -> ParsedRequest:
    """Parse positional arguments and keyword options the way binwalk v2 does.

    Positional strings that start with ``-`` are command line options; everything else is a
    target file. Keyword arguments named after v2 long options (``extract=True``,
    ``directory="out"``) or short options (``e=True``) are converted to command line form.
    binwalk3 additions (``threads``, ``search_all``, ``signatures``, ``exclude_signatures``,
    ``timeout``, ``plot_directory``) are read directly. Raises ModuleException if an option
    value is invalid.

    Args:
        arguments: Positional arguments: file paths and v2 command line options.
        kwargs: Keyword options.

    Returns:
        The parsed files and options.
    """
    argv: list[str] = [path_text(item) for item in arguments]
    kwarg_argv, extras = _split_kwargs(kwargs)
    namespace, unknown = _build_parser().parse_known_args([*argv, *kwarg_argv])
    _warn_unsupported(namespace)

    files: list[str] = []
    for item in unknown:
        if item.startswith("-") and not Path(item).exists():
            warnings.warn(f"Ignoring unknown option {item!r}", UnknownOptionWarning, stacklevel=3)
        else:
            files.append(item)

    depth_value = _namespace_value(namespace, "depth")
    if isinstance(depth_value, int) and depth_value > 0:
        matryoshka_depth = depth_value
    elif _flag(namespace, "matryoshka"):
        matryoshka_depth = V2_MATRYOSHKA_DEPTH
    else:
        matryoshka_depth = 0

    directory = _namespace_value(namespace, "directory")
    high = _namespace_value(namespace, "high")
    low = _namespace_value(namespace, "low")
    block = _namespace_value(namespace, "block")
    timeout = extras.get("timeout", DEFAULT_TIMEOUT)
    plot_directory = extras.get("plot_directory")

    options = ScanOptions(
        signature=_flag(namespace, "signature"),
        extract=_flag(namespace, "extract"),
        carve=_flag(namespace, "carve"),
        matryoshka_depth=matryoshka_depth,
        directory=directory if isinstance(directory, str) and directory else None,
        entropy=_flag(namespace, "entropy"),
        use_zlib=_flag(namespace, "fast"),
        save_plot=_flag(namespace, "save"),
        show_legend=not _flag(namespace, "nlegend"),
        trigger_high=high if isinstance(high, float) else 0.95,
        trigger_low=low if isinstance(low, float) else 0.85,
        block_size=block if isinstance(block, int) and block > 0 else None,
        quiet=_flag(namespace, "quiet") or not _flag(namespace, "verbose"),
        verbose=_flag(namespace, "verbose"),
        include=_validate_regexes(_namespace_strings(namespace, "include")),
        exclude=_validate_regexes(_namespace_strings(namespace, "exclude")),
        signatures=_string_tuple(extras.get("signatures"), "signatures"),
        exclude_signatures=_string_tuple(extras.get("exclude_signatures"), "exclude_signatures"),
        search_all=extras.get("search_all") is True,
        threads=_optional_int(extras.get("threads"), "threads"),
        timeout=_optional_float(timeout, "timeout"),
        plot_directory=path_text(plot_directory) if plot_directory is not None else None,
    )
    return ParsedRequest(files=tuple(files), options=options)
