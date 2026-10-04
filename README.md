# Generate transfection mix maps — v0.1

A local Streamlit app adapted from **Optimized Transfection Mix Maps.ipynb**.
Choose a plate-layout CSV and a saved Google Sheet of DNA concentrations, then
create an LT1 or L2000 Excel mix map with the notebook's calculation methods.
Version **0.1** is an initial test release for **Apple Silicon Macs running macOS
14 or later**.

## Install the Mac app

1. Download the `.dmg` from the [v0.1 release](https://github.com/BRPollak/transfection-mix-maps/releases/tag/v0.1) and open it.
2. Drag **Transfection Mix Maps.app** into **Applications**. You can use your own
   `~/Applications` folder instead if preferred.
3. Eject the disk image and open the installed **Transfection Mix Maps** app.

The app includes its Python runtime and dependencies. You do not need Terminal,
uv, or a separate Python installation. A small native app window starts the local
server and opens the interface in your browser. Keep that window open while
working. Close the window or quit the app to stop the server; closing only the
browser tab leaves the app running.

This test build is locally signed with an **ad hoc signature**. It is not signed
with an Apple Developer ID and is not notarized. macOS may show a Gatekeeper
alert. If you trust this build and intend to open it, follow Apple's per-app
instructions in [Safely open apps on your Mac](https://support.apple.com/102445).
After the first blocked launch, Apple describes using **System Settings → Privacy
& Security → Open Anyway** when that option is available.

## Use the app

The app uses one scrollable page:

1. In the Google connection section at the top, confirm Google sign-in, enter the
   concentration Sheet URL, and load/check the Sheet. The page confirms whether
   its concentration format is usable and shows when the saved data was refreshed.
2. Press **Choose plate CSV…** to select your plate file in the native macOS file
   chooser. Its folder automatically becomes the workbook's save location.
3. Select **LT1** or **L2000**. **Reagent settings** shows settings for the selected
   transfectant. Each generation creates one reagent workbook.
4. To save somewhere else, press **Save Excel files to…** and select an existing
   folder in the native macOS folder chooser. The app displays its name and location.
   This override stays selected until you choose another plate CSV.
5. Generate the Excel mix map. The workbook is saved directly in the selected
   folder; you can also download it from the app. The app creates no workbook
   folders or sidecar files.

The app remembers your Google authentication, chosen Sheet, output folder, and
reagent preferences between sessions. The plate CSV must be selected again when
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
5. Load/check the Sheet. The app saves the connection and the selected Sheet for
   future launches, and reports authentication and concentration-format status.

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
tabs are supported. The app checks the detected concentration columns and reports
format problems before generation. Blank or unrelated tabs may be skipped with
warnings; the confirmation shows which data was recognized. Conflicting duplicate
concentrations anywhere in the Sheet block confirmation and generation. Resolve
them in the Sheet, then refresh. Missing plasmids and impossible volumes also
block generation.

Your **plate CSV** may be either format:

| Format | Required columns |
| --- | --- |
| Wide | `Well`, `Plasmid1`, `Mass1 (ng)`; optionally additional numbered plasmid/mass pairs |
| Long | `Well`, `Plasmid`, `Mass (ng)`; multiple rows can describe one well |

The file and folder choosers run on the Mac hosting the app. This app is designed
to run locally; hosting it on another computer would open the choosers there.

## Files and behavior

- `app.py`: single-page form, Google connection status, and results.
- `core.py`: adapted notebook parser, matching, calculations, and Excel layout.
- `sources.py`: plate reader, saved preferences, Google authentication, and snapshots.
- `native_dialogs.py`: native macOS plate-file and output-folder selection.
- `workflow.py`: validation and single-reagent workbook generation.
- `app_version.py`: the version displayed by the app and launcher.
- `local_state/`: private settings, tokens, and cached concentrations; the installed
  app stores this under its Application Support folder rather than inside the app.
- `tests/`: automated checks; synthetic input fixtures live only in `tests/fixtures/`.

L2000's final-volume default is now **25 µL**, matching LT1. The previous saved
L2000 default of 1,500 µL is migrated to 25 µL; other custom values are preserved.
Reagent values can still be adjusted in the main page. Duplicate concentration
conflicts always stop the run; there is no first/last-row override. Warnings
appear in the app and workbook. Non-finite numeric inputs are rejected. A guard
rejects coordinates beyond 64 rows or 96 columns to prevent a typo from creating
an enormous printable grid. Errors clear the on-screen result; changing inputs
requires regeneration.

The selected output folder must already exist. Workbooks are published directly
into it only after generation succeeds; incomplete temporary files are removed
after failures. Concentration provenance is recorded inside the workbook. The
app maintains its private authentication and preferences in the Application
Support location described above.

The server binds to `127.0.0.1` and Streamlit usage telemetry is disabled. Plate
selection transfers the CSV only to the server on this computer. No hosted service
is required for the app; Google Sheets access requires a network connection when
authenticating or refreshing the saved concentration data.

## Testing status

This is a v0.1 test release. Automated checks cover calculations, exports,
Google connection logic, saved preferences, and simulated native file/folder
selections. Live Google authentication and selecting real files/folders through
the packaged app still need end-to-end testing. See [VALIDATION.md](VALIDATION.md)
for the exact verification scope and [CHANGELOG.md](CHANGELOG.md) for release notes.
In the installed app, these documents are under **Show Package Contents →
Contents → Resources** in Finder.

## Reinstall or move to another Mac

Install the app from the DMG on a supported Mac. Replacing the app does not replace
the installed app's Application Support data. A different Mac needs its own Google
connection setup; the installer does not carry credentials between computers.

## Run from source or develop

This repository contains the current v0.1 source as a fresh initial commit; earlier
development versions are not included. The self-contained installer is available
under [Releases](https://github.com/BRPollak/transfection-mix-maps/releases).

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
