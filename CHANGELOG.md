# Changelog

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
