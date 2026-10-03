"""Parsing of real binwalk JSON logs, including the malformed binwalk 3.1.0 Windows format."""

from __future__ import annotations

import json

import pytest

from binwalk._v3_log import iter_documents, parse_analyses
from tests.helpers import FIXTURES

LEGACY_LOG = FIXTURES / "logs" / "v3.1.0-windows-matryoshka.json"
MODERN_LOG = FIXTURES / "logs" / "v3.1.1-matryoshka.json"


def test_legacy_log_is_not_valid_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        json.loads(LEGACY_LOG.read_text(encoding="utf-8"))


def test_legacy_log_parses_every_analysis() -> None:
    analyses = parse_analyses(LEGACY_LOG.read_text(encoding="utf-8"))
    assert [analysis.file_path.rsplit("\\", 1)[-1] for analysis in analyses] == [
        "nested.bin",
        "test.txt",
    ]
    parent, child = analyses
    assert [(sig.offset, sig.name, sig.size) for sig in parent.signatures] == [(130, "zip", 126)]
    extraction = parent.extractions[parent.signatures[0].id]
    assert extraction.success
    assert extraction.extractor == "7z"
    assert child.file_path.startswith(extraction.output_directory)
    assert child.signatures == ()


def test_modern_log_parses_every_analysis() -> None:
    text = MODERN_LOG.read_text(encoding="utf-8")
    assert len(json.loads(text)) == 2
    analyses = parse_analyses(text)
    assert len(analyses) == 2
    assert analyses[0].signatures[0].description.startswith("ZIP archive, version: 2.0")
    assert analyses[0].signatures[0].confidence == 250


def test_entropy_documents_are_skipped() -> None:
    text = json.dumps(
        [
            {"Entropy": {"file": "x", "blocks": [{"start": 0, "end": 4, "entropy": 1.0}]}},
            {"Analysis": {"file_path": "x", "file_map": [], "extractions": {}}},
        ]
    )
    assert [analysis.file_path for analysis in parse_analyses(text)] == ["x"]


def test_malformed_entries_are_dropped_or_defaulted() -> None:
    text = json.dumps(
        [
            7,
            {
                "Analysis": {
                    "file_path": "x",
                    "file_map": [
                        "not an entry",
                        {"id": "no-offset", "name": "zip"},
                        {"offset": 32, "id": "kept", "size": "big", "name": 5, "confidence": True},
                    ],
                    "extractions": {},
                }
            },
        ]
    )
    (analysis,) = parse_analyses(text)
    (signature,) = analysis.signatures
    assert (signature.offset, signature.id, signature.size, signature.name) == (32, "kept", 0, "")
    assert signature.confidence == 0
    assert signature.description == ""


def test_invalid_log_reports_offset() -> None:
    with pytest.raises(ValueError, match="offset 2"):
        iter_documents("[ nonsense ]")
