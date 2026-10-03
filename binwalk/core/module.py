"""binwalk v2 compatible result classes backed by binwalk v3.

Results are returned one Module per scanned file (the binwalk3 3.1.3 shape). Each signature
Module also carries the binwalk v2 attributes: ``name``, ``extractor.output`` and
``Result.file.path``. Entropy results are returned in separate Modules named ``Entropy``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from binwalk._errors import ModuleException
from binwalk._options import ParsedRequest, parse_request
from binwalk._v3_backend import (
    BinwalkV3Backend,
    V3Extraction,
    V3ModuleResult,
    V3ScanResult,
    get_backend,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence
    from types import TracebackType

    from typing_extensions import Self

SIGNATURE = "Signature"
ENTROPY = "Entropy"


class FilePath(str):
    """A file path string with the binwalk v2 ``BlockFile`` attributes ``path`` and ``name``.

    It compares equal to the path you passed in, as in binwalk3 3.1.3, while
    ``result.file.path`` gives the absolute path, as in binwalk v2.
    """

    __slots__ = ()

    @property
    def path(self) -> str:
        """Return the absolute path.

        Returns:
            The resolved absolute path.
        """
        return str(Path(str(self)).resolve())

    @property
    def name(self) -> str:
        """Return the path as originally given.

        Returns:
            The path string.
        """
        return str(self)

    @property
    def basename(self) -> str:
        """Return the final path component.

        Returns:
            The file name without directories.
        """
        return Path(str(self)).name

    @property
    def size(self) -> int:
        """Return the file size in bytes, or 0 if the file cannot be read.

        Returns:
            The size in bytes.
        """
        try:
            return Path(str(self)).stat().st_size
        except OSError:
            return 0


class Result:
    """One scan result.

    Attributes:
        offset: Byte offset in ``file``.
        description: Result description.
        size: Size of the matched data, if known.
        entropy: Entropy on the 0..1 scale for entropy results.
        file: The file this result belongs to; also exposes ``.path`` and ``.name``.
        module: Signature name (for example ``zip``) or ``entropy``, as in binwalk3 3.1.3.
        name: Signature name.
        id: binwalk v3 result id.
        confidence: binwalk v3 confidence (0-255).
        extraction: Extraction outcome, when extraction was requested.
        carved: Path of the carved ``.raw`` file, when carving was requested.
        depth: Recursion depth of ``file`` (0 for the scanned file).
        valid: Always True; invalid results are never returned.
        display: Whether binwalk v2 would display the result.
        extract: Whether extraction applied to this result.
        plot: Whether the result belongs on an entropy plot.
        entropy_bits: Entropy in bits per byte (0..8) for entropy results.
    """

    offset: int
    description: str
    size: int | None
    entropy: float | None
    file: FilePath | None
    module: str | None
    name: str | None
    id: str | None
    confidence: int | None
    extraction: V3Extraction | None
    carved: str | None
    depth: int
    valid: bool
    display: bool
    extract: bool
    plot: bool
    entropy_bits: float | None

    def __init__(
        self,
        offset: int = 0,
        description: str = "",
        size: int | None = None,
        entropy: float | None = None,
        file: str | None = None,
        module: str | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        confidence: int | None = None,
        extraction: V3Extraction | None = None,
        carved: str | None = None,
        depth: int = 0,
        valid: bool = True,
        display: bool = True,
        extract: bool = True,
        plot: bool = True,
        entropy_bits: float | None = None,
        **extra: object,
    ) -> None:
        """Create a result. Unknown keyword arguments become attributes, as in binwalk v2.

        Args:
            offset: Byte offset.
            description: Description.
            size: Size of the matched data.
            entropy: Entropy on the 0..1 scale.
            file: File path.
            module: Signature name or ``entropy``.
            name: Signature name.
            id: binwalk v3 result id.
            confidence: binwalk v3 confidence.
            extraction: Extraction outcome.
            carved: Carved file path.
            depth: Recursion depth.
            valid: Validity flag.
            display: Display flag.
            extract: Extraction flag.
            plot: Plot flag.
            entropy_bits: Entropy in bits per byte.
            **extra: Additional attributes.
        """
        self.offset = offset
        self.description = description
        self.size = size
        self.entropy = entropy
        self.file = FilePath(file) if file is not None else None
        self.module = module
        self.name = name
        self.id = id
        self.confidence = confidence
        self.extraction = extraction
        self.carved = carved
        self.depth = depth
        self.valid = valid
        self.display = display
        self.extract = extract
        self.plot = plot
        self.entropy_bits = entropy_bits
        for key, value in extra.items():
            setattr(self, key, value)

    @classmethod
    def from_v3(cls, item: V3ScanResult) -> Result:
        """Build a Result from a backend result.

        Args:
            item: Backend result.

        Returns:
            The equivalent Result.
        """
        return cls(
            offset=item.offset,
            description=item.description,
            size=item.size,
            entropy=item.entropy,
            file=item.file,
            module=item.module,
            name=item.name,
            id=item.id,
            confidence=item.confidence,
            extraction=item.extraction,
            carved=item.carved,
            depth=item.depth,
            display=item.display,
            extract=item.extraction is not None,
            plot=item.module == "entropy",
            entropy_bits=item.entropy_bits,
        )

    def __repr__(self) -> str:
        """Return a short representation with offset and description.

        Returns:
            The representation string.
        """
        return f"<Result: offset={self.offset:#x}, description='{self.description}'>"


@dataclass
class ExtractDetails:
    """Files produced by one extraction, as in binwalk v2.

    Attributes:
        files: Extracted file paths.
        command: Extractor that produced them.
    """

    files: list[str] = field(default_factory=list[str])
    command: str = ""


@dataclass
class ExtractInfo:
    """Extraction output for one file, as in binwalk v2's ``extractor.output[path]``.

    Attributes:
        carved: Carved file path by offset.
        extracted: Extraction details by offset.
        directory: The ``<name>.extracted`` directory.
    """

    carved: dict[int, str] = field(default_factory=dict[int, str])
    extracted: dict[int, ExtractDetails] = field(default_factory=dict[int, ExtractDetails])
    directory: str | None = None


@dataclass
class Extractor:
    """binwalk v2's ``module.extractor`` view of extraction output.

    Attributes:
        enabled: True if extraction or carving ran.
        directory: Base extraction directory.
        output: ExtractInfo keyed by the absolute path of each file that had results.
    """

    enabled: bool = False
    directory: str | None = None
    output: dict[str, ExtractInfo] = field(default_factory=dict[str, ExtractInfo])

    @classmethod
    def from_results(cls, results: Sequence[Result], directory: str | None) -> Extractor:
        """Collect extraction and carving output from results.

        Args:
            results: Signature results.
            directory: Base extraction directory, or None if nothing was extracted.

        Returns:
            The populated Extractor.
        """
        extractor = cls(enabled=directory is not None, directory=directory)
        for result in results:
            if result.file is None or (result.extraction is None and result.carved is None):
                continue
            info = extractor.output.setdefault(result.file.path, ExtractInfo())
            if result.carved is not None:
                info.carved[result.offset] = result.carved
            if result.extraction is not None:
                info.extracted[result.offset] = ExtractDetails(
                    files=list(result.extraction.files),
                    command=result.extraction.extractor,
                )
                info.directory = str(Path(result.extraction.output_directory).parent)
        return extractor


class Module:
    """Results for one scanned file.

    Attributes:
        file: The path that was scanned, as passed in.
        name: ``Signature`` or ``Entropy``.
        results: Results in file order.
        errors: Problems that stopped all or part of the scan.
        warnings: Non-fatal messages logged by binwalk.
        extractor: Extraction output (signature modules).
        plot: Saved entropy plot path (entropy modules).
        enabled: Always True for returned modules.
        status: None; kept for binwalk v2 attribute compatibility.
    """

    file: str
    name: str
    results: list[Result]
    errors: list[str]
    warnings: list[str]
    extractor: Extractor
    plot: str | None
    enabled: bool
    status: object

    def __init__(self, file_path: str, name: str = SIGNATURE) -> None:
        """Create an empty module.

        Args:
            file_path: The scanned file.
            name: ``Signature`` or ``Entropy``.
        """
        self.file = file_path
        self.name = name
        self.results = []
        self.errors = []
        self.warnings = []
        self.extractor = Extractor()
        self.plot = None
        self.enabled = True
        self.status = None

    def __iter__(self) -> Iterator[Result]:
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

    def __repr__(self) -> str:
        """Return a short representation with module name, file and result count.

        Returns:
            The representation string.
        """
        counts = f"results={len(self.results)}, errors={len(self.errors)}"
        return f"<Module {self.name}: file='{self.file}', {counts}>"


def build_modules(
    file_path: str, scanned: V3ModuleResult, *, signature: bool, entropy: bool
) -> list[Module]:
    """Split one backend result into a Signature module and an Entropy module.

    Args:
        file_path: The scanned file, as passed in.
        scanned: Backend result for that file.
        signature: Whether signature scanning ran.
        entropy: Whether entropy analysis ran.

    Returns:
        The Signature module (if signature scanning ran or there were no entropy results)
        followed by the Entropy module (if entropy analysis ran).
    """
    modules: list[Module] = []
    if signature or not entropy:
        module = Module(file_path, SIGNATURE)
        module.results = [
            Result.from_v3(item) for item in scanned.results if item.module != "entropy"
        ]
        module.errors = list(scanned.errors)
        module.warnings = list(scanned.warnings)
        module.extractor = Extractor.from_results(module.results, scanned.extraction_directory)
        modules.append(module)
    if entropy:
        module = Module(file_path, ENTROPY)
        module.results = [
            Result.from_v3(item) for item in scanned.results if item.module == "entropy"
        ]
        module.errors = [] if modules else list(scanned.errors)
        module.plot = scanned.plot
        modules.append(module)
    return modules


class Modules:
    """Run scans with binwalk v2 or binwalk3 3.1.3 calling conventions.

    Both styles work::

        Modules().execute("fw.bin", extract=True)
        with Modules("fw.bin", "--signature", "-e") as modules:
            results = modules.execute()

    Attributes:
        backend: The backend that runs binwalk v3.
        results: Modules returned by the most recent ``execute`` call.
    """

    backend: BinwalkV3Backend
    results: list[Module]

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Store default files and options for ``execute``.

        Args:
            *args: Default files and v2 command line options.
            **kwargs: Default keyword options.
        """
        self.backend = get_backend()
        self._args: tuple[object, ...] = args
        self._kwargs: dict[str, object] = dict(kwargs)
        self.results = []

    def __enter__(self) -> Self:
        """Enter a ``with`` block.

        Returns:
            This instance.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Leave a ``with`` block. Nothing needs cleaning up.

        Args:
            exc_type: Exception type, if one was raised.
            exc: Exception, if one was raised.
            traceback: Traceback, if an exception was raised.
        """

    def _request(self, args: Sequence[object], kwargs: Mapping[str, object]) -> ParsedRequest:
        merged = {**self._kwargs, **kwargs}
        return parse_request((*self._args, *args), merged)

    def execute(self, *args: object, **kwargs: object) -> list[Module]:
        """Scan files and return their modules.

        Arguments given here are added to those given to the constructor; keyword options
        given here override constructor options with the same name.

        Args:
            *args: Files and v2 command line options.
            **kwargs: Keyword options, for example ``extract=True`` or ``directory="out"``.

        Returns:
            For each file, a Signature module and, if entropy was requested, an Entropy module.

        Raises:
            ModuleException: If no files were given, an option is invalid, or the scan fails.
        """
        request = self._request(args, kwargs)
        if not request.files:
            message = "No files specified for scanning"
            raise ModuleException(message)
        options = request.options
        try:
            scanned = self.backend.scan_files(request.files, options)
        except ModuleException:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            message = f"Scan failed: {exc}"
            raise ModuleException(message) from exc
        modules: list[Module] = []
        for file_path, item in zip(request.files, scanned):
            modules.extend(
                build_modules(
                    file_path, item, signature=options.runs_signature, entropy=options.entropy
                )
            )
        self.results = modules
        return modules
