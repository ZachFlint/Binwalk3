"""Build hooks that tag the wheel for the platform of the bundled executable.

When ``binwalk/binwalk_bin/binwalk_windows_x64.exe`` exists, the wheel is tagged
``py3-none-win_amd64`` and contains the executable and its manifest. Set
``BINWALK3_PURE_WHEEL=1`` (or build without the executable) to produce a ``py3-none-any``
wheel that uses binwalk v3 from PATH.
"""

from __future__ import annotations

import os
from pathlib import Path

from setuptools import Distribution, setup
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.command.build_py import build_py

BUNDLED_FILES = ["binwalk_windows_x64.exe", "manifest.json"]
BUNDLED_EXE = Path(__file__).resolve().parent / "binwalk" / "binwalk_bin" / BUNDLED_FILES[0]
PLATFORM_TAG = "win_amd64"


def _bundling() -> bool:
    return BUNDLED_EXE.is_file() and os.environ.get("BINWALK3_PURE_WHEEL") != "1"


class BinaryDistribution(Distribution):
    """Report platform-specific content so files install at the wheel root (platlib)."""

    def has_ext_modules(self) -> bool:
        """Report whether the build carries a platform-specific executable.

        Returns:
            True when the bundled executable is included.
        """
        return _bundling()


class BuildPy(build_py):
    """Copy package files, leaving out the executable when it is not bundled."""

    def run(self) -> None:
        """Copy the package files, then remove bundled files left by an earlier build.

        setuptools reuses its build directory, so a previous bundled build can leave the
        executable there, and it would otherwise end up in a ``py3-none-any`` wheel.
        """
        super().run()
        if not _bundling() and not self.editable_mode:
            target = Path(self.build_lib) / "binwalk" / "binwalk_bin"
            for name in BUNDLED_FILES:
                (target / name).unlink(missing_ok=True)


class BdistWheel(bdist_wheel):
    """Mark the wheel platform-specific when it carries the executable."""

    def finalize_options(self) -> None:
        """Set the platform name and purity before the build starts."""
        if _bundling():
            self.plat_name = PLATFORM_TAG
            self.plat_name_supplied = True
        super().finalize_options()
        self.root_is_pure = not _bundling()

    def get_tag(self) -> tuple[str, str, str]:
        """Return the wheel tag.

        Returns:
            ``("py3", "none", "win_amd64")`` with the executable, else ``("py3", "none", "any")``.
        """
        return ("py3", "none", PLATFORM_TAG if _bundling() else "any")


setup(
    distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": BdistWheel, "build_py": BuildPy},
    package_data={
        "binwalk": ["py.typed"],
        "binwalk.binwalk_bin": BUNDLED_FILES if _bundling() else [],
    },
)
