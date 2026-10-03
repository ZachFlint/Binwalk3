"""Version information."""

from __future__ import annotations

from binwalk._binary import read_manifest

__version__ = "3.2.0"
__api_version__ = "2.3.4"


def _core_version() -> str:
    manifest = read_manifest()
    version = manifest.get("binwalk_version")
    commit = manifest.get("upstream_commit")
    if isinstance(version, str) and isinstance(commit, str) and commit:
        return f"{version}+{commit[:7]}"
    return "unknown"


__binwalk_core_version__ = _core_version()
