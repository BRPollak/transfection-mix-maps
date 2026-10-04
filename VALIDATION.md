# Version 0.1 validation

Updated October 4, 2026.

## Current app revision

- **104 automated tests pass**: 14 interface/version tests, 39
  source/authentication/state-location tests, 24 native-dialog tests, and 27
  workflow tests.
- Version `0.1` is consistent across the visible app label, browser title, launcher
  output, project metadata, and lockfile. The offline lockfile check passed.
- Workflow checks cover known LT1/L2000 volumes, wide/long plate CSV equivalence,
  duplicate/missing concentration failures, impossible volumes, non-finite inputs,
  Google worksheet provenance, repeated-run preservation, and exported warnings.
- Output checks cover direct saves into an existing selected folder, unique
  filenames, preservation of previous files during name collisions, rejection of
  missing folders without creating them, and temporary-file cleanup after errors.
  Generation creates no output directories or JSON sidecars.
- The L2000 default is now 25 µL. Tests cover its known volumes at that setting
  and migration from the previous 1,500 µL default while preserving other custom
  values. Conflicting concentrations anywhere in the Sheet stop generation;
  there is no user-selectable duplicate policy.
- Interface checks cover the native plate-file chooser, automatic selection of
  the plate's parent folder for output, a manual folder override, and resetting
  that override when another plate is selected.
- Every generation is restricted to one transfectant, LT1 or L2000. Tests confirm
  combined, empty, repeated, and unsupported selections fail before publishing output.
- Synthetic plate and concentration inputs live in `tests/fixtures/`. Production
  workflow has no demonstration mode, demonstration output names, or demonstration
  result field.
- Opened the current app in a local Chrome preview and confirmed an
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

## Mac app package

The v0.1 package targets Apple Silicon and macOS 14 or later. It bundles Python
and dependencies, launches from a small native window, and opens the local browser
interface without Terminal or uv. Closing or quitting that window stops the local
server. Packaged settings and Google credentials are stored outside the app under
`~/Library/Application Support/Transfection Mix Maps/local_state/`.

The following package checks passed:

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

This is an initial test release using local ad hoc signing. It is not Developer ID
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
claim that the new default produces the old default's outputs. The calculation
methods and Excel layout functions remain unchanged.

The previous warm-process local trial generated the two reagent workbooks in
0.191 seconds. That historical synthetic benchmark excludes startup, file
selection, and Google refresh. It is not a new performance measurement of this
revision or of the user's inputs.
