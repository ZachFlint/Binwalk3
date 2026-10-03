"""Run every Python example in README.md against real files."""

from __future__ import annotations

import re
import shutil
import warnings
from pathlib import Path

import pytest

import binwalk
from tests.helpers import FIXTURES, write_nested_gzip

README = Path(__file__).resolve().parent.parent / "README.md"
BLOCK_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)
EXAMPLES = BLOCK_RE.findall(README.read_text(encoding="utf-8"))


def test_readme_has_examples() -> None:
    assert len(EXAMPLES) >= 10


@pytest.mark.usefixtures("backend")
@pytest.mark.parametrize(
    "source", EXAMPLES, ids=[f"example{index}" for index in range(len(EXAMPLES))]
)
def test_readme_example_runs(
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_nested_gzip(tmp_path / "firmware.bin", levels=2)
    shutil.copy2(FIXTURES / "multi_signatures.bin", tmp_path / "other.bin")
    monkeypatch.chdir(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error", binwalk.UnknownOptionWarning)
        exec(compile(source, "README.md", "exec"), {"__name__": "__readme__"})
    if "print(" in source:
        assert capsys.readouterr().out.strip()
