"""Run the binwalk v3 executable and convert its results.

``BinwalkV3Backend``, ``V3ScanResult``, ``V3ModuleResult`` and ``get_backend`` are public
and keep every field they had in binwalk3 3.1.3.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from binwalk import _entropy
from binwalk._binary import BinaryInfo, Discovery, discover_binary, probe_binary, subprocess_flags
from binwalk._errors import ModuleException
from binwalk._options import ScanOptions, parse_request
from binwalk._v3_log import LogAnalysis, LogExtraction, parse_analyses

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

_LOG_LINE_RE = re.compile(r"^\[\S+\s+(ERROR|WARN)\s+[^\]]*\]\s*(.*)$")
_STDERR_TAIL_LINES = 20
_HASH_CHUNK = 1 << 20
_FALLBACK_BINARY_NAME = "binwalk3"


@dataclass(frozen=True)
class V3Extraction:
    """Extraction outcome for one signature match.

    Attributes:
        success: Whether the extractor reported success.
        extractor: Extractor name, for example ``7z`` or ``gzip``.
        output_directory: Directory the extractor wrote into.
        size: Number of bytes the extractor consumed, if known.
        files: Every file found under ``output_directory`` after the scan.
        do_not_recurse: True if binwalk does not scan these files recursively.
    """

    success: bool
    extractor: str
    output_directory: str
    size: int | None = None
    files: tuple[str, ...] = ()
    do_not_recurse: bool = False


@dataclass
class V3ScanResult:
    """One signature match or entropy block.

    The first six fields are the binwalk3 3.1.3 fields. ``module`` holds the signature name
    (for example ``zip``) for signature results and ``entropy`` for entropy blocks.

    Attributes:
        offset: Byte offset in ``file``.
        description: Description reported by binwalk v3, or the entropy description.
        size: Size of the matched data in bytes.
        entropy: Entropy on the 0..1 scale, for entropy results.
        file: File the result belongs to. Results from the scanned file use the path you
            passed in; results from extracted files use their path on disk.
        module: Signature name, or ``entropy``.
        name: Signature name (None for entropy results).
        id: binwalk v3 result id.
        confidence: binwalk v3 confidence value (0-255).
        extraction: Extraction outcome when extraction was requested.
        carved: Path of the carved ``.raw`` file when carving was requested.
        depth: Recursion depth: 0 for the scanned file, 1 for files extracted from it, and so on.
        display: Whether binwalk v2 would display the result.
        entropy_bits: Entropy in bits per byte (0..8), for entropy results.
    """

    offset: int
    description: str
    size: int | None = None
    entropy: float | None = None
    file: str | None = None
    module: str | None = None
    name: str | None = None
    id: str | None = None
    confidence: int | None = None
    extraction: V3Extraction | None = None
    carved: str | None = None
    depth: int = 0
    display: bool = True
    entropy_bits: float | None = None

    def __repr__(self) -> str:
        """Return a short representation with offset, description, size and entropy.

        Returns:
            The representation string.
        """
        parts = [f"offset={self.offset:#x}", f"description='{self.description}'"]
        if self.size is not None:
            parts.append(f"size={self.size}")
        if self.entropy is not None:
            parts.append(f"entropy={self.entropy:.2f}")
        return f"<V3ScanResult: {', '.join(parts)}>"


@dataclass
class V3ModuleResult:
    """Everything found in one scanned file.

    Attributes:
        results: Signature results, then entropy results.
        errors: Problems that stopped all or part of the scan.
        file: The path that was scanned, as passed in.
        warnings: Non-fatal messages logged by binwalk, such as extractor failures.
        extraction_directory: Directory used for extraction, when extracting or carving.
        plot: Path of the saved entropy plot, if one was saved.
    """

    results: list[V3ScanResult] = field(default_factory=list[V3ScanResult])
    errors: list[str] = field(default_factory=list[str])
    file: str | None = None
    warnings: list[str] = field(default_factory=list[str])
    extraction_directory: str | None = None
    plot: str | None = None

    def __iter__(self) -> Iterator[V3ScanResult]:
        """Iterate over results.

        Returns:
            An iterator over ``results``.
        """
        return iter(self.results)

    def __len__(self) -> int:
        """Return the number of results.

        Returns:
            ``len(results)``.
        """
        return len(self.results)


@dataclass
class _RunOutcome:
    analyses: list[LogAnalysis] = field(default_factory=list[LogAnalysis])
    errors: list[str] = field(default_factory=list[str])
    warnings: list[str] = field(default_factory=list[str])


def _same_volume(first: Path, second: Path) -> bool:
    if os.name != "nt":
        return True
    return os.path.splitdrive(str(first))[0].lower() == os.path.splitdrive(str(second))[0].lower()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_content(first: Path, second: Path) -> bool:
    try:
        if first.samefile(second):
            return True
        if first.stat().st_size != second.stat().st_size:
            return False
        return _file_digest(first) == _file_digest(second)
    except OSError:
        return False


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _is_under(path: str, directory: str) -> bool:
    normalized_path = _norm(path)
    normalized_dir = _norm(directory)
    return normalized_path.startswith(normalized_dir.rstrip(os.sep) + os.sep)


def _list_files(directory: str) -> tuple[str, ...]:
    root = Path(directory)
    if not root.is_dir():
        return ()
    return tuple(sorted(str(path) for path in root.rglob("*") if path.is_file()))


def _depths(analyses: Sequence[LogAnalysis]) -> list[int]:
    depths = [0] * len(analyses)
    for index, analysis in enumerate(analyses[1:], start=1):
        best_parent: int | None = None
        best_length = -1
        for parent_index in range(index):
            for item in analyses[parent_index].extractions.values():
                length = len(_norm(item.output_directory))
                if length > best_length and _is_under(analysis.file_path, item.output_directory):
                    best_parent = parent_index
                    best_length = length
        if best_parent is not None:
            depths[index] = depths[best_parent] + 1
    return depths


def _stderr_messages(stderr: str) -> list[str]:
    messages: list[str] = []
    for line in stderr.splitlines():
        match = _LOG_LINE_RE.match(line.strip())
        if match is not None and match.group(2) not in messages:
            messages.append(match.group(2))
    return messages


def _stderr_tail(stderr: str) -> str:
    lines = [line for line in stderr.splitlines() if line.strip()]
    return "\n".join(lines[-_STDERR_TAIL_LINES:])


def _description_filter(
    options: ScanOptions,
) -> tuple[list[re.Pattern[str]], list[re.Pattern[str]]]:
    return [re.compile(pattern) for pattern in options.include], [
        re.compile(pattern) for pattern in options.exclude
    ]


def _keep_description(
    description: str, includes: Sequence[re.Pattern[str]], excludes: Sequence[re.Pattern[str]]
) -> bool:
    text = description.lower()
    if includes and not any(pattern.search(text) for pattern in includes):
        return False
    return not any(pattern.search(text) for pattern in excludes)


class BinwalkV3Backend:
    """Runs a binwalk v3 executable.

    Attributes:
        binary_path: Path of the executable that will be run.
        available: True if the executable is a working binwalk 3.x.
        info: Version and supported options of the executable, if available.
        discovery: Candidates checked when no explicit path was given.
    """

    binary_path: str
    available: bool
    info: BinaryInfo | None
    discovery: Discovery

    def __init__(self, binary_path: str | None = None) -> None:
        """Locate and validate the binwalk v3 executable.

        Args:
            binary_path: Executable to use. If None, the ``BINWALK3_BINARY`` environment
                variable, the bundled executable and PATH are searched in that order.
        """
        if binary_path is None:
            self.discovery = discover_binary()
            self.info = self.discovery.binary
        else:
            self.info = probe_binary(binary_path)
            self.discovery = Discovery(
                self.info,
                [f"explicit {binary_path}: {'ok' if self.info else 'not a working binwalk 3.x'}"],
            )
        self.binary_path = self.info.path if self.info else (binary_path or _FALLBACK_BINARY_NAME)
        self.available = self.info is not None

    def unavailable_reason(self) -> str:
        """Describe why no executable is available, listing every candidate checked.

        Returns:
            A message suitable for an exception or log.
        """
        tried = "; ".join(self.discovery.tried) or "nothing"
        return f"Binwalk v3 binary not available (checked: {tried})"

    def _require_info(self) -> BinaryInfo:
        if self.info is None:
            raise RuntimeError(self.unavailable_reason())
        return self.info

    def scan(self, *files: str, **kwargs: object) -> list[V3ModuleResult]:
        """Scan files and return one V3ModuleResult per file.

        Accepts the keyword options of ``binwalk.scan``. Problems with individual files are
        reported in that file's ``errors`` instead of being raised. ``scan_files`` exceptions
        (RuntimeError, ModuleException) propagate.

        Args:
            *files: Paths to scan.
            **kwargs: Scan options, for example ``extract=True`` or ``entropy=True``.

        Returns:
            One result object per file, in the order given.

        Raises:
            ValueError: If no files were given.
        """
        request = parse_request(files, kwargs)
        if not request.files:
            message = "No files specified for scanning"
            raise ValueError(message)
        return self.scan_files(request.files, request.options)

    def scan_files(self, files: Sequence[str], options: ScanOptions) -> list[V3ModuleResult]:
        """Scan files with already-parsed options.

        A ModuleException is raised if the executable lacks an option the scan needs.

        Args:
            files: Paths to scan.
            options: Scan options.

        Returns:
            One result object per file, in the order given.

        Raises:
            RuntimeError: If no binwalk v3 executable is available and signature scanning is needed.
        """
        if options.runs_signature:
            if self.info is None:
                raise RuntimeError(self.unavailable_reason())
            self._check_capabilities(self.info, options)
        return [self._scan_one(path, options) for path in files]

    def scan_bytes(self, data: bytes, name: str = "stdin", **kwargs: object) -> V3ModuleResult:
        """Scan in-memory data.

        Without extraction or carving the data is piped to ``binwalk --stdin`` when the
        executable supports it. Otherwise it is written to a temporary file named ``name``.
        A ModuleException is raised if an option is invalid or unsupported.

        Args:
            data: Bytes to scan.
            name: Name used in results and for extraction output.
            **kwargs: Scan options, as for ``scan``.

        Returns:
            Results with ``file`` set to ``name``.

        Raises:
            RuntimeError: If no binwalk v3 executable is available and signature scanning is needed.
        """
        options = parse_request((), kwargs).options
        info: BinaryInfo | None = None
        if options.runs_signature:
            if self.info is None:
                raise RuntimeError(self.unavailable_reason())
            info = self.info
            self._check_capabilities(info, options)
        result = V3ModuleResult(file=name)
        if info is not None:
            if not options.extract and not options.carve and info.supports("--stdin"):
                outcome = self._run(info, ["--stdin"], options, stdin=data)
                self._merge(result, outcome, options, display_path=name, base_path=None)
            else:
                with tempfile.TemporaryDirectory(prefix="binwalk3-") as scratch:
                    target = Path(scratch) / Path(name).name
                    target.write_bytes(data)
                    self._signature_scan(result, target, name, options)
        if options.entropy:
            self._entropy_scan(result, data, name, options)
        return result

    def _check_capabilities(self, info: BinaryInfo, options: ScanOptions) -> None:
        required: list[str] = ["--log", "--quiet"]
        if options.extract:
            required.extend(("--extract", "--directory"))
        if options.carve:
            required.extend(("--carve", "--directory"))
        if options.matryoshka_depth:
            required.append("--matryoshka")
        if options.signatures:
            required.append("--include")
        if options.exclude_signatures:
            required.append("--exclude")
        if options.search_all:
            required.append("--search-all")
        if options.threads:
            required.append("--threads")
        missing = [option for option in dict.fromkeys(required) if not info.supports(option)]
        if missing:
            unsupported = ", ".join(missing)
            message = f"binwalk {info.version_string} at {info.path} does not support {unsupported}"
            raise ModuleException(message)

    def _scan_one(self, path: str, options: ScanOptions) -> V3ModuleResult:
        result = V3ModuleResult(file=path)
        target = Path(path)
        if not target.is_file():
            result.errors.append(f"File not found: {path}")
            return result
        try:
            if options.runs_signature:
                self._signature_scan(result, target, path, options)
            if options.entropy:
                self._entropy_scan(result, target.read_bytes(), path, options)
        except OSError as exc:
            result.errors.append(f"Error scanning {path}: {exc}")
        return result

    def _prepare_extraction(self, target: Path, options: ScanOptions) -> Path:
        directory = Path(options.directory or "extractions").resolve()
        link = directory / target.name
        resolved_target = target.resolve()
        if link.exists():
            if not _same_content(link, resolved_target):
                message = (
                    f"{link} already exists and is a different file; binwalk v3 would analyze it "
                    f"instead of {target}. Use another directory or remove it."
                )
                raise ModuleException(message)
        elif not _same_volume(resolved_target, directory):
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved_target, link)
        return directory

    def _signature_scan(
        self, result: V3ModuleResult, target: Path, display_path: str, options: ScanOptions
    ) -> None:
        info = self._require_info()
        arguments: list[str] = []
        base_path = str(target.resolve())
        if options.extract or options.carve:
            directory = self._prepare_extraction(target, options)
            result.extraction_directory = str(directory)
            arguments.extend(("--directory", str(directory)))
            base_path = str(directory / target.name)
        arguments.append(str(target.resolve()))
        outcome = self._run(info, arguments, options)
        self._merge(result, outcome, options, display_path=display_path, base_path=base_path)

    def _command(self, info: BinaryInfo, options: ScanOptions, log_path: str) -> list[str]:
        command = [info.path, "--quiet", "--log", log_path]
        if options.extract:
            command.append("--extract")
        if options.carve:
            command.append("--carve")
        if options.matryoshka_depth and (options.extract or options.carve):
            command.append("--matryoshka")
        if options.search_all:
            command.append("--search-all")
        if options.threads:
            command.extend(("--threads", str(options.threads)))
        if options.signatures:
            command.append(f"--include={','.join(options.signatures)}")
        if options.exclude_signatures:
            command.append(f"--exclude={','.join(options.exclude_signatures)}")
        return command

    def _run(
        self,
        info: BinaryInfo,
        arguments: Sequence[str],
        options: ScanOptions,
        stdin: bytes | None = None,
    ) -> _RunOutcome:
        outcome = _RunOutcome()
        with tempfile.TemporaryDirectory(prefix="binwalk3-") as scratch:
            log_path = str(Path(scratch) / "results.json")
            command = [*self._command(info, options, log_path), *arguments]
            try:
                completed = subprocess.run(
                    command,
                    input=stdin,
                    capture_output=True,
                    timeout=options.timeout,
                    check=False,
                    creationflags=subprocess_flags(),
                )
            except subprocess.TimeoutExpired:
                outcome.errors.append(f"binwalk timed out after {options.timeout} seconds")
                return outcome
            except OSError as exc:
                outcome.errors.append(f"Failed to run {info.path}: {exc}")
                return outcome
            stderr = completed.stderr.decode("utf-8", errors="replace")
            outcome.warnings.extend(_stderr_messages(stderr))
            if completed.returncode != 0:
                tail = _stderr_tail(stderr)
                outcome.errors.append(
                    f"binwalk exited with code {completed.returncode}"
                    + (f": {tail}" if tail else "")
                )
            log_file = Path(log_path)
            if not log_file.is_file():
                if completed.returncode == 0:
                    outcome.errors.append("binwalk did not write a results log")
                return outcome
            try:
                outcome.analyses = parse_analyses(
                    log_file.read_text(encoding="utf-8", errors="replace")
                )
            except ValueError as exc:
                outcome.errors.append(f"Failed to parse results: {exc}")
        return outcome

    def _merge(
        self,
        result: V3ModuleResult,
        outcome: _RunOutcome,
        options: ScanOptions,
        *,
        display_path: str,
        base_path: str | None,
    ) -> None:
        result.errors.extend(outcome.errors)
        result.warnings.extend(outcome.warnings)
        includes, excludes = _description_filter(options)
        depths = _depths(outcome.analyses)
        max_depth = options.matryoshka_depth if (options.extract or options.carve) else 0
        for index, analysis in enumerate(outcome.analyses):
            depth = depths[index]
            if depth > max_depth:
                continue
            is_base = index == 0 or (
                base_path is not None and _norm(analysis.file_path) == _norm(base_path)
            )
            file_label = display_path if is_base else analysis.file_path
            for signature in analysis.signatures:
                if not _keep_description(signature.description, includes, excludes):
                    continue
                extraction = analysis.extractions.get(signature.id)
                carved_path = f"{analysis.file_path}_{signature.offset}_{signature.name}.raw"
                result.results.append(
                    V3ScanResult(
                        offset=signature.offset,
                        description=signature.description,
                        size=signature.size,
                        file=file_label,
                        module=signature.name,
                        name=signature.name,
                        id=signature.id,
                        confidence=signature.confidence,
                        extraction=_convert_extraction(extraction)
                        if extraction is not None
                        else None,
                        carved=carved_path
                        if options.carve and Path(carved_path).is_file()
                        else None,
                        depth=depth,
                    )
                )

    def _entropy_scan(
        self, result: V3ModuleResult, data: bytes, display_path: str, options: ScanOptions
    ) -> None:
        settings = _entropy.EntropySettings(
            block_size=options.block_size,
            trigger_high=options.trigger_high,
            trigger_low=options.trigger_low,
            use_zlib=options.use_zlib,
            verbose=options.verbose,
        )
        blocks = _entropy.analyze(data, settings)
        result.results.extend(
            V3ScanResult(
                offset=block.offset,
                description=block.description,
                size=block.size,
                entropy=block.entropy,
                file=display_path,
                module="entropy",
                display=block.display,
                entropy_bits=block.entropy_bits,
            )
            for block in blocks
        )
        if options.save_plot:
            markers = (
                [
                    (item.offset, item.description)
                    for item in result.results
                    if item.module != "entropy" and item.depth == 0
                ]
                if options.show_legend
                else []
            )
            output = _entropy.plot_path(display_path, options.plot_directory)
            result.plot = str(_entropy.save_plot(blocks, output, markers))


def _convert_extraction(extraction: LogExtraction) -> V3Extraction:
    return V3Extraction(
        success=extraction.success,
        extractor=extraction.extractor,
        output_directory=extraction.output_directory,
        size=extraction.size,
        files=_list_files(extraction.output_directory),
        do_not_recurse=extraction.do_not_recurse,
    )


class _SharedBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: BinwalkV3Backend | None = None

    def get(self) -> BinwalkV3Backend:
        with self._lock:
            if self._instance is None:
                self._instance = BinwalkV3Backend()
            return self._instance

    def reset(self) -> None:
        with self._lock:
            self._instance = None


_shared = _SharedBackend()


def get_backend() -> BinwalkV3Backend:
    """Return the shared backend, creating it on first use.

    Returns:
        The process-wide BinwalkV3Backend.
    """
    return _shared.get()


def reset_backend() -> None:
    """Discard the shared backend so the next ``get_backend`` call searches again.

    Use this after changing ``BINWALK3_BINARY`` or installing a different binwalk.
    """
    _shared.reset()
