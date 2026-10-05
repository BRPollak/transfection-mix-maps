# Excel output formatting verification

Verified October 5, 2026. Source update only; no installer was built, installed,
or published for these formatting changes.

## Automated checks

- `.venv/bin/python -m pytest -q`: **416 tests passed**.
- `UV_CACHE_DIR=/private/tmp/mixmap-formatting-uv-cache uv lock --check --offline`:
  passed; dependency versions are unchanged.
- `git diff --check`: passed.

Coverage includes all six layouts with LT1 and L2000, both 96-well halves,
bold well identifiers, retained large bulk-mix symbols, neutral grayscale
throughout the workbook, blank grid corner labels, and source-free subtitles.
Rounding checks cover each pipette increment, precision band, boundary crossing,
half-up tie, zero, and tiny positive volumes. Export checks confirm printed
warning examples use original numeric values while calculations, supporting
numeric tables, source labels, and diagnostic text retain their existing values.

## Rendered workbook review

Generated fresh synthetic workbooks through the application exporter and
imported them into Artifact Tool for visual inspection. Reviewed dense 96-well
maps (both halves), dense 48-well maps, and single-well maps for both reagents,
plus a sparse 48-well L2000 map and a printable bulk recipe. Bold well IDs, regular recipe text, large mix
symbols, readable rounded amounts, wrapping, and the active/empty/header gray
hierarchy rendered correctly without clipping or overlap.

Synthetic workbooks, render scripts, and PNG evidence are retained in the
ignored `build/mixmap-formatting/visual-checks/` directory.

These are worksheet renders, not native Excel print or PDF checks. Native Excel
automation stalled during app discovery and was aborted. Print geometry,
merged dish cells, page areas, and landscape Letter settings passed automated
checks; native pagination and physical printing were not reverified.

# v1.0.1 source verification

Verified October 4, 2026. This is a tested source update; no v1.0.1 installer
was built, installed, or published.

## Automated checks

- `.venv/bin/python -m pytest -q`: **373 tests passed**.
- `UV_CACHE_DIR=/private/tmp/mixmap-v101-uv-cache uv lock --check --offline`:
  passed; dependency versions are unchanged.
- `git diff --check`: passed.
- App, project, lockfile, and native launcher fallback report **1.0.1**.
  The package manifest includes the shared plate-format definitions.

Coverage includes all six geometries and their row/column boundaries in wide
and long CSVs, canonical well names, blank/zero unsupported wells and duplicate
unused template rows, retained malformed-input checks, and complete batch
rejection for unsupported positive DNA. UI checks cover the fresh-session
48-well default, session-only plate type, revalidation of retained CSVs, stale
result removal, and full-sized preview/result grids.

Workbook checks cover exact physical well positions, both 96-well map tabs even
when one half is empty, shared whole-plate recipes and symbols, print settings,
geometry provenance, merged dish cells, literal source text, and unchanged
LT1/L2000 calculation and Generate/Download behavior.

## Native Excel print checks

Generated synthetic two-plasmid fixtures for each format. Opened and exported
the following maps through Microsoft Excel's native Print / Save as PDF dialog,
then rendered the PDFs with Poppler and inspected them:

- Dense 96-well L2000 maps, both A-D and E-H, with five DNA-mass groups and long
  plasmid names; each half is one landscape Letter page with the same whole-plate
  recipes and clear prepare-once instructions.
- Dense 96-well LT1 top half, with readable wrapped component lines.
- Six-well L2000 map with five groups and preparation warnings.
- Single-well LT1 and L2000 maps, with one labeled A1 recipe.

The initial dish layout exposed Excel clipping an oversized single column.
The final layout merges normal-width columns into one well; fresh native PDF
exports confirmed the complete title, instructions, recipe, and borders print.
Regression tests cover that structure for both reagents.

Synthetic fixtures and local visual evidence are retained in the ignored
`build/v1.0.1/visual-checks/` directory. The final dish evidence uses the
`plate-1-LT1-fixed` and `plate-1-L2000-fixed` filenames; the earlier dish PDF
records the issue found during verification.

## Verification limits

No physical printouts, live Google authorization, real CSV/folder picker flow,
or installer upgrade was tested for v1.0.1. Automated UI tests simulate Google
access and native choices. Interactive previews are covered by HTML and
Streamlit tests; a browser visual check was not completed. Native print review
sampled the formats listed above; all supported geometries have structural
workbook tests.

# v1.0.0 verification (historical)

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
