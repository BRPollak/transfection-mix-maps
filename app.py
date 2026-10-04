"""Local Streamlit interface for Google Sheets-backed transfection mix maps."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app_version import VERSION
from core import MixMapError
from native_dialogs import FolderPickerError, PlatePickerError, choose_output_folder, choose_plate_file
from sources import (APP_DIR, LOCAL_ZONE, STATE_DIR, authenticate_google, auth_status,
                     load_settings, load_snapshot, private_json, refresh_google,
                     save_settings, sheet_id)
from workflow import default_configs, generate

st.set_page_config(page_title=f"Generate transfection mix maps · v{VERSION}", page_icon="🧪", layout="wide",
                   initial_sidebar_state="collapsed")

UI_VERSION = 3
FIELDS = {
    "final_volume_ul": ("Final volume per well (µL)", "Before the well overage factor is applied."),
    "dna_to_reagent_ratio_ul_per_ug": ("Reagent ratio (µL / µg DNA)", "Reagent volume per microgram of DNA."),
    "well_overage_factor": ("Well overage factor", "1.3 prepares 30% extra for each well."),
    "bulk_overage_factor": ("Bulk overage factor", "Additional overage for the L2000 bulk reagent tube."),
}
PREF_KEYS = ["reagent_choice", "output_folder", "sheet_url", "credentials_path"]
PREF_KEYS += [f"{r}_{field}" for r in ("LT1", "L2000") for field in FIELDS]


def show_error(exc):
    st.error(exc.title if isinstance(exc, MixMapError) else str(exc))
    if isinstance(exc, MixMapError):
        for detail in exc.details:
            st.text(detail)
        for fix in exc.fixes:
            st.caption(fix)


def initialize():
    migrated = False
    if st.session_state.get("ui_version") != UI_VERSION:
        try:
            saved = load_settings()
        except MixMapError as exc:
            saved = {}
            st.session_state["settings_error"] = exc
        if saved.get("settings_version") != UI_VERSION:
            # Replace the former default while preserving customized volumes.
            for values in (saved, st.session_state):
                if values.get("L2000_final_volume_ul") == 1500.0:
                    values["L2000_final_volume_ul"] = 25.0
                if values.get("output_folder") == str(APP_DIR / "generated"):
                    values["output_folder"] = ""
                values.pop("duplicate_policy", None)
            migrated = True
        st.session_state.preferences = saved
        # Invalidate a result left open in an older version of the app.
        for key in ["result", "result_fingerprint", "demo", "source_mode", "local_concentration_path", "plate_upload"]:
            st.session_state.pop(key, None)
        st.session_state.ui_version = UI_VERSION
    saved = st.session_state.preferences
    defaults = {"reagent_choice": "LT1", "output_folder": "", "sheet_url": "",
                "credentials_path": str(STATE_DIR / "auth" / "client_credentials.json")}
    choices = {"reagent_choice": ["LT1", "L2000"]}
    for key, default in defaults.items():
        candidate = st.session_state.get(key, saved.get(key, default))
        if not isinstance(candidate, str) or (key in choices and candidate not in choices[key]):
            candidate = default
        st.session_state[key] = candidate
    for reagent, config in default_configs().items():
        for field in FIELDS:
            key = f"{reagent}_{field}"
            value = st.session_state.get(key, saved.get(key, config[field]))
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                value = config[field]
            st.session_state[key] = float(value)
    if migrated:
        persist()


def preferences():
    saved = st.session_state.get("preferences", {})
    result = {key: st.session_state.get(key, saved.get(key)) for key in PREF_KEYS}
    result["settings_version"] = UI_VERSION
    st.session_state.preferences = result
    return result


def persist():
    try:
        save_settings(preferences())
        st.session_state.pop("save_error", None)
    except OSError as exc:
        st.session_state.save_error = f"Could not save settings on this Mac: {exc}"


def connection_changed():
    st.session_state.pop("sheet_issue", None)
    st.session_state.pop("result", None)
    persist()


def restore_selected_reagent():
    reagent = st.session_state.reagent_choice
    for field in FIELDS:
        st.session_state[f"{reagent}_{field}"] = float(default_configs()[reagent][field])
    persist()


def google_setup():
    path = Path(st.session_state.credentials_path).expanduser()
    with st.expander("One-time Google setup", expanded=False):
        st.markdown("""
