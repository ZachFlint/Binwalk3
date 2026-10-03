"""binwalk v2 calling conventions and result attributes."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

import binwalk
from binwalk.core.exceptions import ModuleException as CoreModuleException
from binwalk.core.module import Modules as CoreModules
from tests.helpers import FIXTURES

MULTI = str(FIXTURES / "multi_signatures.bin")
MULTI_OFFSETS = [0, 638, 1276]


@pytest.mark.usefixtures("backend")
def test_cli_style_arguments_match_keywords() -> None:
    by_flags = binwalk.scan("--signature", "--quiet", MULTI)
    by_short = binwalk.scan("-B", "-q", MULTI)
    by_kwargs = binwalk.scan(MULTI, signature=True, quiet=True)
    by_short_kwargs = binwalk.scan(MULTI, B=True, q=True)
    for modules in (by_flags, by_short, by_kwargs, by_short_kwargs):
        assert [module.name for module in modules] == ["Signature"]
        assert [result.offset for result in modules[0]] == MULTI_OFFSETS


@pytest.mark.usefixtures("backend")
def test_modules_context_manager_and_execute_alias() -> None:
    with CoreModules(MULTI, signature=True) as modules:
        results = modules.execute()
    assert [result.offset for result in results[0]] == MULTI_OFFSETS
    assert modules.results is results
    assert [r.offset for r in binwalk.execute(MULTI)[0]] == MULTI_OFFSETS


@pytest.mark.usefixtures("backend")
def test_execute_arguments_extend_constructor_arguments() -> None:
    simple = str(FIXTURES / "simple.zip")
    modules = CoreModules(MULTI).execute(simple)
    assert [module.file for module in modules] == [MULTI, simple]


@pytest.mark.usefixtures("backend")
def test_result_file_has_v2_attributes() -> None:
    relative = str(Path("tests") / "fixtures" / "simple.zip")
    (result,) = binwalk.scan(relative)[0].results
    assert result.file == relative
    assert result.file is not None
    assert result.file.name == relative
    assert result.file.path == str(Path(relative).resolve())
    assert result.file.size == 126
    assert result.valid
    assert result.display


def test_unsupported_option_warns_and_can_be_made_an_error() -> None:
    with pytest.warns(binwalk.UnsupportedOptionWarning, match="--opcodes"):
        binwalk.scan(MULTI, opcodes=True)
    with pytest.warns(binwalk.UnsupportedOptionWarning, match="--hexdump"):
        binwalk.scan("-W", MULTI)
    with warnings.catch_warnings():
        warnings.simplefilter("error", binwalk.UnsupportedOptionWarning)
        with pytest.raises(binwalk.UnsupportedOptionWarning):
            binwalk.scan(MULTI, raw="\x00")


def test_unknown_keyword_warns() -> None:
    with pytest.warns(binwalk.UnknownOptionWarning, match="not_an_option"):
        binwalk.scan(MULTI, not_an_option=True)


def test_invalid_usage_raises_module_exception() -> None:
    with pytest.raises(binwalk.ModuleException, match="No files specified"):
        binwalk.scan(signature=True)
    with pytest.raises(binwalk.ModuleException, match="Invalid include/exclude regex"):
        binwalk.scan(MULTI, include="(")
    with pytest.raises(binwalk.ModuleException, match="Invalid usage"):
        binwalk.scan(MULTI, "--depth", "deep")
    assert CoreModuleException is binwalk.ModuleException


@pytest.mark.usefixtures("backend")
def test_quiet_and_display_options_are_accepted_silently() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        modules = binwalk.scan(MULTI, quiet=True, verbose=False, term=True, csv=True, nplot=True)
    assert [result.offset for result in modules[0]] == MULTI_OFFSETS
