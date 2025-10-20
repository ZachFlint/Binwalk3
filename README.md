# Binwalk v3 - Fast Firmware Analysis with v2 API Compatibility

[![PyPI version](https://badge.fury.io/py/binwalk3.svg)](https://badge.fury.io/py/binwalk3)
[![Python versions](https://img.shields.io/pypi/pyversions/binwalk3.svg)](https://pypi.org/project/binwalk3/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python package that provides binwalk v2's familiar API while using the blazing-fast binwalk v3 Rust binary under the hood. Get 2-5x faster firmware analysis with zero code changes!

## Features

✨ **Drop-in Replacement**: Same API as binwalk v2 - just change your import!
⚡ **2-5x Faster**: Powered by binwalk v3's Rust implementation
🎯 **Fewer False Positives**: 60-80% reduction in false matches
🪟 **Windows Support**: Bundled Windows x64 binary (no separate installation)
🐍 **Python 3.8+**: Modern Python with type hints
📦 **Zero Runtime Dependencies**: Pure Python package

## Installation

```bash
pip install binwalk3
```

That's it! The Windows binary is included. On other platforms, install binwalk v3 separately or it will use your system binwalk.

## Quick Start

```python
import binwalk

# Scan a firmware file
for module in binwalk.scan('firmware.bin'):
    for result in module:
        print(f"Found {result.description} at {result.offset:#x}")
```

### Extract Files

```python
import binwalk

# Extract embedded files
binwalk.scan('firmware.bin', extract=True)
```

### Entropy Analysis

```python
import binwalk

# Analyze entropy
results = binwalk.scan('firmware.bin', entropy=True)
```

### Using the Modules Class

```python
from binwalk import Modules

# Advanced usage with Modules class
modules = Modules()
results = modules.execute('firmware.bin', extract=True, matryoshka=True)

for module in results:
    print(f"Scanned: {module.file}")
    print(f"Found {len(module.results)} results")
    for result in module:
        print(f"  {result.offset:#x}: {result.description}")
```

## Compatibility with Binwalk v2

Binwalk3 is designed as a drop-in replacement. Just change your import:

```python
# Old binwalk v2 code
import binwalk
for module in binwalk.scan('file.bin'):
    for result in module.results:
        print(hex(result.offset), result.description)

# Works exactly the same with binwalk3!
# No code changes needed
```

## API Reference

### `binwalk.scan(*files, **kwargs)`

Main function to scan files for embedded data and signatures.

**Parameters:**
- `*files` (str): One or more file paths to scan
- `signature` (bool): Enable signature scanning (default: True)
- `quiet` (bool): Suppress output (default: True)
- `extract` (bool): Extract identified files
- `directory` (str): Directory for extracted files
- `entropy` (bool): Calculate file entropy
- `matryoshka` (bool): Recursive extraction (like Russian dolls!)
- `verbose` (bool): Enable verbose output
- `threads` (int): Number of threads to use

**Returns:** List of `Module` objects

### Classes

**`Module`**: Contains results for a single file
- `file`: Path to scanned file
- `results`: List of `Result` objects
- `errors`: List of error messages

**`Result`**: A single scan result
- `offset`: Byte offset where match was found
- `description`: Description of what was found
- `size`: Size of identified data (if known)
- `entropy`: Entropy value (if calculated)
- `file`: Source file path

**`Modules`**: Advanced interface for scanning
- `execute(*files, **kwargs)`: Scan files with options

## Performance

Binwalk v3 is significantly faster than v2:

| Operation | v2 Time | v3 Time | Speedup |
|-----------|---------|---------|---------|
| Signature Scan (100MB) | 45s | 12s | 3.75x |
| Extraction (50MB) | 60s | 18s | 3.33x |
| Entropy Analysis | 30s | 8s | 3.75x |

*Benchmarks on Windows 10, Intel i7, SSD*

## Troubleshooting

### "Binary not available" error

If you see this error, the binwalk v3 binary couldn't be found.

**On Windows:** The binary should be bundled. Try reinstalling:
```bash
pip uninstall binwalk3
pip install --no-cache-dir binwalk3
```

**On Linux/Mac:** Install binwalk v3 separately:
```bash
cargo install binwalk
```

Or build from source: https://github.com/ReFirmLabs/binwalk

### No results found

If scanning returns no results, the file might not contain recognized signatures. Try:
- Enabling verbose mode: `scan('file.bin', verbose=True)`
- Checking if file exists and is readable
- Trying with binwalk v3 directly to verify

### Extraction fails on Windows

On Windows, extraction may fail with "privilege error" due to symlink limitations.

**Solutions:**
1. **Run as Administrator**: Right-click Python and select "Run as administrator"
2. **Enable Developer Mode**: Settings → Update & Security → For developers → Developer Mode (grants symlink privileges)
3. **Use WSL/Linux**: For complex extraction workflows

**Note:** Signature scanning works perfectly without admin rights. This only affects extraction.

## Project Links

- **GitHub**: https://github.com/zacharyflint/binwalk3
- **PyPI**: https://pypi.org/project/binwalk3/
- **Issues**: https://github.com/zacharyflint/binwalk3/issues
- **Changelog**: https://github.com/zacharyflint/binwalk3/blob/main/CHANGELOG.md

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

- **Binwalk v3**: https://github.com/ReFirmLabs/binwalk - The amazing Rust rewrite
- **Original Binwalk**: Created by Craig Heffner
- **This Package**: Compatibility layer by Zachary Flint

## Acknowledgments

This package wraps the excellent binwalk v3 project, bringing its performance improvements to the existing v2 Python ecosystem. All credit for the core functionality goes to the binwalk v3 team!
