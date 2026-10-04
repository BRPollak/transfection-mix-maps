# Version 0.3 validation

Updated October 4, 2026.

## Version 0.3 source verification

All **206 automated tests pass** with `.venv/bin/python -m pytest -q`, including
**21 interface tests**. `git diff --check` also passes.

App, project, lockfile, and launcher fallback agree on **0.3**. The bundle builder
uses the same app version for its metadata. `uv lock --check --offline` passes
without changing dependency versions.

The current revision adds regression coverage for grouped L2000 recipes and
their well assignments, a maximum of five distinct positive DNA totals per
plate, uniform overage factors, and preparation versus delivery instructions.
Input regression cases cover canonical well coordinates, column zero,
malformed masses and unsupported units, populated rows missing wells,
ambiguous concentration columns, identifier preservation, and literal Excel
labels. Interface checks exercise mixed-mass results and failure without new
output when a plate exceeds the five-group limit.

Synthetic 48-well LT1 and five-mix L2000 workbooks were rendered through
LibreOffice to Letter-landscape PDFs and visually inspected. The L2000 map and
recipe sheet were also inspected in grayscale: every populated well carries its
full numbered mix name and aliquot, and each recipe lists its assigned wells.
Identification does not depend on color. Preparation/delivery instructions,
five-mix legends, and all 48 well labels were readable without clipping in these
fixtures. This is digital print-layout verification, not a physical print test
or a claim of identical rendering in every spreadsheet application.

Live Google sign-in, real native picker interactions, and physical printouts
remain unverified for this revision. No v0.3 installer has been built or tested.
The historical checks below do not imply packaged verification of these changes.

## Version 0.2 source verification (historical)

- **99 automated tests passed** with `.venv/bin/python -m pytest -q`, covering
  the interface, plate preview, Google source handling, workflow, and native
  dialog wrappers.
- App, project, and lockfile versions agreed on `0.2`; the offline lockfile check
  passed. All nine allowlisted app/configuration files exist for future packaging.
- Sheet scans no longer block on unrelated tabs or incomplete unused stocks.
  Tests cover absent, blank, invalid, and conflicting plate-used concentrations,
  aggregated errors, exact and case-insensitive matching, and no file creation
  when concentration validation fails. Successful LT1/L2000 exports still pass.
- Interface tests confirm one compact generation error, cleared previous results,
  preview population without Google sign-in, and clearing the preview when a
  newly selected plate is invalid.
- The suite was reduced from 175 to 99 cases by removing cosmetic wording checks,
  obsolete single-file chooser coverage, and redundant helper-level cases already
  covered by actual workbook generation or the active multi-file workflow.
- Multi-plate checks cover the five-file limit, cancellation, required manual
  folder selection for each new batch, returning to single-plate folder defaults,
  preview switching without invalidating results, and duplicate input filenames.
  Workbooks are staged before publication; failures preserve pre-existing files
  and attempt to roll back newly published batch workbooks. If rollback cannot
  remove an output, the error identifies the remaining file. Cleanup failures
  are reported without falsely claiming that successful outputs do not exist.
- Browser checks with two synthetic layouts confirmed the filename dropdown in
  the preview's top-right corner, switching from A1/A2/B1/B2 to C4/F8, the filenames
  and paths above the preview, and the prompt to manually choose an output folder.
- The multi-file native AppleScript compiled successfully. Foundation JSON
  serialization was checked with paths containing quotes and newlines; automated
  dialog tests cover invalid and unreadable selections as well as the five-file limit.
- Browser inspection verified a fixed A–F / 1–8 grid with 48 circles, 5 purple
  DNA wells and 43 inert grey wells using synthetic inputs. Popups for A1 and F8
  displayed the expected plasmid names and masses without clipping. No browser
  console errors were reported. Empty-preview rendering and setting labels were
  also inspected in the unmodified app entry point.
- Populated browser checks used a temporary fixture-seeded wrapper; automated
  picker tests use simulated native selections. Live Google authentication and
  real native file selection remain outside this revision's verification scope.
- That revision was the v0.2 source update. No v0.2 installer was built or tested.
  The packaging allowlist includes `plate_preview.py` for a future build. All
  packaged-app checks below refer only to the published v0.1 build.

## Published v0.1 validation (historical)

- **104 automated tests passed**: 14 interface/version tests, 39
  source/authentication/state-location tests, 24 native-dialog tests, and 27
  workflow tests.
- Version `0.1` was consistent across the visible app label, browser title, launcher
  output, project metadata, and lockfile. The offline lockfile check passed.