Set up the Google connection once. Your sign-in and selected Sheet will be remembered.

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select or create a project.
2. Enable **Google Sheets API** and configure **Google Auth Platform / OAuth consent**.
   If the app is in Testing, add your Google account as a test user.
3. Create an **OAuth client ID → Desktop app** and download its JSON file.
4. Choose that JSON below, save it, then press **Sign in to Google**.
""")
        upload = st.file_uploader("Google desktop client file (.json)", type=["json"], key="oauth_client_upload")
        if upload is not None and st.button("Save Google client file"):
            try:
                payload = json.loads(upload.getvalue())
                installed = payload.get("installed", {})
                if not installed.get("client_id") or not installed.get("client_secret"):
                    raise ValueError("Choose a Desktop app OAuth client JSON downloaded from Google Cloud.")
                if installed.get("auth_uri") != "https://accounts.google.com/o/oauth2/auth" or installed.get("token_uri") != "https://oauth2.googleapis.com/token":
                    raise ValueError("The client file must use Google's authentication and token endpoints.")
                target = STATE_DIR / "auth" / "client_credentials.json"
                private_json(target, payload)
                st.session_state.credentials_path = str(target)
                connection_changed()
                st.success("Google client file saved. You can now sign in.")
            except (ValueError, OSError, AttributeError) as exc:
                st.error(str(exc))
        if path.is_file():
            st.caption(f"Saved Google client file: {path.name}")
        st.caption("This app requests read-only access to Google Sheets. Google may occasionally ask you to sign in again.")


def google_section():
    snapshot = None
    issue = None
    with st.container(border=True):
        st.subheader("1 · Connect your Google Sheet")
        st.caption("Your Google sign-in and selected Sheet are saved between uses on this Mac.")
        google_setup()
        status = auth_status(st.session_state.credentials_path)
        auth_ready = status["state"] == "saved"
        auth_left, auth_right = st.columns([3, 1])
        with auth_left:
            if auth_ready:
                st.success("Google sign-in saved")
                st.caption(status["message"])
            else:
                st.info("Google sign-in needed. Complete One-time Google setup above, then sign in.")
        with auth_right:
            label = "Confirm Google sign-in" if auth_ready else "Sign in to Google"
            if st.button(label, width="stretch"):
                try:
                    with st.spinner("Checking Google sign-in. Complete sign-in in the window that opens…"):
                        authenticate_google(st.session_state.credentials_path)
                    st.session_state.pop("sheet_issue", None)
                    persist()
                    st.rerun()
                except (MixMapError, OSError) as exc:
                    show_error(exc)
        st.text_input("Google Sheet URL or ID", key="sheet_url", on_change=connection_changed,
                      placeholder="Paste the Google Sheet containing your plasmid concentrations")
        st.caption("Concentrations must be in ng/µL. The Sheet needs a plasmid-name column and a concentration column.")
        url = st.session_state.sheet_url.strip()
        sid = None
        if url:
            try:
                sid = sheet_id(url)
                snapshot = load_snapshot(url, st.session_state.credentials_path)
            except (MixMapError, ValueError, OSError) as exc:
                issue = exc
        confirm_col, link_col = st.columns([2, 3])
        with confirm_col:
            if st.button("Confirm Sheet & refresh concentrations", type="primary", disabled=not (auth_ready and sid), width="stretch"):
                try:
                    with st.spinner("Opening the Sheet and checking its columns and concentrations…"):
                        snapshot = refresh_google(url, st.session_state.credentials_path)
                    st.session_state.pop("sheet_issue", None)
                    persist()
                except (MixMapError, ValueError, OSError) as exc:
                    st.session_state.sheet_issue = exc
        with link_col:
            if sid:
                st.link_button("Open selected Google Sheet ↗", f"https://docs.google.com/spreadsheets/d/{sid}/edit")
        issue = st.session_state.get("sheet_issue", issue)
        if issue:
            show_error(issue)
        report = snapshot.get("validation", {}) if snapshot else {}
        if snapshot:
            title = snapshot.get("title") or "Selected Google Sheet"
            st.markdown(f"**Selected Sheet:** {title}")
            fetched = datetime.fromisoformat(snapshot["fetched_at"])
            stamp = fetched.astimezone(LOCAL_ZONE).strftime("%b %d, %Y at %I:%M %p %Z")
            st.caption(f"Last confirmed with Google: {stamp}. Generate uses these saved concentrations; refresh after changing your Sheet.")
            if report.get("valid"):
                st.success(f"Sheet format confirmed · {report.get('valid_row_count', 0)} usable concentration rows")
            else:
                st.error("Sheet format needs attention before you can generate a mix map.")
            for error in report.get("errors", []):
                st.error(str(error))
            for warning in report.get("warnings", []):
                st.warning(str(warning))
            with st.expander("See Sheet format check and concentrations"):
                checks = [{"Worksheet": r["title"], "Status": r["status"],
                           "Plasmid column": r.get("plasmid_column") or "—",
                           "Concentration column": r.get("concentration_column") or "—",
                           "Usable rows": r.get("valid_row_count", 0)} for r in report.get("worksheets", [])]
                if checks:
                    st.dataframe(pd.DataFrame(checks), hide_index=True, width="stretch")
                if report.get("preview"):
                    st.dataframe(pd.DataFrame(report["preview"]), hide_index=True, width="stretch")
            age = (datetime.now(LOCAL_ZONE) - fetched).total_seconds()
            stale_ok = True
            if age > 24 * 3600:
                st.warning("Your saved concentrations are more than 24 hours old. Refresh if the Sheet has changed.")
                stale_ok = st.checkbox("Use these saved concentrations for this run", value=False,
                                       key="use_saved_" + hashlib.sha256((sid + snapshot["fetched_at"]).encode()).hexdigest()[:12])
            ready = auth_ready and report.get("valid", False) and stale_ok and not issue
        else:
            st.caption("Sheet format: not checked yet. Confirm the Sheet to check column names and positive numeric concentrations.")
            ready = False
    return snapshot, ready


def show_result(result):
    artifact = result["artifacts"][0]
    st.success(f"{artifact['reagent']} workbook saved in {result['elapsed']:.2f} seconds.")
    a, b, c = st.columns(3)
    a.metric("Wells", result["wells"])
    b.metric("Plasmid entries", result["entries"])
    c.metric("Unique plasmids", result["plasmids"])
    st.caption(f"Saved in {result['folder']}")
    if result["warnings"]:
        with st.expander(f"Review {len(result['warnings'])} warning(s)", expanded=True):
            for warning in result["warnings"]:
                st.warning(warning)
    st.download_button(f"Download {artifact['reagent']} workbook", artifact["bytes"], file_name=artifact["name"],
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", on_click="ignore")
    with st.expander("Preview volumes and plate map", expanded=True):
        summary = artifact["summary"]
        st.dataframe(summary[["Well", "Total DNA_ng", "Total working DNA_uL", "DNA diluent_uL", "Reagent_uL"]],
                     hide_index=True, width="stretch")
        st.dataframe(summary.pivot(index="Row", columns="Col", values="Mix").fillna(""), width="stretch")
        if artifact["bulk"]:
            bulk = artifact["bulk"]
            st.write(f"**Bulk reagent tube:** {bulk['Bulk reagent_uL']:.3f} µL reagent + {bulk['Bulk diluent_uL']:.3f} µL diluent = {bulk['Bulk total_uL']:.3f} µL total.")


def main():
    initialize()
    st.markdown("""<style>
    .block-container {padding-top: 4.5rem; padding-bottom:4rem; max-width:1120px;}
    h1 {letter-spacing:-.04em; font-weight:700;}
    .eyebrow {font-size:.75rem; letter-spacing:.16em; color:#237D70; font-weight:700;}
    div[data-testid="stMetric"] {background:#EDF2ED; padding:14px 18px; border-radius:12px;}
    </style><div class="eyebrow">PLATE PREPARATION · LOCAL WORKSPACE</div>""", unsafe_allow_html=True)
    st.title("Generate transfection mix maps")
    st.caption(f"v{VERSION}")
    st.write("Connect your concentrations, choose a plate, and save an Excel map ready for the bench.")
    if "settings_error" in st.session_state:
        show_error(st.session_state.pop("settings_error"))
    snapshot, sheet_ready = google_section()

    st.subheader("2 · Plate layout")
    if st.button("Choose plate CSV…", icon="📄"):
        try:
            initial_folder = st.session_state.output_folder or str(Path.home())
            selected = choose_plate_file(initial_folder)
            if selected:
                plate_path = Path(selected)
                if plate_path.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError("Choose a plate CSV smaller than 20 MB.")
                plate_bytes = plate_path.read_bytes()
                if not plate_bytes:
                    raise ValueError("This plate CSV is empty. Choose a file with a plate layout.")
                st.session_state.plate_path = str(plate_path)
                st.session_state.plate_bytes = plate_bytes
                st.session_state.plate_name = plate_path.name
                st.session_state.output_folder = str(plate_path.parent)
                st.session_state.pop("result", None)
                persist()
        except (PlatePickerError, OSError, ValueError) as exc:
            for key in ("plate_path", "plate_bytes", "plate_name", "result"):
                st.session_state.pop(key, None)
            st.error(str(exc))
    if st.session_state.get("plate_path"):
        st.markdown(f"**Selected plate:** {st.session_state.plate_name}")
        st.caption(st.session_state.plate_path)
    else:
        st.caption("Choose a CSV on your Mac. Its folder will also be used to save your workbook.")
    st.caption("Wide format: Well, Plasmid1, Mass1 (ng), … · Long format: Well, Plasmid, Mass (ng).")
    plate_bytes = st.session_state.get("plate_bytes")
    plate_name = st.session_state.get("plate_name")

    st.subheader("3 · Reagent settings")
    st.radio("Transfectant", ["LT1", "L2000"], horizontal=True, key="reagent_choice", on_change=persist)
    reagent = st.session_state.reagent_choice
    visible_fields = list(FIELDS) if reagent == "L2000" else list(FIELDS)[:3]
    columns = st.columns(2)
    for i, field in enumerate(visible_fields):
        label, help_text = FIELDS[field]
        with columns[i % 2]:
            st.number_input(label, min_value=0.001, step=0.1, format="%.3f", key=f"{reagent}_{field}",
                            help=help_text, on_change=persist)
    st.caption("L2000 prepares separate DNA and bulk reagent tubes." if reagent == "L2000" else "LT1 prepares one complete mix per well.")
    st.button(f"Restore {reagent} defaults", on_click=restore_selected_reagent)

    st.subheader("4 · Save your workbook")
    folder_col, name_col = st.columns([1, 2])
    with folder_col:
        if st.button("Save Excel files to…", icon="📁", width="stretch"):
            try:
                selected = choose_output_folder(st.session_state.output_folder or str(Path.home()))
                if selected:
                    st.session_state.output_folder = selected
                    persist()
            except FolderPickerError as exc:
                st.error(str(exc))
    with name_col:
        destination = Path(st.session_state.output_folder).expanduser() if st.session_state.output_folder else None
        if destination:
            st.markdown(f"**Selected folder:** {destination.name or str(destination)}")
            st.caption(str(destination))
        else:
            st.caption("Select a plate CSV or choose an existing folder.")
    st.caption("Excel files are saved directly to the selected folder. You can change it above.")
    if destination and not destination.is_dir():
        st.error("The selected folder is no longer available. Choose an existing folder.")
    if "save_error" in st.session_state:
        st.error(st.session_state.save_error)

    configs = default_configs()
    for r in configs:
        for field in FIELDS:
            configs[r][field] = st.session_state[f"{r}_{field}"]
    preferences()  # Retain hidden reagent settings when Streamlit removes their widgets.
    ready = bool(plate_bytes and sheet_ready and destination and destination.is_dir())
    fingerprint = hashlib.sha256((plate_bytes or b"") + json.dumps({
        "name": plate_name, "snapshot": snapshot, "reagent": reagent,
        "config": configs[reagent],
        "output": str(destination), "sheet_ready": sheet_ready,
    }, sort_keys=True).encode()).hexdigest()
    if st.session_state.get("result") and st.session_state.get("result_fingerprint") != fingerprint:
        st.session_state.pop("result", None)
        st.info("Inputs changed. Generate again to preview results for these settings.")
    if st.button(f"Generate {reagent} Excel mix map", type="primary", disabled=not ready, width="stretch"):
        st.session_state.pop("result", None)
        try:
            with st.spinner("Checking plate inputs and building your workbook…"):
                result = generate(plate_bytes, plate_name, snapshot["tables"],
                                  f"Google Sheet: {snapshot['sheet_id']}", snapshot["fetched_at"],
                                  [reagent], configs, str(destination))
            st.session_state.result = result
            st.session_state.result_fingerprint = fingerprint
            persist()
        except Exception as exc:
            show_error(exc)
    if not ready:
        st.caption("Confirm Google sign-in and a valid Sheet, then choose a plate CSV to generate your workbook.")
    if st.session_state.get("result"):
        show_result(st.session_state.result)
    st.divider()
    st.caption("Benjamin Pollak | brpollak@uscd.edu")


main()
