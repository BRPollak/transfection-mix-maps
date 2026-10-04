# Generate transfection mix maps — v0.3

A local Streamlit app adapted from **Optimized Transfection Mix Maps.ipynb**.
Choose up to five plate-layout CSVs and a saved Google Sheet of DNA concentrations,
then create an LT1 or L2000 Excel mix map for each plate using your reagent
settings. The app targets **Apple Silicon Macs running macOS 14 or later**.

Version **0.3** adds separate L2000 bulk mixes for different DNA totals, stricter
input validation, and clearer preparation and delivery volumes. Printed mix
names and well assignments remain readable in black and white. It includes
v0.2's batch generation, interactive 48-well preview, and concentration checks
limited to the plasmids your plates use. No v0.3 installer has been built or
published with this source update. Use the
[source instructions below](#run-from-source-or-develop) to run these changes.

## Install the published Mac app (v0.1)

1. Download the `.dmg` from the [v0.1 release](https://github.com/BRPollak/transfection-mix-maps/releases/tag/v0.1) and open it.
2. Drag **Transfection Mix Maps.app** into **Applications**. You can use your own
   `~/Applications` folder instead if preferred.
3. Eject the disk image and open the installed **Transfection Mix Maps** app.

The published v0.1 installer predates the v0.2 and v0.3 features described below. Future
installers will appear under [Releases](https://github.com/BRPollak/transfection-mix-maps/releases).

The app includes its Python runtime and dependencies. You do not need Terminal,
uv, or a separate Python installation. A small native app window starts the local
server and opens the interface in your browser. Keep that window open while
working. Close the window or quit the app to stop the server; closing only the
browser tab leaves the app running.

The published v0.1 test build is locally signed with an **ad hoc signature**. It is not signed
with an Apple Developer ID and is not notarized. macOS may show a Gatekeeper
alert. If you trust this build and intend to open it, follow Apple's per-app
instructions in [Safely open apps on your Mac](https://support.apple.com/102445).
After the first blocked launch, Apple describes using **System Settings → Privacy
& Security → Open Anyway** when that option is available.

## Use the app

The v0.3 app uses one scrollable page:

1. In the Google connection section at the top, confirm Google sign-in, enter the
   concentration Sheet URL, and load the Sheet. The page shows the available
   concentrations and when the saved data was refreshed. Concentrations are
   checked against the selected plate when you generate.
2. Press **Choose plate CSVs…** to select one to five plate layouts in the native
   macOS file chooser. Use Command-click or Shift-click to select several CSVs.
   A single plate automatically uses its folder as the workbook's save location.
   Selecting multiple plates clears the save location, and you must choose an
   output folder for that batch. A 48-well preview below the selector shows rows
   A–F and columns 1–8. Use the filename dropdown at the top right to switch
   between selected layouts. Their filenames and paths are listed above it. Wells
   with DNA are light purple; hover or focus a populated well to see its plasmids and
   masses in ng. Empty wells are light grey and do not respond to interaction.
3. Select **LT1** or **L2000**. **Reagent settings** shows settings for the selected
   transfectant. All selected plates use the same run settings, with a separate
   workbook for each plate. The volume and ratio inputs are labeled **Final volume
   to be delivered to each well (µL)** and **Transfectant ratio (µL / µg DNA)**.
4. To save somewhere else, press **Save Excel files to…** and select an existing
   folder in the native macOS folder chooser. The app displays its name and location.
   This choice stays selected until you choose another plate selection.
5. Generate the Excel mix maps. Every selected plate is checked before any final
   workbook is saved. If any plate fails validation, the batch creates no output. Each
   workbook is saved directly in the selected folder with a unique filename;
   you can also download each one from the app. The app creates no workbook
   folders or sidecar files. Switching the preview dropdown does not regenerate
   workbooks or change the selected batch.

For **L2000**, each plate may contain up to **five distinct positive total DNA
masses**. Wells with the same total receive the same recipe, named **Bulk
transfectant mix 1** through **5**. Mix 1 serves the largest group of wells; ties
are ordered by the earliest well's physical row, then column. Numbering restarts
for each plate. Empty wells receive no bulk mix. More than five totals in any
selected plate stops the entire batch before output is saved.

The workbook's **Bulk transfectant mixes** sheet gives each mix's preparation
recipe, assigned wells, and aliquot volume. Each populated well on the **Mix Map**
also identifies its assigned mix and aliquot. Prepare each bulk mix in its own
labeled tube and add its aliquot only to the corresponding wells' DNA mixtures.
Use the printed mix names and well lists to identify assignments; color is an
optional aid, and the map and recipes can be used with black-and-white printing.
The same well and bulk overage factors apply to every bulk mix.

Preparation includes overage; delivery uses the configured final volume. With
the defaults, LT1 prepares **32.5 µL** and delivers **25 µL** per well. L2000
prepares **15 µL** of DNA mixture per well, adds **15 µL** from the assigned bulk
mix, and delivers **25 µL** of that completed mixture. Bulk overage increases
the quantity prepared in each bulk tube without increasing its per-well aliquot.

The app remembers your Google authentication, chosen Sheet, output folder, and
reagent preferences between sessions. The plate CSVs must be selected again when
you return. Every workbook gets a unique filename so earlier workbooks are preserved.

## Connect Google Sheets once

The notebook's Colab authentication cannot transfer to a local app. The first
sign-in needs a desktop OAuth client. If you already have one, select its JSON
file in the app's Google setup section.

1. In [Google Cloud Console](https://console.cloud.google.com/), select or create
   a project and enable **Google Sheets API**.
2. Configure Google Auth Platform / the OAuth consent screen. If its audience is
   External and its publishing status is Testing, add your Google account as a
   test user. Institutional accounts may restrict creation or authorization of
   OAuth apps.
3. Create an **OAuth client ID** with application type **Desktop app** and download
   its JSON file.
4. Select that JSON file in the app, sign in to Google with an account that can read
   your concentration Sheet, and confirm the Sheet URL.
5. Load the Sheet. The app saves the connection and the selected Sheet for future
   launches, and displays the usable concentrations it found.

The app requests only the `spreadsheets.readonly` scope and opens your Sheet by ID.
It does not mount Drive or traverse folders. Credentials and authorization are
saved privately at
`~/Library/Application Support/Transfection Mix Maps/local_state/` for the installed
app. Do not share this folder. No Google credentials or personal settings are
included in the installer. Google may occasionally require you to sign in again.

The app uses the displayed saved Sheet snapshot for generation. Refresh it when
stock values change. Snapshots older than 24 hours require explicit acknowledgment
before use. The snapshot time and hash are recorded in the workbook's **Run config**.
A sign-in or Sheet-access failure is displayed; the app does not silently switch
to a different concentration source. Local concentration CSV/XLSX input is not
supported.

Google setup reference: [gspread authentication](https://docs.gspread.org/en/latest/oauth2.html).

## Input formats

Your **Google Sheet** must include plasmid identifiers and concentrations in ng/µL.
Use a header row with **Plasmid** and **Concentration (ng/uL)**. Multiple worksheet
tabs are supported. Loading a Sheet does not require every tab or stock entry to
have a concentration. Unrelated tabs, missing values, and duplicate conflicts for
unused plasmids do not block your run. When you generate, the app checks only
plasmids with positive DNA mass in your selected plates. Missing plasmids, missing
or unusable concentrations, and ambiguous or conflicting concentrations for those
plasmids are listed together in one error box. No workbook is created for a failed
run. Batch errors also identify the plate that needs correction. Correct the
listed entries and refresh the Sheet before trying again.
Each used stock's worksheet must have one unambiguous concentration column.
Headers with explicit units must use ng/µL (including `ng/uL`); alternatives such
as nM or µg/µL are rejected rather than converted. Distinct concentration columns
are ambiguous even when their header spellings differ.

Your **plate CSV** may be either format:

| Format | Required columns |
| --- | --- |
| Wide | `Well`, `Plasmid1`, `Mass1 (ng)`; optionally additional numbered plasmid/mass pairs |
| Long | `Well`, `Plasmid`, `Mass (ng)`; multiple rows can describe one well |

Masses must be finite nonnegative numbers in ng, optionally followed by `ng`.
For example, `100` and `100 ng` are accepted; expressions such as `100/2`,
unrecognized text such as `100foo`, and other units such as `1 ug` are rejected.
Mass column headers with explicit units must also use ng. Error details identify
the affected source rows so they can be corrected.

Well coordinates are normalized consistently: `A01` and `A1` refer to the same
well. Column zero is invalid. Wide-format duplicate coordinates are rejected
after normalization; long-format rows for one well contribute to the same DNA
total. Completely blank rows may be skipped, but a populated row without a well
is an error. Plasmid identifiers such as `00123` and `NA` are preserved, and
labels beginning with `=` are exported as literal text instead of Excel formulas.

The file and folder choosers run on the Mac hosting the app. This app is designed
to run locally; hosting it on another computer would open the choosers there.
The preview displays A1–F8. If a layout includes other wells, a notice lists the
wells outside that view; those wells remain part of the layout and calculations.

## Files and behavior

- `app.py`: single-page form, Google connection status, and results.
- `plate_preview.py`: 48-well preview with plasmid and mass tooltips.
- `core.py`: adapted notebook parser, matching, calculations, and Excel layout.
- `sources.py`: plate reader, saved preferences, Google authentication, and snapshots.
- `native_dialogs.py`: native macOS plate-file and output-folder selection.
- `workflow.py`: validation and batch workbook generation for one transfectant.
- `app_version.py`: the version displayed by the app and launcher.
- `local_state/`: private settings, tokens, and cached concentrations; the installed
  app stores this under its Application Support folder rather than inside the app.
- `tests/`: automated checks; synthetic input fixtures live only in `tests/fixtures/`.

L2000's final-volume default is now **25 µL**, matching LT1. The previous saved
L2000 default of 1,500 µL is migrated to 25 µL; other custom values are preserved.
Reagent values can still be adjusted in the main page. Duplicate concentration
conflicts for plasmids used by the plate stop the run; there is no first/last-row override. Warnings
appear in the app and workbook. Non-finite numeric inputs are rejected. A guard
rejects coordinates beyond 64 rows or 96 columns to prevent a typo from creating
an enormous printable grid. Errors clear the on-screen result; changing run
inputs requires regeneration. Choosing another plate only for preview preserves
the current results.

The selected output folder must already exist. Workbooks are published directly
into it only after every workbook is prepared. If a save fails, the app attempts
to remove newly published files from that batch and reports any it cannot remove.
Temporary-file cleanup problems are also reported. Existing workbooks are preserved.
Concentration provenance is recorded inside each workbook. The
app maintains its private authentication and preferences in the Application
Support location described above.

The server binds to `127.0.0.1` and Streamlit usage telemetry is disabled. Plate
selection transfers the CSV only to the server on this computer. No hosted service
is required for the app; Google Sheets access requires a network connection when
authenticating or refreshing the saved concentration data.

## Testing status

The v0.3 source passes **206 automated tests**, including **21 interface tests**,
covering calculations, exports,
batch validation and saving, Google connection logic, saved preferences, plate
previews, and simulated native file/folder selections. Regression
checks include grouped L2000 recipes, well assignments, the five-mass limit,
input validation, literal identifiers, and preparation versus delivery volumes.
Live Google authentication and real native file/folder selections still need
end-to-end testing; physical printouts and a v0.3 packaged app have not been
tested. See [VALIDATION.md](VALIDATION.md)
for the exact verification scope and [CHANGELOG.md](CHANGELOG.md) for release notes.
In the installed app, these documents are under **Show Package Contents →
Contents → Resources** in Finder.

## Reinstall or move to another Mac

Install the app from the DMG on a supported Mac. Replacing the app does not replace
the installed app's Application Support data. A different Mac needs its own Google
connection setup; the installer does not carry credentials between computers.

## Run from source or develop

This repository contains the v0.3 source. The published v0.1 installer is available
under [Releases](https://github.com/BRPollak/transfection-mix-maps/releases); building
and publishing a v0.3 installer is separate from this source update.

Clone this repository or download its source archive. Source runs
use `local_state/` beside the source files unless `MIXMAP_STATE_DIR` is set.

Keep the source folder and `uv.lock`. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
if needed, then double-click **Start Mix Maps.command**. It installs Python 3.12
and locked packages on first setup, which needs internet access, then reuses the
local environment on later launches. Keep its Terminal window open; press
**Control-C** there to stop a source run.

Or run from a terminal in this folder:

```sh
uv sync --locked --no-dev --python 3.12
uv run --no-sync python launch.py
```

For development/tests:

```sh
uv sync --locked
uv run pytest -q
```

The repository excludes credentials, user settings, generated workbooks, and the
machine-specific Python environment. macOS may ask how to open a downloaded
`.command` file; use Terminal or run the commands above. The DMG includes the
runtime so installed-app users do not need these development steps.

Streamlit reference: [running a local app](https://docs.streamlit.io/develop/concepts/architecture/run-your-app).

Benjamin Pollak | brpollak@uscd.edu
