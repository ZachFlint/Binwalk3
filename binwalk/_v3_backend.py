"""Binwalk v3 backend implementation.

This module provides a wrapper around the binwalk v3 Rust binary,
exposing it through a Python interface compatible with binwalk v2.
"""

import json
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class V3ScanResult:
    """Result from a single binwalk v3 scan match."""

    offset: int
    description: str
    size: Optional[int] = None
    entropy: Optional[float] = None
    file: Optional[str] = None
    module: Optional[str] = None

    def __repr__(self) -> str:
        """Return formatted string representation."""
        parts = [f"offset={self.offset:#x}", f"description='{self.description}'"]
        if self.size is not None:
            parts.append(f"size={self.size}")
        if self.entropy is not None:
            parts.append(f"entropy={self.entropy:.2f}")
        return f"<V3ScanResult: {', '.join(parts)}>"


@dataclass
class V3ModuleResult:
    """Results from a binwalk v3 module scan."""

    results: list[V3ScanResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def __iter__(self):
        """Iterate over scan results."""
        return iter(self.results)

    def __len__(self):
        """Return number of results."""
        return len(self.results)


class BinwalkV3Backend:
    """Backend interface to binwalk v3 binary."""

    def __init__(self, binary_path: Optional[str] = None):
        """Initialize backend with optional binary path.

        Args:
            binary_path: Path to binwalk v3 binary. If None, will search for bundled or system binary.
        """
        self.binary_path = binary_path or self._find_binary()
        self.available = self._validate_binary()

    def _find_binary(self) -> str:
        """Find binwalk v3 binary.

        Searches in order:
        1. Bundled binary in package
        2. System PATH for binwalk3/binwalk

        Returns:
            Path to binary or default name
        """
        # Check for bundled binary
        package_dir = Path(__file__).parent
        binary_dir = package_dir / "binwalk_bin"

        # Platform-specific binary names
        system = platform.system().lower()
        machine = platform.machine().lower()

        binary_map = {
            ("windows", "amd64"): "binwalk_windows_x64.exe",
            ("windows", "x86_64"): "binwalk_windows_x64.exe",
        }

        # Check bundled binary
        binary_name = binary_map.get((system, machine))
        if binary_name:
            bundled_binary = binary_dir / binary_name
            if bundled_binary.exists():
                # Make executable on Unix-like systems
                if system != "windows":
                    bundled_binary.chmod(0o755)
                return str(bundled_binary)

        # Search system PATH
        for name in ["binwalk3", "binwalk", "binwalk.exe"]:
            binary = shutil.which(name)
            if binary and self._is_v3_binary(binary):
                return binary

        # Default fallback
        return "binwalk3"

    def _is_v3_binary(self, binary_path: str) -> bool:
        """Check if binary is binwalk v3.

        Args:
            binary_path: Path to binary to check

        Returns:
            True if binary is v3, False otherwise
        """
        try:
            result = subprocess.run(
                [binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # v3 typically shows "binwalk 3.x.x" in output
            return result.returncode == 0 and "3." in result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _validate_binary(self) -> bool:
        """Validate that binary exists and is executable.

        Returns:
            True if binary is available and functional
        """
        try:
            result = subprocess.run(
                [self.binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def scan(
        self,
        *files: str,
        signature: bool = False,
        quiet: bool = True,
        extract: bool = False,
        directory: Optional[str] = None,
        entropy: bool = False,
        matryoshka: bool = False,
        verbose: bool = False,
        threads: Optional[int] = None,
        **kwargs: Any,
    ) -> list[V3ModuleResult]:
        """Scan files for signatures using binwalk v3.

        Args:
            *files: Paths to files to scan
            signature: Enable signature scanning (default True in v3)
            quiet: Suppress output
            extract: Extract identified files
            directory: Directory for extraction
            entropy: Calculate entropy
            matryoshka: Recursive scanning
            verbose: Verbose output
            threads: Number of threads to use
            **kwargs: Additional arguments (for v2 compatibility)

        Returns:
            List of V3ModuleResult objects, one per file

        Raises:
            RuntimeError: If binwalk binary is not available
            ValueError: If no files specified
        """
        if not self.available:
            raise RuntimeError(
                f"Binwalk v3 binary not available at: {self.binary_path}. "
                "See binwalk_bin/BUILD_NOTE.md for compilation instructions."
            )

        if not files:
            raise ValueError("No files specified for scanning")

        results = []
        for file_path in files:
            try:
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    result = V3ModuleResult()
                    result.errors.append(f"File not found: {file_path}")
                    results.append(result)
                    continue

                result = self._scan_single_file(
                    str(file_path_obj),
                    extract=extract,
                    directory=directory,
                    entropy=entropy,
                    matryoshka=matryoshka,
                    quiet=quiet,
                    verbose=verbose,
                    threads=threads,
                )
                results.append(result)
            except Exception as e:
                result = V3ModuleResult()
                result.errors.append(f"Error scanning {file_path}: {str(e)}")
                results.append(result)

        return results

    def _scan_single_file(
        self,
        file_path: str,
        extract: bool = False,
        directory: Optional[str] = None,
        entropy: bool = False,
        matryoshka: bool = False,
        quiet: bool = True,
        verbose: bool = False,
        threads: Optional[int] = None,
    ) -> V3ModuleResult:
        """Scan a single file with binwalk v3.

        Args:
            file_path: Path to file to scan
            extract: Extract identified files
            directory: Directory for extraction
            entropy: Calculate entropy
            matryoshka: Recursive scanning
            quiet: Suppress output
            verbose: Verbose output
            threads: Number of threads

        Returns:
            V3ModuleResult with scan results
        """
        # Create temporary JSON output file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json_path = f.name

        try:
            # Build command
            cmd = [self.binary_path, "-l", json_path]

            if extract:
                cmd.append("-e")
            if directory and extract:
                cmd.extend(["-C", directory])
            if matryoshka:
                cmd.append("-M")
            if entropy:
                cmd.append("-E")
            if quiet and not verbose:
                cmd.append("-q")
            if verbose:
                cmd.append("-v")
            if threads:
                cmd.extend(["-t", str(threads)])

            cmd.append(file_path)

            # Execute binwalk
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )

            # Parse results
            module_result = self._parse_json_output(json_path, file_path)

            # Check for errors
            if result.returncode not in (0, 1):
                if result.stderr:
                    module_result.errors.append(f"Binwalk error: {result.stderr}")

            return module_result

        finally:
            # Cleanup temp file
            Path(json_path).unlink(missing_ok=True)

    def _parse_json_output(
        self, json_path: str, file_path: str
    ) -> V3ModuleResult:
        """Parse binwalk v3 JSON output.

        Args:
            json_path: Path to JSON output file
            file_path: Original file path being scanned

        Returns:
            V3ModuleResult with parsed results
        """
        module_result = V3ModuleResult()

        try:
            with open(json_path, "r") as f:
                data = json.load(f)

            # Binwalk v3 actual format: [{"Analysis": {"file_map": [...]}}]
            if isinstance(data, list) and len(data) > 0:
                analysis = data[0].get("Analysis", {})

                # Parse file_map (signature results)
                file_map = analysis.get("file_map", [])
                for item in file_map:
                    result = V3ScanResult(
                        offset=item.get("offset", 0),
                        description=item.get("description", ""),
                        size=item.get("size"),
                        file=file_path,
                        module=item.get("name", "signature"),
                    )
                    module_result.results.append(result)

            # Fallback: Old format for compatibility
            elif isinstance(data, dict):
                # Parse signature results
                if "signatures" in data:
                    for item in data["signatures"]:
                        result = V3ScanResult(
                            offset=item.get("offset", 0),
                            description=item.get("description", ""),
                            size=item.get("size"),
                            file=file_path,
                            module="signature",
                        )
                        module_result.results.append(result)
                elif "results" in data:
                    # Alternative format
                    for item in data["results"]:
                        result = V3ScanResult(
                            offset=item.get("offset", 0),
                            description=item.get("description", ""),
                            size=item.get("size"),
                            file=file_path,
                            module="signature",
                        )
                        module_result.results.append(result)

                # Parse entropy results
                if "entropy" in data:
                    for item in data["entropy"]:
                        result = V3ScanResult(
                            offset=item.get("offset", 0),
                            description=f"Entropy: {item.get('entropy', 0):.2f}",
                            entropy=item.get("entropy"),
                            file=file_path,
                            module="entropy",
                        )
                        module_result.results.append(result)

        except (json.JSONDecodeError, FileNotFoundError) as e:
            module_result.errors.append(f"Failed to parse results: {str(e)}")

        return module_result


# Global backend instance
_backend: Optional[BinwalkV3Backend] = None


def get_backend() -> BinwalkV3Backend:
    """Get or create global backend instance.

    Returns:
        Singleton BinwalkV3Backend instance
    """
    global _backend
    if _backend is None:
        _backend = BinwalkV3Backend()
    return _backend
