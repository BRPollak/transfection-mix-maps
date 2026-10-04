# Changelog

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
