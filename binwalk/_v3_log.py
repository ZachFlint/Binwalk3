"""Parse the JSON log that ``binwalk --log`` writes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

_SEPARATORS = frozenset(" \t\r\n,]")


@dataclass(frozen=True)
class LogSignature:
    """One entry of an analysis ``file_map``.

    Attributes:
        offset: Byte offset of the match.
        id: Unique id that links the match to its extraction result.
        size: Size of the matched data in bytes.
        name: Signature name, for example ``zip``.
        confidence: Signature confidence (0-255).
        description: Human-readable description.
    """

    offset: int
    id: str
    size: int
    name: str
    confidence: int
    description: str


@dataclass(frozen=True)
class LogExtraction:
    """One entry of an analysis ``extractions`` map.

    Attributes:
        success: Whether the extractor reported success.
        extractor: Extractor name, for example ``7z`` or ``gzip``.
        output_directory: Directory the extractor wrote into.
        size: Number of bytes the extractor consumed, if known.
        do_not_recurse: True if binwalk will not scan the extracted files recursively.
    """

    success: bool
    extractor: str
    output_directory: str
    size: int | None
    do_not_recurse: bool


@dataclass(frozen=True)
class LogAnalysis:
    """Analysis results for one file, either the target or a recursively extracted file.

    Attributes:
        file_path: Path of the analyzed file as binwalk saw it.
        signatures: Matches in file order.
        extractions: Extraction results keyed by signature id.
    """

    file_path: str
    signatures: tuple[LogSignature, ...] = ()
    extractions: Mapping[str, LogExtraction] = field(default_factory=dict[str, LogExtraction])


def iter_documents(text: str) -> list[object]:
    """Decode every JSON value in a binwalk log, tolerating legacy framing errors.

    binwalk 3.1.1 writes one valid JSON list. binwalk 3.1.0 on Windows appends to the file
    after writing a closing bracket, producing ``[A ], B ]``. Values are decoded one at a
    time and commas, closing brackets and whitespace between them are skipped. Top-level lists
    are flattened.

    Args:
        text: Raw log file contents.

    Returns:
        The decoded top-level values in order.

    Raises:
        ValueError: If the log contains text that is not JSON.
    """
    decoder = json.JSONDecoder()
    values: list[object] = []
    position = 0
    length = len(text)
    while position < length:
        if text[position] in _SEPARATORS:
            position += 1
            continue
        try:
            value, position = cast("tuple[object, int]", decoder.raw_decode(text, position))
        except json.JSONDecodeError as exc:
            message = f"Invalid JSON in binwalk log at offset {exc.pos}: {exc.msg}"
            raise ValueError(message) from exc
        if isinstance(value, list):
            values.extend(cast("list[object]", value))
        else:
            values.append(value)
    return values


def _as_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in cast("dict[object, object]", value).items()}


def _as_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _parse_signature(raw: object) -> LogSignature | None:
    entry = _as_mapping(raw)
    if "offset" not in entry:
        return None
    return LogSignature(
        offset=_as_int(entry.get("offset")),
        id=_as_str(entry.get("id")),
        size=_as_int(entry.get("size")),
        name=_as_str(entry.get("name")),
        confidence=_as_int(entry.get("confidence")),
        description=_as_str(entry.get("description")),
    )


def _parse_extraction(raw: object) -> LogExtraction:
    entry = _as_mapping(raw)
    size = entry.get("size")
    return LogExtraction(
        success=entry.get("success") is True,
        extractor=_as_str(entry.get("extractor")),
        output_directory=_as_str(entry.get("output_directory")),
        size=size if isinstance(size, int) and not isinstance(size, bool) else None,
        do_not_recurse=entry.get("do_not_recurse") is True,
    )


def _parse_analysis(raw: object) -> LogAnalysis:
    entry = _as_mapping(raw)
    raw_map = entry.get("file_map")
    signatures = tuple(
        signature
        for signature in (
            _parse_signature(item)
            for item in (cast("list[object]", raw_map) if isinstance(raw_map, list) else [])
        )
        if signature is not None
    )
    extractions = {
        key: _parse_extraction(value)
        for key, value in _as_mapping(entry.get("extractions")).items()
    }
    return LogAnalysis(
        file_path=_as_str(entry.get("file_path")), signatures=signatures, extractions=extractions
    )


def parse_analyses(text: str) -> list[LogAnalysis]:
    """Return every ``Analysis`` document in a binwalk log, in the order binwalk wrote them.

    The first analysis is the target file. Later ones come from recursive (matryoshka) scans
    of extracted files. ``Entropy`` documents are ignored because entropy is computed in Python.
    A ValueError from ``iter_documents`` propagates if the log is not valid JSON.

    Args:
        text: Raw log file contents.

    Returns:
        Parsed analyses.
    """
    analyses: list[LogAnalysis] = []
    for document in iter_documents(text):
        mapping = _as_mapping(document)
        if "Analysis" in mapping:
            analyses.append(_parse_analysis(mapping["Analysis"]))
    return analyses
