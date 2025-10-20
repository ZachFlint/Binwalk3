"""Test basic import functionality."""

import pytest


def test_import_binwalk():
    """Test that binwalk can be imported."""
    import binwalk

    assert binwalk is not None


def test_import_scan():
    """Test that scan function can be imported."""
    from binwalk import scan

    assert callable(scan)


def test_import_modules():
    """Test that Modules class can be imported."""
    from binwalk.core.module import Modules

    assert Modules is not None


def test_import_all():
    """Test that all exports are available."""
    import binwalk

    assert hasattr(binwalk, "scan")
    assert hasattr(binwalk, "Modules")
    assert hasattr(binwalk, "Module")
    assert hasattr(binwalk, "Result")
    assert hasattr(binwalk, "ModuleException")


def test_version_attributes():
    """Test that version attributes exist and are correct."""
    import binwalk

    assert hasattr(binwalk, "__version__")
    assert hasattr(binwalk, "__api_version__")
    assert hasattr(binwalk, "__binwalk_core_version__")

    assert binwalk.__version__ == "3.1.0"
    assert binwalk.__api_version__ == "2.3.4"
    assert binwalk.__binwalk_core_version__ == "3.1.0"


def test_module_docstrings():
    """Test that main module has documentation."""
    import binwalk

    assert binwalk.__doc__ is not None
    assert len(binwalk.__doc__) > 0
