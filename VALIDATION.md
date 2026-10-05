# v1.0.0 verification

Verified October 4, 2026. The source baseline is GitHub's merged v0.3
(`66712f2` on `main`).

## Automated source checks

- `.venv/bin/python -m pytest -q`: **248 tests passed**, including 25 interface
  tests and six packaging/version checks.
- `uv lock --check --offline`: passed with an isolated writable cache.
- `git diff --check`: passed.
- App, project, lockfile, native launcher fallback, and installer use **1.0.0**.
  Dependency versions are unchanged.

The suite covers calculations and input validation, Google connection handling,
settings, plate previews, Excel formatting, and native-dialog wrappers. Tests
check matching L2000 symbols in previews and workbooks, preparation overages,
five-mix limits, literal source labels, and plate-specific preview switching.

Generation and save checks cover in-memory generation without workbook files,
Download to the currently selected folder, folder changes without regeneration,
individual batch downloads, unavailable folders, save failures and retries,
filename collisions, and temporary-file cleanup warnings.

Installer tests exercise the actual macOS package metadata: fixed Applications
destination, complete bundle replacement, application-quit requirement, version
consistency, and exclusion of unrelated/private files. The builder rejects stale
application sources and dependencies inherited from another Python environment.

## Installer evidence

Release assets are available from [v1.0.0](https://github.com/BRPollak/transfection-mix-maps/releases/tag/v1.0.0):

- `Transfection-Mix-Maps-1.0.0-arm64.pkg`
- `Transfection-Mix-Maps-1.0.0-arm64.pkg.sha256`
- `Transfection-Mix-Maps-1.0.0-release.json`

The release metadata records the exact source commit, installer checksum, and
bundle/package verification results. Local check scripts and detailed reports
are retained under `build/v1.0.0/checks/`; local artifacts are in `dist/v1.0.0/`.
These generated directories are excluded from Git.

Package verification checks source and documentation parity, version and app
identity, Apple Silicon executables, a strict ad hoc signature, portable runtime
paths, locked production dependencies, and absence of private state or generated
workbooks. It also verifies the bundled PNG and macOS icon resources.
Bundled-runtime checks use synthetic inputs and temporary settings
for LT1/L2000 generation and the Generate/Download interface.

The `.pkg` targets Apple Silicon Macs running macOS 14 or later and installs to
`/Applications/Transfection Mix Maps.app`. It preserves Application Support,
contains no install/uninstall scripts, and requires the application to close.
The installer is unsigned; the app has an ad hoc signature and is not Developer
ID signed or notarized.

## Manual verification scope

This revision has not been installed over the running application or checked
with live Google authorization, real native file/folder pickers, or physical
printouts. Automated interface checks simulate Google access and native choices.

For a hands-on check, install the package, confirm version 1.0.0, refresh the
Google Sheet, select one and several plate CSVs, and verify that Generate creates
no Excel files while Download saves to the selected folder. Check a multi-mix
L2000 printout and confirm that sign-in and settings remain after reopening.

Earlier v0.3 local builds received digital print-layout and browser checks, and
the shapes build was installed with preserved settings. Those historical checks
do not substitute for hands-on verification of the v1.0.0 installer.
