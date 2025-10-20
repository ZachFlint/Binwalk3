"""Test v3 backend functionality."""

import pytest

from binwalk._v3_backend import (
    BinwalkV3Backend,
    V3ModuleResult,
    V3ScanResult,
    get_backend,
)


def test_v3scan_result_dataclass():
    """Test V3ScanResult dataclass."""
    result = V3ScanResult(
        offset=0x100, description="Test", size=50, entropy=0.7, module="signature"
    )

    assert result.offset == 0x100
    assert result.description == "Test"
    assert result.size == 50
    assert result.entropy == 0.7
    assert result.module == "signature"


def test_v3module_result_dataclass():
    """Test V3ModuleResult dataclass."""
    module_result = V3ModuleResult()

    assert isinstance(module_result.results, list)
    assert isinstance(module_result.errors, list)
    assert len(module_result) == 0


def test_v3module_result_iteration():
    """Test V3ModuleResult iteration."""
    module_result = V3ModuleResult()
    module_result.results.append(V3ScanResult(offset=0, description="Test"))

    count = 0
    for result in module_result:
        count += 1

    assert count == 1


def test_backend_initialization():
    """Test BinwalkV3Backend initialization."""
    backend = BinwalkV3Backend()

    assert backend is not None
    assert hasattr(backend, "binary_path")
    assert hasattr(backend, "available")
    assert isinstance(backend.available, bool)


def test_find_binary():
    """Test binary detection."""
    backend = BinwalkV3Backend()

    assert backend.binary_path is not None
    assert isinstance(backend.binary_path, str)


def test_validate_binary():
    """Test binary validation."""
    backend = BinwalkV3Backend()

    # Should complete without error
    assert isinstance(backend.available, bool)


def test_scan_nonexistent_file():
    """Test scanning nonexistent file."""
    backend = BinwalkV3Backend()

    if not backend.available:
        # If binary not available, should raise RuntimeError
        with pytest.raises(RuntimeError):
            backend.scan("nonexistent_file_12345.bin")
    else:
        # If binary available, should handle missing file gracefully
        results = backend.scan("nonexistent_file_12345.bin")
        assert len(results) == 1
        assert len(results[0].errors) > 0


def test_get_backend_singleton():
    """Test backend singleton pattern."""
    backend1 = get_backend()
    backend2 = get_backend()

    assert backend1 is backend2


def test_backend_scan_requires_binary():
    """Test that scan requires binary when it's not available."""
    backend = BinwalkV3Backend()

    if not backend.available:
        with pytest.raises(RuntimeError, match="not available"):
            backend.scan("test.bin")


def test_backend_scan_requires_files():
    """Test that scan requires at least one file."""
    backend = BinwalkV3Backend()

    if backend.available:
        with pytest.raises(ValueError, match="No files"):
            backend.scan()
