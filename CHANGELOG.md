# Changelog

## 1.0.3 — October 5, 2026

- Bold the well identifier in each printable recipe and use grayscale throughout
  Excel workbooks. Keep DNA wells lightest, empty wells darker, and row/column
  labels slightly darker; preserve bulk-mix symbols and plate geometry.
- Apply pipette-aware volume rounding to Mix Maps and printable bulk recipes,
  including preparation instructions and warning examples. Use increments of
  0.002, 0.01, 0.02, 0.2, or 1 µL according to the original volume, with exact
  halfway values rounded upward. Calculations and supporting numeric tables
  retain their existing precision.
- Remove the grid's "Row" corner label and concentration-source text from Mix
  Map subtitles. Retain source provenance in supporting sheets.
- Release a self-contained v1.0.3 installer for Apple Silicon Macs on macOS 14
  or later, including all six plate formats from v1.0.1. Keep starter templates
  and instructions for adapting the CSV template to each plate type in the
  README. Updates preserve saved Google sign-in and preferences.

## 1.0.1 — October 4, 2026

Source update. No v1.0.1 installer has been built or published; the available
installer remains v1.0.0.

- Add one required plate type for the whole batch: 96-well (8 × 12), 48-well
  (6 × 8), 24-well (4 × 6), 12-well (3 × 4), 6-well (2 × 3), and single well
  (dish, A1). Start each new app session at 48-well without saving this selection
  in preferences. Type changes retain CSVs, revalidate them, and clear results.
- Keep wide and long CSV schemas and normalized well names. Ignore unsupported
  wells with blank or valid-zero DNA entries, including duplicate unused rows;
  report source rows with positive DNA outside the selected geometry. Preserve
  malformed-input checks and require positive DNA to generate recipes.
- Show the complete selected geometry in previews and workbook maps. Split
  96-well output into independently printable Mix Map (A-D) and Mix Map (E-H)
  tabs. Repeat instructions and whole-plate recipes on both tabs, with consistent
  symbols and a reminder to prepare each bulk recipe once for the whole plate.
- Record plate type and geometry in artifact metadata and Run config; include
  plate type in result invalidation. Retain reagent calculations, overages,
  supporting sheets, and explicit Generate/Download behavior.
- Set source, launcher fallback, and project versions to 1.0.1; package the shared
  plate-format module in future builds. Leave the v1.0.0 installer link available.

## 1.0.0 — October 4, 2026

- Generate mix maps in memory and save each workbook only when Download is
  pressed, using the currently selected folder. Keep previews when changing
  folders, preserve existing files, and allow retries after save errors.
- Use ▲ ● ■ ◆ ★ to identify multiple L2000 bulk mixes consistently in the
  preview, Excel map, and recipe sheets. Include preparation amounts above
  the map, hide markers for a single group, and use numbered preview badges
  when there are more than five DNA-mass groups.
- Add a self-contained Apple Silicon `.pkg` installer for macOS 14 or later.
  Upgrades replace the application bundle while preserving Google sign-in
  and preferences. Validate isolated dependencies and exclude private state.
- Add a matching plate icon to the app header, browser tab, and Mac app bundle.
- Set app, launcher, project, and installer versions to 1.0.0. Replace the
  README with concise setup and use instructions and a direct installer link;
  keep developer instructions in BUILDING.md.

## 0.3 — October 4, 2026

Source update. No v0.3 installer has been built or published with these changes.

- Prepare up to five separate L2000 bulk transfectant mixes per plate, grouped
  by positive total DNA mass. Number mixes by descending well count, breaking
  ties by the earliest physical row and then column. All mixes use the same
  well and bulk overage factors. More than five groups blocks the entire batch.
- Show each bulk mix's recipe and assigned wells in the app and a dedicated
  printable workbook sheet. Label each populated Mix Map well with its assigned
  bulk transfectant mix and aliquot volume, so identification works in black and
  white without relying on color.
- Distinguish overage-inclusive preparation amounts from the final amount to
  deliver for LT1 and L2000.
- Normalize well identifiers before calculation and duplicate detection, reject
  column zero, and reject populated wide-format rows with missing wells.
- Validate complete DNA-mass values and ng units; malformed expressions and
  incompatible units produce source-row errors instead of altered values.
- Reject ambiguous concentration columns and explicitly unsupported units for
  used stocks while continuing to tolerate unrelated worksheet problems.
- Preserve CSV plasmid identifiers such as `00123` and `NA`, and write source
  labels as literal Excel text rather than formulas.
- Update the app and project version to 0.3. Existing cached calculation results
  require regeneration, while saved reagent preferences remain available.

## 0.2 — October 4, 2026

Source update. No v0.2 installer was built or published with these changes.

- Select up to five plate CSVs at once and switch the 48-well preview with a
  filename dropdown. Selected filenames and full paths are listed together.
- Simplify the plate preview instructions and remove the selected-plate count.
- Trim the automated suite to 99 functional tests, removing redundant, cosmetic,
  and obsolete cases.
- Multiple-plate selections require a manual output-folder choice. Generate one
  uniquely named workbook per plate using the same transfection settings.
- Validate and build the entire batch before publishing workbooks. Attempt to
  remove new batch outputs if a later save fails, and report any remaining files
  or temporary-file cleanup problems without hiding successful outputs.
- Validate concentrations only for plasmids used by the selected plates. Unrelated
  Sheet formatting, missing values, and duplicate conflicts no longer block runs.
- Report all missing or unusable plate concentrations in one error box, identify
  the affected plates, and create no output on validation failure.
- Add an 8-column, 6-row plate preview with pale purple DNA wells, plasmid/mass
  tooltips, and inert grey empty wells. The preview dropdown does not change run
  inputs or invalidate results; wells outside A1–F8 are explicitly identified.
- Rename run settings to **Final volume to be delivered to each well (µL)** and
  **Transfectant ratio (µL / µg DNA)**.

## 0.1 — October 4, 2026

Initial test release for Apple Silicon Macs running macOS 14 or later.

- Self-contained Mac app with a bundled Python runtime, local browser interface,
  and native launcher window. Quitting the app stops its local server.
- Single scrollable interface with individual LT1 and L2000 modes, conditional
  reagent settings, and a 25 µL final-volume default for both transfectants.
- Saved Google authentication, Sheet selection, concentration-format checks, and
  snapshot provenance. Google Sheets is the only concentration source.
- Native plate-CSV and folder selection. A selected plate's folder becomes the
  save location, with a manual override available.
- Excel workbooks saved directly into an existing folder with unique filenames.
  Generation creates no output folders or sidecar files.
- Strict conflicting-concentration handling across the selected Sheet.
- No demonstration inputs or outputs in the user interface; synthetic fixtures
  remain available only for testing.
- Visible v0.1 label and the requested Benjamin Pollak contact footer.

The installed app keeps credentials and preferences in Application Support; the
installer includes no personal credentials. This build uses local ad hoc signing
and is not Developer ID signed or notarized. Live Google authentication and real
native picker selections still need end-to-end testing. See `VALIDATION.md` for
verification details.
