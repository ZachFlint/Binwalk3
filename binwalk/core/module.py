"""Binwalk v2-compatible module interface.

This module provides classes that mimic the binwalk v2 API while using
the faster binwalk v3 backend under the hood.
"""

from typing import Any, Optional

from .._v3_backend import get_backend


class Result:
    """V2-compatible Result class.

    Represents a single scan result from binwalk.
    """

    def __init__(
        self,
        offset: int = 0,
        description: str = "",
        size: Optional[int] = None,
        entropy: Optional[float] = None,
        file: Optional[str] = None,
        module: Optional[str] = None,
    ):
        """Initialize a Result.

        Args:
            offset: Byte offset of the result
            description: Description of what was found
            size: Size of the identified data (if known)
            entropy: Entropy value (if calculated)
            file: File path this result came from
            module: Module type that detected this result
        """
        self.offset = offset
        self.description = description
        self.size = size
        self.entropy = entropy
        self.file = file
        self.module = module

    def __repr__(self) -> str:
        """Return string representation of Result."""
        return f"<Result: offset={self.offset:#x}, description='{self.description}'>"


class Module:
    """V2-compatible Module class.

    Represents scan results for a single file.
    """

    def __init__(self, file_path: str):
        """Initialize a Module.

        Args:
            file_path: Path to the file that was scanned
        """
        self.file = file_path
        self.results: list[Result] = []
        self.errors: list[str] = []

    def __iter__(self):
        """Iterate over results."""
        return iter(self.results)

    def __len__(self):
        """Return number of results."""
        return len(self.results)


class ModuleException(Exception):
    """V2-compatible ModuleException.

    Raised when module operations fail.
    """

    pass


class Modules:
    """V2-compatible Modules class using v3 backend.

    This class provides the primary interface for scanning files,
    maintaining compatibility with binwalk v2's API while using
    the faster binwalk v3 backend.

    Example:
        >>> from binwalk.core.module import Modules
        >>> modules = Modules()
        >>> results = modules.execute('firmware.bin')
        >>> for module in results:
        ...     for result in module:
        ...         print(f"Found {result.description} at {result.offset:#x}")
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize Modules instance.

        Args:
            *args: Positional arguments (for v2 compatibility)
            **kwargs: Keyword arguments passed to scan operations
        """
        self.backend = get_backend()
        self._args = args
        self._kwargs = kwargs

    def execute(self, *files: str, **kwargs: Any) -> list[Module]:
        """Execute binwalk scan on files.

        This is the main entry point for scanning files. It maintains
        compatibility with binwalk v2's interface while using v3 internally.

        Args:
            *files: One or more file paths to scan
            **kwargs: Scan options:
                - signature (bool): Enable signature scanning
                - quiet (bool): Suppress output
                - extract (bool): Extract identified files
                - directory (str): Directory for extraction
                - entropy (bool): Calculate entropy
                - matryoshka (bool): Recursive scanning
                - verbose (bool): Verbose output
                - threads (int): Number of threads

        Returns:
            List of Module objects, one per file scanned

        Raises:
            ModuleException: If scan fails

        Example:
            >>> modules = Modules()
            >>> results = modules.execute('file1.bin', 'file2.bin', extract=True)
        """
        # Merge instance kwargs with call kwargs
        merged_kwargs = {**self._kwargs, **kwargs}

        try:
            # Call v3 backend
            v3_results = self.backend.scan(*files, **merged_kwargs)

            # Convert to v2-compatible Module objects
            modules = []
            for file_path, v3_module in zip(files, v3_results):
                module = Module(file_path)

                # Convert V3ScanResult to Result
                for v3_result in v3_module.results:
                    result = Result(
                        offset=v3_result.offset,
                        description=v3_result.description,
                        size=v3_result.size,
                        entropy=v3_result.entropy,
                        file=v3_result.file,
                        module=v3_result.module,
                    )
                    module.results.append(result)

                # Copy errors
                module.errors = v3_module.errors.copy()

                modules.append(module)

            return modules

        except Exception as e:
            raise ModuleException(f"Scan failed: {str(e)}") from e
