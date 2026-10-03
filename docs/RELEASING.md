# Releasing

A release uploads three files to PyPI:

- `binwalk3-<version>.tar.gz`: the sdist, without the executable.
- `binwalk3-<version>-py3-none-win_amd64.whl`: includes the bundled executable.
- `binwalk3-<version>-py3-none-any.whl`: no executable; binwalk is found on `PATH`.

## Prepare

1. Set the version in `pyproject.toml`.
2. Add a dated section to `CHANGELOG.md`.
3. Merge to `master` and wait for CI to pass.

## Publish from a Windows machine

Run from a clean checkout of `master`. The build needs the tools listed in
[BUILDING.md](BUILDING.md).

```
git submodule update --init vendor/binwalk
uv sync --group dev
pwsh -File scripts/build_binary.ps1
uv run pytest
uv build --sdist --out-dir dist/release
uv build --wheel --out-dir dist/release
$env:BINWALK3_PURE_WHEEL = "1"; uv build --wheel --out-dir dist/release; $env:BINWALK3_PURE_WHEEL = $null
uvx twine check dist/release/*
uv publish dist/release/*
```

`uv publish` asks for credentials. Use `__token__` as the username and a PyPI API token as
the password, or set `UV_PUBLISH_TOKEN` first. To try the upload on TestPyPI first, add
`--publish-url https://test.pypi.org/legacy/` and use a TestPyPI token.

Then tag the release:

```
git tag v<version>
git push origin v<version>
```

## Publish from GitHub Actions

`.github/workflows/release.yml` builds, tests and uploads the same three files when a GitHub
release is published. It uses PyPI trusted publishing, which must be set up once on PyPI
under the project's Publishing settings: owner `ZachFlint`, repository `Binwalk3`, workflow
`release.yml`, environment `pypi`. Create a `pypi` environment in the repository settings
as well.

```
git tag v<version>
git push origin v<version>
gh release create v<version> --title v<version> --notes-file <notes>
```

Use only one of the two methods for a given version. PyPI rejects files that already exist.
