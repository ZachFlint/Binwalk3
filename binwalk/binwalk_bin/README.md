# Pre-compiled Binwalk v3 Binaries

This directory contains pre-compiled binwalk v3 binaries for distribution.

## Current Binaries
- `binwalk_windows_x64.exe` - Windows 10/11 64-bit (compiled from binwalk v3.1.0)

## Build Information
- Source: https://github.com/ReFirmLabs/binwalk
- Version: v3.1.0
- Compiler: Rust 1.83+ with MSVC toolchain
- Build command: `cargo build --release --target x86_64-pc-windows-msvc`

## Verification
Run `binwalk_windows_x64.exe --version` to verify binary integrity.
