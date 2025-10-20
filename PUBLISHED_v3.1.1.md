# Binwalk3 v3.1.1 - Published to PyPI

**Date:** October 19, 2025
**Version:** 3.1.1
**PyPI URL:** https://pypi.org/project/binwalk3/3.1.1/

## Publication Status

✅ **SUCCESSFULLY PUBLISHED**

Both distribution packages uploaded:
- `binwalk3-3.1.1-py3-none-any.whl` (3.5 MB)
- `binwalk3-3.1.1.tar.gz` (3.4 MB)

## Critical Bug Fix

### Issue in v3.1.0
The initial release had a critical JSON parsing bug that caused **ALL signature scans to return zero results**.

**Root Cause:**
- Python wrapper expected: `{"signatures": [...]}`
- Binwalk v3 outputs: `[{"Analysis": {"file_map": [...]}}]`

**Impact:** Complete failure of signature detection in v3.1.0

### Fix in v3.1.1
Updated `_parse_json_output()` in `binwalk/_v3_backend.py`:
- Correctly parses `[{"Analysis": {"file_map": [...]}}]` format
- Maintains backward compatibility with old format
- All signature types now detected correctly

## Validation Results

### Real Binary Tests (6/6 Passed)
✅ MSI Installer - 2 signatures (CAB + PNG)
✅ Adobe JAR - 1 signature (ZIP)
✅ notepad.exe - 3 signatures (PE + Copyright + PNG)
✅ kernel32.dll - 2 signatures (PE + CRC)
✅ shell32.dll - 2 signatures (PE + Copyright)
✅ mmc.exe - 6 signatures (PE + CRC + Copyright + PNG)

### Comprehensive Feature Tests (9/10 Passed)
✅ ZIP signature detection
✅ JAR file detection
✅ MSI file detection
✅ Embedded signatures at custom offsets
✅ Entropy calculation
✅ Non-existent file error handling
✅ Multiple file scanning
✅ Empty file handling
✅ Signature parameter functionality
⚠️ Extraction (Windows symlink privilege limitation - documented)

## Signature Types Verified

All working correctly in real binaries:
- Windows PE executables
- ZIP archives (JAR files)
- Microsoft Cabinet (CAB) archives
- PNG images
- Copyright text
- CRC32 polynomial tables

## Known Limitations

**Extraction on Windows:** Requires administrator privileges due to binwalk v3 binary's use of symlinks (Windows OS limitation). Solutions documented in README:
1. Run as administrator
2. Enable Developer Mode
3. Use WSL/Linux

## Installation

```bash
pip install binwalk3
```

## Quick Test

```python
import binwalk

# Scan a file
for module in binwalk.scan('firmware.bin'):
    for result in module:
        print(f"{result.offset:#x}: {result.description}")
```

## Changes from v3.1.0

### Fixed
- **Critical**: JSON parsing now handles binwalk v3 format correctly
- Signature detection now works (was returning empty in v3.1.0)
- All file format signatures detected properly

### Documentation
- Added Windows extraction limitation note
- Added troubleshooting for privilege errors
- Comprehensive validation documentation

## Files Updated

1. `binwalk/_v3_backend.py` - Fixed JSON parsing
2. `README.md` - Added Windows extraction notes
3. `CHANGELOG.md` - Added v3.1.1 release notes
4. `pyproject.toml` - Version bump to 3.1.1
5. `binwalk/__version__.py` - Version bump to 3.1.1

## Verification

Package tested and verified:
- Locally installed from wheel
- All real binary tests passing
- All feature tests passing (except known Windows extraction limitation)

## Recommendation

✅ Users on v3.1.0 should upgrade immediately:
```bash
pip install --upgrade binwalk3
```

v3.1.0 has non-functional signature detection and should not be used.
