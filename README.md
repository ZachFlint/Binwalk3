# binwalk3

binwalk3 runs [binwalk v3](https://github.com/ReFirmLabs/binwalk) (the Rust rewrite) and
returns its results through the binwalk v2 Python API. Code written for `import binwalk`
v2 can switch to the faster v3 scanner with few or no changes.

The Windows x64 wheel includes a binwalk v3 executable. On other platforms, install
binwalk v3 yourself and put it on `PATH`.

## Install

```
pip install binwalk3
```

To save entropy graphs as PNG files, also install matplotlib:

```
pip install binwalk3[plot]
```

The package is imported as `binwalk`. It cannot be installed alongside binwalk v2, which
uses the same import name.

Python 3.9 or newer is required.

## Which binwalk executable is used

The first match wins:

1. The path in the `BINWALK3_BINARY` environment variable. If it is set but does not point
   to a working binwalk 3.x, no other location is tried.
2. The executable bundled in the Windows x64 wheel.
3. `binwalk3`, then `binwalk`, on `PATH`. Each candidate must report version 3.x;
   binwalk v2 is rejected.

To see what was chosen:

```python
import binwalk

backend = binwalk.get_backend()
print(backend.available, backend.binary_path)
print(binwalk.__binwalk_core_version__)
```

`__binwalk_core_version__` is the bundled binwalk version and upstream commit, for
example `3.1.1+2671397`. If you change `BINWALK3_BINARY` while your program is running,
call `binwalk.reset_backend()` so the next scan searches again.

The bundled executable is built from upstream binwalk commit `2671397` (2026-08-11) with
two small patches. See [docs/BUILDING.md](docs/BUILDING.md).

## Usage

### Scan a file

```python
import binwalk

for module in binwalk.scan("firmware.bin", signature=True, quiet=True):
    for result in module.results:
        print(f"{result.offset:#x}  {result.description}")
```

`scan` returns a list of `Module` objects. Each result has `offset`, `description`,
`size`, `name` (the binwalk v3 signature name, such as `gzip`), `confidence` and `file`.

### Extract

```python
import binwalk

for module in binwalk.scan("firmware.bin", extract=True, directory="out"):
    for result in module.results:
        if result.extraction is not None:
            print(result.offset, result.extraction.success, result.extraction.files)
```

Extracted files go into `out/firmware.bin.extracted/<offset in hex>/`. Without
`directory`, binwalk v3 uses `./extractions`.

The same information is available in the binwalk v2 layout:

```python
import binwalk

module = binwalk.scan("firmware.bin", extract=True, directory="out")[0]
for path, info in module.extractor.output.items():
    for offset, details in info.extracted.items():
        print(path, offset, details.command, details.files)
```

### Extract recursively

```python
import binwalk

module = binwalk.scan("firmware.bin", extract=True, matryoshka=True, directory="out")[0]
for result in module.results:
    print(result.depth, result.file, result.description)
```

Results from extracted files are included in the same module. `result.depth` is 0 for the
file you scanned, 1 for files extracted from it, and so on. `result.file` is the path you
passed in for depth 0 and the extracted file's path for deeper results. `matryoshka=True`
follows binwalk v2 and stops at depth 8; pass an integer, such as `matryoshka=3`, to set a
different limit.

### Carve

```python
import binwalk

module = binwalk.scan("firmware.bin", carve=True, directory="out")[0]
for result in module.results:
    print(result.offset, result.carved)
```

Each match is written to `<directory>/<name>_<offset>_<signature>.raw`.

### Entropy

```python
import binwalk

for module in binwalk.scan("firmware.bin", entropy=True):
    for result in module.results:
        if result.display:
            print(result.offset, result.description)
```

Entropy is calculated in Python with binwalk v2's method: the file is split into about
2048 blocks (each a multiple of 1024 bytes), and each block's Shannon entropy is reported on
a 0 to 1 scale. `result.entropy_bits` gives the same value in bits per byte (0 to 8).
`display` is True for rising and falling edges, as in binwalk v2.

`signature=True, entropy=True` returns a `Signature` module followed by an `Entropy`
module for each file. `entropy=True` alone returns only `Entropy` modules.

To save a graph, add `save=True` (requires matplotlib). The PNG is written to
`<working directory>/<file name>.png`, or into `plot_directory` if you pass one.
binwalk3 never opens a plot window.

### binwalk v2 command line style

```python
import binwalk

modules = binwalk.scan("--signature", "--extract", "--directory", "out", "firmware.bin")
```

Short options (`"-B", "-e", "-C", "out"`) and single-letter keywords (`e=True`) work too.

### Scan bytes in memory

```python
import binwalk

with open("firmware.bin", "rb") as handle:
    data = handle.read()

for result in binwalk.scan_bytes(data, name="firmware.bin")[0].results:
    print(result.offset, result.description)
```

### Multiple files

```python
import binwalk

for module in binwalk.scan("firmware.bin", "other.bin"):
    print(module.file, len(module.results))
```

Each file gets its own `Module`, in the order given.

## Differences from binwalk v2

binwalk3 aims to accept binwalk v2 code, but binwalk v3 is a different program and some
results differ.

- **Descriptions differ.** binwalk v3 writes its own descriptions (for example
  `ZIP archive, version: 2.0, file count: 1, total size: 126 bytes`), and it recognizes a
  different set of formats. Code that matches on exact description text may need updating.
- **One module per file.** binwalk v2 returns one `Signature` module containing results for
  all files. binwalk3 returns one `Signature` module per file (and one `Entropy` module per
  file when entropy is requested). For a single file the shape is the same.
- **`result.module`** is the signature name (`zip`, `gzip`, ...) for signature results and
  `entropy` for entropy results. Use `module.name` for `Signature` or `Entropy`.
- **`result.file`** is a string that also has binwalk v2's `.path` (absolute path) and
  `.name` (path as given).
- **`include` and `exclude`** are regular expressions matched against the lowercased
  description, as in binwalk v2. To choose binwalk v3 signatures by name, use
  `signatures=["zip", "gzip"]` or `exclude_signatures=[...]`.

| binwalk v2 option | Status |
|---|---|
| `-B --signature`, `-e --extract`, `-M --matryoshka`, `-d --depth`, `-C --directory` | Supported |
| `-z --carve` | Supported; also carves data that matches no signature |
| `-E --entropy`, `-F --fast`, `-K --block`, `-H --high`, `-L --low`, `-J --save`, `-Q --nlegend` | Supported |
| `-y --include`, `-x --exclude` | Supported (regex on descriptions) |
| `-q --quiet`, `-v --verbose`, `-t --term`, `-c --csv`, `-N --nplot` | Accepted; they only affect terminal output, which binwalk3 does not produce |
| `-A --opcodes`, `-R --raw`, `-m --magic`, `-b --dumb`, `-I --invalid` | Not supported |
| `-X --deflate`, `-Z --lzma`, `-P --partial`, `-S --stop`, `-Y --disasm`, `-T --minsn`, `-k --continue` | Not supported |
| `-D --dd`, `-j --size`, `-n --count`, `-0 --run-as`, `-u --limit`, `-1 --preserve-symlinks`, `-r --rm`, `-V --subdirs` | Not supported |
| `-W --hexdump` and its display options, `-l --length`, `-o --offset`, `-O --base`, `-g --swap`, `-f --log`, `-a --finclude`, `-p --fexclude`, `-s --status` | Not supported |

An unsupported option is ignored and raises a `binwalk.UnsupportedOptionWarning`. To make
it an error instead:

```python
import warnings

import binwalk

warnings.simplefilter("error", binwalk.UnsupportedOptionWarning)
```

A keyword that is neither a binwalk v2 option nor a binwalk3 option raises
`binwalk.UnknownOptionWarning` and is ignored.

### binwalk3 options

| Keyword | Meaning |
|---|---|
| `signatures` | Only scan for these binwalk v3 signature names |
| `exclude_signatures` | Skip these binwalk v3 signature names |
| `search_all` | Search every offset for every signature |
| `threads` | Number of binwalk v3 worker threads |
| `timeout` | Seconds before the binwalk process is stopped (default 600; `None` waits forever) |
| `plot_directory` | Where `save=True` writes entropy graphs |

## Extraction tools

binwalk v3 extracts 40 formats itself, including gzip, bzip2, xz, lzma, zlib, Android
sparse images, device trees, uImage, TRX and PNG/JPEG/GIF/BMP images.

Other formats are extracted by external programs that must be on `PATH`:

| Program | Formats |
|---|---|
| `7z` (Windows) or `7zz` (Linux, macOS) from 7-Zip | ZIP, 7z, ARJ, APFS, CPIO, CramFS, ISO 9660, EFI GPT, compress'd (.Z) |
| `sasquatch` | SquashFS |
| `jefferson` | JFFS2 |
| `ubireader_extract_files`, `ubireader_extract_images` | UBIFS, UBI |
| `unyaffs` | YAFFS2 |
| `cabextract` | Microsoft Cabinet |
| `dmg2img`, `dumpifs`, `lz4`, `lzop`, `lzfse`, `srec_cat`, `tar`, `tsk_recover`, `uefi-firmware-parser`, `unrar`, `vmlinux-to-elf`, `zstd` | One or a few formats each |

Run `binwalk -L` with the executable from `binwalk.get_backend().binary_path` for the full
list of signatures and the program each one uses.

On Windows, most of these are not available, so those formats are identified but not
extracted. A missing program does not stop the scan: the result's
`extraction.success` is False and the message from binwalk is in `module.warnings`.

## Errors

- A file that cannot be scanned (missing, unreadable, or binwalk exits with an error) is
  reported in that file's `module.errors`. Other files in the same call are still scanned.
- `binwalk.ModuleException` is raised for problems with the call itself: no files given, an
  invalid option value, no usable binwalk executable, or an option the executable does not
  support.
- Extraction raises `ModuleException` if the extraction directory already contains a
  different file with the same name as the target. binwalk v3 would otherwise scan that
  file instead of yours.
- Extraction works across drives on Windows. binwalk v3 links the target into the
  extraction directory, which fails across drives, so binwalk3 copies it there first.

## Building the bundled executable

See [docs/BUILDING.md](docs/BUILDING.md).

## Versions and license

The package version (3.2.0) is separate from the binwalk version it bundles
(`binwalk.__binwalk_core_version__`). `binwalk.__api_version__` is the binwalk v2 API
version it follows (2.3.4).

binwalk3 is released under the MIT license. binwalk is developed by ReFirm Labs and
contributors at <https://github.com/ReFirmLabs/binwalk> and is also MIT licensed.
