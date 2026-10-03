#Requires -Version 7.0
[CmdletBinding()]
param(
    [string]$Target = 'x86_64-pc-windows-msvc',
    [string]$CargoTargetDir = (Join-Path $PSScriptRoot '..' 'build' 'cargo-target')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$upstream = Join-Path $repoRoot 'vendor' 'binwalk'
$patchDir = Join-Path $repoRoot 'patches'
$binDir = Join-Path $repoRoot 'binwalk' 'binwalk_bin'
$exeOut = Join-Path $binDir 'binwalk_windows_x64.exe'
$manifestOut = Join-Path $binDir 'manifest.json'

if (-not (Test-Path (Join-Path $upstream 'Cargo.toml'))) {
    throw "Upstream source missing at $upstream. Run: git submodule update --init vendor/binwalk"
}

$status = git -C $upstream status --porcelain
if ($LASTEXITCODE -ne 0) { throw 'git status failed for vendor/binwalk' }
if ($status) { throw "vendor/binwalk has local changes; refusing to build:`n$status" }

$patches = @(Get-ChildItem -Path $patchDir -Filter '*.patch' | Sort-Object Name)
$applied = [System.Collections.Generic.List[string]]::new()

try {
    foreach ($patch in $patches) {
        git -C $upstream apply --check $patch.FullName
        if ($LASTEXITCODE -ne 0) { throw "Patch does not apply: $($patch.Name)" }
        git -C $upstream apply $patch.FullName
        if ($LASTEXITCODE -ne 0) { throw "Failed to apply: $($patch.Name)" }
        $applied.Add($patch.FullName)
        Write-Host "Applied $($patch.Name)"
    }

    $previousRustFlags = $env:RUSTFLAGS
    $env:RUSTFLAGS = (@($previousRustFlags, '-C target-feature=+crt-static') | Where-Object { $_ }) -join ' '
    $env:CARGO_TARGET_DIR = $CargoTargetDir
    try {
        cargo build --release --locked --target $Target --manifest-path (Join-Path $upstream 'Cargo.toml')
        if ($LASTEXITCODE -ne 0) { throw "cargo build failed with exit code $LASTEXITCODE" }
    }
    finally {
        $env:RUSTFLAGS = $previousRustFlags
    }

    $built = Join-Path $CargoTargetDir $Target 'release' 'binwalk.exe'
    if (-not (Test-Path $built)) { throw "Build output not found: $built" }

    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    Copy-Item -LiteralPath $built -Destination $exeOut -Force

    $versionOutput = (& $exeOut --version).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Built binary failed to report its version' }
    if ($versionOutput -notmatch '^binwalk (\d+\.\d+\.\d+)$') { throw "Unexpected version output: $versionOutput" }

    $manifest = [ordered]@{
        binwalk_version = $Matches[1]
        upstream_commit = (git -C $upstream rev-parse HEAD).Trim()
        upstream_commit_date = (git -C $upstream log -1 --format=%cs).Trim()
        patches = @($patches | ForEach-Object { $_.Name })
        target = $Target
        rustc = (rustc --version).Trim()
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $exeOut).Hash.ToLowerInvariant()
        size = (Get-Item -LiteralPath $exeOut).Length
        built_at = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
    $json = $manifest | ConvertTo-Json -Depth 3
    [IO.File]::WriteAllText($manifestOut, $json + "`n", [Text.UTF8Encoding]::new($false))

    Write-Host "Built $exeOut"
    Write-Host $json
}
finally {
    for ($i = $applied.Count - 1; $i -ge 0; $i--) {
        git -C $upstream apply -R $applied[$i]
        if ($LASTEXITCODE -ne 0) { Write-Warning "Failed to revert $($applied[$i])" }
    }
}
