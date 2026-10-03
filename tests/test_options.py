"""Option parsing: accepted argument types and rejected values."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

import binwalk
from tests.helpers import FIXTURES, write_nested_gzip

if TYPE_CHECKING:
    from pathlib import Path

MULTI = FIXTURES / "multi_signatures.bin"


@pytest.mark.usefixtures("backend")
def test_path_objects_and_bytes_paths_are_accepted() -> None:
    expected = [0, 638, 1276]
    assert [result.offset for result in binwalk.scan(MULTI)[0]] == expected
    assert [result.offset for result in binwalk.scan(os.fsencode(MULTI))[0]] == expected
    assert binwalk.scan(MULTI)[0].file == str(MULTI)


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("signatures", 5, "signatures must be a string or a sequence of strings"),
        ("exclude_signatures", 1.5, "exclude_signatures must be a string or a sequence of strings"),
        ("threads", True, "threads must be an integer"),
        ("threads", 2.5, "threads must be an integer"),
        ("threads", "many", "threads must be an integer"),
        ("timeout", False, "timeout must be a number"),
        ("timeout", [30], "timeout must be a number"),
        ("timeout", "soon", "timeout must be a number"),
        ("timeout", 0, "timeout must be positive"),
        ("timeout", -5, "timeout must be positive"),
        ("matryoshka", "deep", "matryoshka must be a bool or a positive int depth"),
        ("include", "(unclosed", r"Invalid include/exclude regex '\(unclosed'"),
        ("exclude", "[z-a]", r"Invalid include/exclude regex '\[z-a\]'"),
    ],
)
def test_invalid_option_values_raise(option: str, value: object, message: str) -> None:
    with pytest.raises(binwalk.ModuleException, match=message):
        binwalk.scan(str(MULTI), **{option: value})


@pytest.mark.usefixtures("backend")
def test_numeric_strings_are_accepted() -> None:
    (module,) = binwalk.scan(str(MULTI), threads="1", timeout="30")
    assert [result.offset for result in module] == [0, 638, 1276]


@pytest.mark.usefixtures("backend")
def test_unknown_command_line_option_warns_and_is_ignored() -> None:
    with pytest.warns(binwalk.UnknownOptionWarning, match="Ignoring unknown option '--bogus'"):
        (module,) = binwalk.scan("--bogus", str(MULTI))
    assert module.file == str(MULTI)
    assert [result.offset for result in module] == [0, 638, 1276]


@pytest.mark.usefixtures("backend")
@pytest.mark.parametrize("value", [False, None, 0])
def test_falsy_matryoshka_disables_recursion(tmp_path: Path, value: object) -> None:
    target = write_nested_gzip(tmp_path / "triple.gz", levels=3)
    (module,) = binwalk.scan(
        str(target), extract=True, matryoshka=value, directory=str(tmp_path / "out")
    )
    assert [result.depth for result in module] == [0]