- Workflow checks cover known LT1/L2000 volumes, wide/long plate CSV equivalence,
  duplicate/missing concentration failures, impossible volumes, non-finite inputs,
  Google worksheet provenance, repeated-run preservation, and exported warnings.
- Output checks cover direct saves into an existing selected folder, unique
  filenames, preservation of previous files during name collisions, rejection of
  missing folders without creating them, and temporary-file cleanup after errors.
  Generation creates no output directories or JSON sidecars.
- The L2000 default changed to 25 µL. Tests covered its known volumes at that setting
  and migration from the previous 1,500 µL default while preserving other custom
  values. At v0.1, conflicting concentrations anywhere in the Sheet stopped
  generation; v0.2 limits these checks to plasmids used by the selected plates.
- Interface checks cover the native plate-file chooser, automatic selection of
  the plate's parent folder for output, a manual folder override, and resetting
  that override when another plate is selected.
- Every generation is restricted to one transfectant, LT1 or L2000. Tests confirm
  combined, empty, repeated, and unsupported selections fail before publishing output.
- Synthetic plate and concentration inputs live in `tests/fixtures/`. Production
  workflow has no demonstration mode, demonstration output names, or demonstration
  result field.
- Opened the v0.1 app in a local Chrome preview and confirmed an
  error-free single-page interface titled **Generate transfection mix maps**,
  the **Choose plate CSV…** button, L2000 selected with a 25 µL default, no
  duplicate-policy option, direct-save wording, and the exact footer
  **Benjamin Pollak | brpollak@uscd.edu**. Only LT1/L2000 choices appear, and
  reagent-specific settings remain in the main page without a sidebar.
- Automated native-dialog tests use simulated selections. Real plate-file and
  folder selections have not been verified end to end: the computer-use interface
  could not inspect the macOS NSOpenPanel service that owns these dialogs.

Live Google OAuth and access to the user's actual concentration Sheet have not
been tested: a desktop OAuth client and user authorization are still needed.
See README.md and the app's first-time Google setup instructions.

## Published v0.1 Mac app package (historical)

The v0.1 package targets Apple Silicon and macOS 14 or later. It bundles Python
and dependencies, launches from a small native window, and opens the local browser
interface without Terminal or uv. Closing or quitting that window stops the local
server. Packaged settings and Google credentials are stored outside the app under
`~/Library/Application Support/Transfection Mix Maps/local_state/`.

The following checks passed for the published v0.1 package:

- A relocated standalone bundle imported all app dependencies using its bundled
  CPython 3.12.14 runtime.
- The bundled runtime generated separate LT1 and L2000 test workbooks.
- The local server health endpoint responded successfully, and SIGTERM shutdown
  cleaned up its server process.
- Opening the native `.app` displayed its ready window and an error-free v0.1
  browser interface. Quitting the native app stopped its local server; the tested
  server ports refused connections afterward.
- Deep, strict verification of the bundle's ad hoc signature passed.
- The bundle contains exactly the eight allowlisted app/configuration files,
  with no `local_state`, generated workbooks, or tests. All bundled symlinks stay
  inside `Contents/Resources`.

The disk-image builder runs integrity verification and emits a separate SHA-256
checksum file. The [v0.1 release report](https://github.com/BRPollak/transfection-mix-maps/releases/download/v0.1/Transfection-Mix-Maps-0.1-release.json)
records the final disk-image result.

The v0.1 package was an initial test release using local ad hoc signing. It is not Developer ID
signed or notarized. Gatekeeper may display an alert; see
[Apple's opening instructions](https://support.apple.com/102445).

Live Google sign-in and real native file/folder-picker interactions have not been
verified end to end in the packaged app.

## Preserved notebook comparison

Before this interface revision, the adapted core was compared against functions
extracted directly from the original Colab notebook on a synthetic plate with
48 wells and 84 plasmid entries. Both reagents produced identical numerical tables,
bulk totals, and warnings. For each reagent, 1,406 Excel cells and their styles
matched; two intentionally changed source-description labels were excluded from
the value comparison. That comparison used the notebook's original configurations,
including the 1,500 µL L2000 default. The current 25 µL L2000 default was explicitly
requested and changes the resulting volume values. The historical parity result
applies when both implementations receive the same configuration; it is not a
claim that the new default produces the old default's outputs. The v0.3
grouped L2000 calculations and workbook layout now differ from the historical
notebook; that comparison does not validate the newly changed behavior.

The previous warm-process local trial generated the two reagent workbooks in
0.191 seconds. That historical synthetic benchmark excludes startup, file
selection, and Google refresh. It is not a new performance measurement of this
revision or of the user's inputs.
