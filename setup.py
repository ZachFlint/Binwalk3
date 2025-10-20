"""Setup script for binwalk3 compatibility package."""

from pathlib import Path

from setuptools import setup

# Read long description from README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8")

setup(
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_data={
        "binwalk": ["py.typed"],
        "binwalk.binwalk_bin": ["*.exe", "*.md"],
    },
    include_package_data=True,
)
