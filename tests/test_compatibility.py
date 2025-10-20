"""Test v2 API compatibility."""

import pytest

from binwalk import Module, ModuleException, Modules, Result


def test_result_class():
    """Test Result class instantiation and attributes."""
    result = Result(
        offset=0x1000, description="Test signature", size=100, entropy=0.5
    )

    assert result.offset == 0x1000
    assert result.description == "Test signature"
    assert result.size == 100
    assert result.entropy == 0.5


def test_result_repr():
    """Test Result __repr__ method."""
    result = Result(offset=256, description="ZIP archive")

    repr_str = repr(result)
    assert "0x100" in repr_str
    assert "ZIP archive" in repr_str


def test_module_class():
    """Test Module class."""
    module = Module("test.bin")

    assert module.file == "test.bin"
    assert isinstance(module.results, list)
    assert isinstance(module.errors, list)
    assert len(module) == 0


def test_module_iteration():
    """Test Module iteration."""
    module = Module("test.bin")
    module.results.append(Result(offset=0, description="Test"))

    count = 0
    for result in module:
        count += 1
        assert isinstance(result, Result)

    assert count == 1
    assert len(module) == 1


def test_modules_class():
    """Test Modules class instantiation."""
    modules = Modules()

    assert modules is not None
    assert hasattr(modules, "execute")
    assert hasattr(modules, "backend")


def test_module_exception():
    """Test ModuleException."""
    exc = ModuleException("Test error")

    assert isinstance(exc, Exception)
    assert str(exc) == "Test error"


def test_scan_function_signature():
    """Test that scan function has correct signature."""
    from binwalk import scan

    import inspect

    sig = inspect.signature(scan)
    assert "files" in str(sig)
    assert "kwargs" in str(sig)
