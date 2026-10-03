# Building the bundled executable

The Windows x64 wheel contains `binwalk/binwalk_bin/binwalk_windows_x64.exe`, built from the
upstream binwalk source in `vendor/binwalk` (a git submodule). The executable and its
`manifest.json` are build outputs and are not committed.

## Requirements

- Windows x64
- PowerShell 7 (`pwsh`)
- Rust with the `x86_64-pc-windows-msvc` target, and the Visual Studio C++ build tools
- Git

## Build

```
git submodule update --init vendor/binwalk
pwsh -File scripts/build_binary.ps1
```

The script:

1. Refuses to run if `vendor/binwalk` has local changes.
2. Applies every file in `patches/` in name order.
3. Runs `cargo build --release --locked --target x86_64-pc-windows-msvc` with
   `-C target-feature=+crt-static`, so the executable does not need the Visual C++ runtime.
   Build output goes to `build/cargo-target`.
4. Copies the executable to `binwalk/binwalk_bin/binwalk_windows_x64.exe`.
5. Writes `binwalk/binwalk_bin/manifest.json` with the binwalk version, upstream commit,
   patches, Rust version, SHA-256 and size.
6. Reverts the patches, even if the build failed.

A clean build takes about two minutes.

## Patches

- `0001-disable-kaleido-download.patch` turns off plotly's `kaleido_download` feature.
  With it on, plotly's build script runs `cargo install` from inside the build, which
  deadlocks on cargo's package lock. binwalk3 calculates entropy in Python and never runs
  `binwalk -E`, so Kaleido is not needed.
- `0002-use-7z-on-windows.patch` makes Windows builds call `7z` instead of `7zz` for ZIP,
  7z, ISO and the other formats 7-Zip extracts. 7-Zip for Windows installs `7z.exe`; `7zz`
  is the Linux and macOS name. The arguments are the same.

## Updating upstream

```
git -C vendor/binwalk fetch
git -C vendor/binwalk checkout <commit>
pwsh -File scripts/build_binary.ps1
```

If a patch no longer applies, the script stops and names it. Regenerate it against the new
commit with `git diff` in `vendor/binwalk`, then run the tests. Update the commit mentioned
in `README.md`.

## Wheels

```
uv build --sdist --out-dir dist
uv build --wheel --out-dir dist
```

`uv build --wheel` builds from the source tree, so the wheel includes the executable and is
tagged `py3-none-win_amd64`. To build the platform-independent wheel (no executable;
binwalk is found on `PATH`), set `BINWALK3_PURE_WHEEL=1`:

```
$env:BINWALK3_PURE_WHEEL = "1"; uv build --wheel --out-dir dist
```

The sdist never includes the executable.

## Tests against binwalk 3.1.0

Some tests check that older binwalk executables still work: binwalk 3.1.0 uses different
command line flags and writes a malformed JSON log on Windows. They run when
`BINWALK3_LEGACY_BINARY` points to a binwalk 3.1.0 executable:

```
git -C vendor/binwalk worktree add ../../build/binwalk-3.1.0 v3.1.0
cargo build --release --manifest-path build/binwalk-3.1.0/Cargo.toml
$env:BINWALK3_LEGACY_BINARY = "build/binwalk-3.1.0/target/release/binwalk.exe"
```
