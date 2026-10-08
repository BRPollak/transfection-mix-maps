# Development and packaging

The installed Mac app includes Python and its dependencies. These instructions
are for working on the source or building an installer.

The current source is **v1.0.4**, a source-only update. No v1.0.4 installer has
been built or published. The available **v1.0.3** installer is self-contained
and supports Apple Silicon Macs running macOS 14 or later. The optional build
commands below show how to package the current source for a future release.

## Run from source

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). From the repository folder:

```sh
uv sync --locked --python 3.12
uv run python launch.py
```

Alternatively, double-click `Start Mix Maps.command`. Keep the launcher or
Terminal open while using the app; quitting it stops the local server.

Source runs keep private settings in `local_state/`. The installed app uses
`~/Library/Application Support/Transfection Mix Maps/local_state/`.
Set `MIXMAP_STATE_DIR` to a separate folder for testing with synthetic data.
Never commit or package credentials, tokens, or personal settings.

## Test

```sh
uv run pytest -q
uv lock --check --offline
git diff --check
```

The suite covers calculations, workbook exports, previews, generation and
explicit downloads, Google connection handling, settings, native-dialog
wrappers, version consistency, and installer policy. macOS package tests require
Apple's packaging tools. See [VALIDATION.md](VALIDATION.md) for verification
scope and manual checks.

## Build the Mac installer

Use an Apple Silicon Mac with macOS 14 or later and Apple's command-line
developer tools. Build in an isolated environment containing the locked
production dependencies:

```sh
UV_PROJECT_ENVIRONMENT=build/package-env uv sync --locked --no-dev --python 3.12
build/package-env/bin/python packaging/build_macos.py \
  --staging build/v1.0.4/staging \
  --pkg dist/v1.0.4/Transfection-Mix-Maps-1.0.4-arm64.pkg
```

Use fresh staging and output paths for each rebuild; existing outputs are not
overwritten. The builder rejects dependencies inherited from another Python
installation, packages only approved application files, and verifies the app's
ad hoc signature. It writes a `.pkg.sha256` checksum beside the installer.

`--bundle-only` builds just the app. `--package-only` packages an existing staged
app after checking its version and source files. `--dmg` can create an optional
drag-and-drop disk image.

The `.pkg` installs to `/Applications/Transfection Mix Maps.app` and replaces
the complete application bundle. It requires the app to close and preserves
Application Support data. Building does not install the app. This installer is
unsigned; the app has an ad hoc signature and is not notarized.

## Prepare a release

Keep `app_version.py`, `pyproject.toml`, the root project entry in `uv.lock`, and
the launcher fallback in `packaging/Launcher.swift` at the same version.
Run the checks against the final source. For a source-only update, skip the
installer build and keep the existing installer link. For an installer release,
build from the final source and verify the bundled runtime and package before
uploading the installer, checksum, and release metadata to the matching GitHub
release. Update the README's versioned installer link only when that installer
is published; keep source-only updates explicitly identified.
Keep binary installers in release assets, outside Git history.

## Source layout

- `app.py`: interface and session state.
- `core.py`: parsing, calculations, and Excel layout.
- `workflow.py`: batch validation, in-memory generation, and explicit saves.
- `plate_formats.py`: shared plate types, geometry, and supported well coordinates.
- `plate_preview.py`: the interactive preview for the selected plate geometry.
- `sources.py`: Google Sheets, concentration snapshots, and settings.
- `native_dialogs.py`: local file and folder selection.
- `packaging/`: native launcher and macOS installer builder.
- `tests/`: regression tests and synthetic fixtures.
