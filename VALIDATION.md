# v1.0.5 source verification

Verified October 8, 2026. This is a source-only update for CSV column validation
and distinguishable printed stock names. No installer was built, installed,
or published.

## Automated checks

- `.venv/bin/python -m pytest -q -k 'not test_real_installer_replaces_only_app_and_requires_quit'`:
  **500 passed, 1 deselected**. The excluded test builds a synthetic installer
  and was deliberately omitted for this update.
- `UV_CACHE_DIR=/private/tmp/mixmap-v105-uv-cache uv lock --check --offline`:
  passed; dependency versions are unchanged.
- `git diff --check`: passed.
- App, project, lockfile project entry, and native launcher fallback report
  **1.0.5**. The existing v1.0.3 installer link remains available.

CSV regressions exercise orphan mass headers with positive, zero, and blank
amounts; duplicate exact and normalized plasmid headers before pandas renames
them; leading-zero slots; and reordered, nonadjacent, and legacy valid pairs.
Errors identify missing or duplicated headers before workbook creation.
Interface tests verify that invalid layouts disable generation, show the
offending headers, and clear old results. Results cached under calculation
revision 4 also require regeneration without altering saved workbooks.

Workbook regressions cover full names differing at their suffixes or in the
middle, multiple stocks in one well, names repeated across wells and both
96-well map halves, literal names matching former shortened labels, and
formula-like identifiers. Row sizing accounts for wrapped text and embedded
newlines; recipes exceeding Excel's 409-point row limit fail with the CSV name,
map section, and affected row/wells instead of clipping identifiers.

## Rendered workbook review and limits

Generated fresh synthetic workbooks through the exporter and reviewed worksheet
renders for a dense 96-well L2000 plate (both halves), a dense 48-well LT1 plate,
and a single-well LT1 map. Complete names with shared prefixes and differing
endings remain visible with wrapping, readable component lines, and retained
bulk-mix symbols. Fixtures, render scripts, and PNG evidence are retained in
the ignored `build/v1.0.5/visual-checks/` directory.

These are worksheet renders, not native Excel print/PDF checks. Native
pagination and physical printing were not exercised. No native launcher or
installer was built.

# v1.0.4 source verification

Verified October 8, 2026. This is a source-only update for Google sign-in retry
handling and account switching. No installer was built, installed, or published.

## Automated checks

- `.venv/bin/python -m pytest -q -k 'not test_real_installer_replaces_only_app_and_requires_quit'`:
  **458 passed, 1 deselected**. The excluded test builds a synthetic installer;
  it was deliberately omitted to avoid packaging an installer for this update.
- `UV_CACHE_DIR=/private/tmp/mixmap-v104-uv-cache uv lock --check --offline`:
  passed; dependency versions are unchanged.
- `git diff --check`: passed.
- App, project, lockfile project entry, and native launcher fallback report
  **1.0.4**. The README retains the available v1.0.3 installer link.

Authentication checks exercise explicit confirmation, expired-token refresh,
and refresh during a Sheet request. Temporary, unrecognized, transport, and
retryable errors preserve local tokens, authentication metadata, and cached
concentrations, and a later retry succeeds without opening OAuth. Confirmed
nonretryable `invalid_grant` errors still require a new sign-in. Raw provider
error details are not shown to users.

Account-switch checks cover the account-selection prompt, read-only Sheets
scope, replacing the authentication session after success, rejecting the old
session's concentrations, clearing prior workbook results, and enabling
generation after a fresh Sheet refresh. Cancellation and unusable OAuth
responses preserve the prior account. Interface checks also confirm that
checking sign-in alone does not dismiss a failed Sheet-access check.

## Verification limits

Google responses and browser authorization are simulated in automated tests;
live Google account selection and consent were not exercised. No native
launcher or installer was built for this source update.

# v1.0.3 release verification

Verified October 5, 2026. The release packages the Excel formatting changes,
all six plate formats, and the current source as a self-contained Apple Silicon
installer for macOS 14 or later.

## Source and bundled runtime

- Full source suite: **416 tests passed** after the version update.
- Offline lockfile and `git diff --check`: passed; dependencies are unchanged.
- App, project, lockfile, and native launcher fallback report **1.0.3**.
- Isolated Python 3.12.14 build environment: all 49 production dependencies
  match the lockfile, with no inherited or development packages.
- Bundled LT1 and L2000 interface checks: passed using temporary synthetic
  state, including Generate/Download behavior and all six plate formats.
- Bundled workbook checks confirm grayscale, bold well IDs, pipette rounding,
  preserved calculation precision, and both 96-well map tabs.

## Installer verification

Package checks passed for the fixed `/Applications/Transfection Mix Maps.app`
destination, complete bundle upgrades, disabled relocation, the matching-app
quit requirement, arm64 binaries, portable runtime links, source/documentation/
icon parity, strict ad hoc signature, checksum, and privacy exclusions. The
payload contains no user settings, credentials, generated workbooks, or install
scripts. The final package is checked again after incorporating these notes.

Release assets: [v1.0.3](https://github.com/BRPollak/transfection-mix-maps/releases/tag/v1.0.3).
The installer, SHA-256 checksum, and release metadata identify the exact source
commit and verification results. Build reports are retained locally under
`build/v1.0.3/checks/`; installers are under `dist/v1.0.3/` outside Git history.
Local upgrade verification is recorded separately from package validation,
including the installed version, receipt, payload parity, and unchanged
Application Support metadata before relaunching.

## Visual review and limits

The worksheet renders described below were reviewed, plus a six-well L2000
example. Native Excel automation stalled, so this release's pagination and
physical printing were not reverified. Live Google authorization and real
native file/folder pickers were not retested. The app is ad hoc signed; the
installer is unsigned and the app is not Developer ID signed or notarized.

# Excel output formatting verification (source-stage history)

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
plus a sparse 48-well L2000 map and a printable bulk recipe. Bold well IDs,
regular recipe text, large mix symbols, readable rounded amounts, wrapping, and the active/empty/header gray
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
