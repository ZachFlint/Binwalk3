# Changelog

All notable changes to binwalk3 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] - 2026-10-02

### Changed
- The bundled Windows executable is built from upstream binwalk commit `2671397`
  (2026-08-11, version 3.1.1) instead of the v3.1.0 release from October 2024. It is built
  with the MSVC toolchain and a static C runtime and is about half the previous size.
- The Windows wheel is tagged `win_amd64`. Other platforms get a wheel without the
  executable and use binwalk v3 from `PATH`.
- Python 3.9 is the minimum version. 3.1.3 declared 3.8 support but failed to import on it.
- Entropy is calculated in Python using binwalk v2's method (0 to 1 scale, edge detection,
  `-K`, `-H`, `-L`, `-F`). binwalk v3's `-E` opens a browser window and needs Kaleido.
- binwalk v3 is always called with long options, so binwalk 3.1.0 and newer executables on
  `PATH` both work.

### Fixed
- `entropy=True` returned no results.
- `matryoshka=True` returned no results and a JSON parse error.
- Only the first file's analysis was read from the binwalk log; results from extracted files
  were dropped.
- binwalk v2 was accepted as v3 because its version string contains "3.".
- Extraction into a directory on a different drive failed on Windows.
- Extraction silently scanned a stale file when the extraction directory already contained
  a different file with the same name. This now raises `ModuleException`.
- ZIP, 7z, ISO and other 7-Zip formats were not extracted on Windows by the upstream build,
  which calls `7zz`. The bundled executable calls `7z`.
- Scans no longer flash a console window when called from a GUI application.

### Added
- binwalk v2 attributes: `Module.name`, `Module.extractor.output`, `Result.file.path` and
  `.name`, `Result.valid`, `display`, `extract`, `plot`.
- binwalk v2 calling styles: command line options as strings, single-letter keywords, the
  `Modules(...)` context manager, and `binwalk.execute`.
- `include`/`exclude` regular expression filters with binwalk v2 semantics.
- `carve`, `search_all`, `signatures`, `exclude_signatures`, `timeout` and
  `plot_directory` options.
- `binwalk.scan_bytes` for data in memory.
- Result fields `name`, `id`, `confidence`, `extraction`, `carved`, `depth` and
  `entropy_bits`; `Module.warnings` with messages logged by binwalk.
- `BINWALK3_BINARY` environment variable and `binwalk.reset_backend()`.
- `UnsupportedOptionWarning` for binwalk v2 options with no binwalk v3 equivalent, and
  `UnknownOptionWarning` for unrecognized keywords.

## [3.1.3] - 2025-10-20

- `binwalk.scan()` and `Modules().execute()` with binwalk v2 style arguments, returning one
  `Module` per scanned file.
- Bundles the binwalk 3.1.0 executable for Windows x64. Other platforms use `binwalk` from
  `PATH`.

[3.2.0]: https://github.com/ZachFlint/Binwalk3/releases/tag/v3.2.0
[3.1.3]: https://pypi.org/project/binwalk3/3.1.3/
