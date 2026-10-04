"""Plate input, validated Google Sheets snapshots, and private local preferences."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from core import (MixMapError, clean_cell, extract_spreadsheet_id,
                  find_concentration_column, find_plasmid_name_column, parse_float,
                  values_to_dataframe)

APP_DIR = Path(__file__).resolve().parent
# Packaged launchers point this at writable Application Support storage; source runs
# keep the existing app-local directory. Resolve now so later working-directory changes
# cannot redirect credentials or settings into the application bundle.
STATE_DIR = Path(os.environ.get("MIXMAP_STATE_DIR", str(APP_DIR / "local_state"))).expanduser().resolve()
LOCAL_ZONE = ZoneInfo("America/Los_Angeles")
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


class _SignInRequired(MixMapError):
    """An invalid grant requires an explicit new authorization flow."""


def now_iso():
    return datetime.now(LOCAL_ZONE).isoformat(timespec="seconds")


def private_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, indent=2, allow_nan=False)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_json(path: Path, fallback=None):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        raise MixMapError("A saved file could not be read", [str(path)],
                          ["Choose your inputs again or refresh Google concentrations."]) from exc


def load_settings():
    return read_json(STATE_DIR / "settings.json", {})


def save_settings(settings):
    private_json(STATE_DIR / "settings.json", settings)


def read_plate(data: bytes):
    try:
        return pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
    except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
        raise MixMapError("Could not read the plate CSV", [str(exc)],
                          ["Choose a CSV with Well, Plasmid, and Mass (ng) columns, or the wide format."]) from exc


def sheet_id(value: str):
    found = extract_spreadsheet_id(value)
    if not found:
        raise MixMapError("Enter a Google Sheet URL or spreadsheet ID")
    return found


def _client_config(credentials_path=None):
    if credentials_path is None:
        credentials_path = load_settings().get("credentials_path")
        if not credentials_path:
            credentials_path = (read_json(STATE_DIR / "auth" / "connection.json", {})
                                .get("credentials_path"))
    if not credentials_path or not str(credentials_path).strip():
        raise MixMapError("Choose your Google OAuth client JSON file")
    credentials = Path(credentials_path).expanduser().resolve()
    if not credentials.is_file():
        raise MixMapError("Google sign-in needs an OAuth client file", [str(credentials)],
                          ["Choose the downloaded Desktop app OAuth client JSON file in Google setup."])
    try:
        config = json.loads(credentials.read_text())
        installed = config["installed"]
        if not all(isinstance(installed.get(key), str) and installed[key].strip()
                   for key in ("client_id", "client_secret", "auth_uri", "token_uri")):
            raise ValueError("Missing client fields")
        if (installed["auth_uri"] != "https://accounts.google.com/o/oauth2/auth"
                or installed["token_uri"] != "https://oauth2.googleapis.com/token"):
            raise ValueError("Unexpected Google OAuth endpoints")
        # Client identity, never the secret, determines the token/cache namespace.
        client_key = hashlib.sha256(installed["client_id"].encode()).hexdigest()[:24]
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise MixMapError("Choose a valid Desktop app OAuth client JSON file", fixes=[
            "Download the Desktop app client from Google Cloud Console. Service-account keys are not supported."
        ]) from exc
    return credentials, config, client_key


def _auth_paths(client_key):
    base = STATE_DIR / "auth" / client_key
    return base / "authorized_user.json", base / "status.json"


def _saved_credentials(config, client_key):
    from google.oauth2.credentials import Credentials

    token_path, _ = _auth_paths(client_key)
    if not token_path.exists():
        return None
    data = read_json(token_path)
    if not isinstance(data, dict) or data.get("client_id") != config["installed"]["client_id"]:
        raise MixMapError("Saved Google sign-in does not match this OAuth client", fixes=["Sign in to Google again."])
    if set(data.get("scopes", [])) != set(SHEETS_SCOPES):
        raise MixMapError("Google sign-in needs read-only Sheets permission", fixes=["Sign in to Google again."])
    try:
        return Credentials.from_authorized_user_info(data, scopes=SHEETS_SCOPES)
    except (ValueError, TypeError) as exc:
        raise MixMapError("Saved Google sign-in needs to be renewed", fixes=["Sign in to Google again."]) from exc


def auth_status(credentials_path=None):
    """Inspect local sign-in state without making requests or opening a browser."""
    try:
        _, config, client_key = _client_config(credentials_path)
    except MixMapError as exc:
        return {"state": "not_connected", "message": exc.title}
    try:
        credentials = _saved_credentials(config, client_key)
        _, metadata_path = _auth_paths(client_key)
        metadata = read_json(metadata_path, {})
        if credentials is None:
            return {"state": "not_connected", "client_key": client_key,
                    "message": "Google setup is ready. Sign in to save access on this Mac."}
        if metadata.get("state") == "needs_sign_in" or not (credentials.valid or credentials.refresh_token):
            return {"state": "needs_sign_in", "client_key": client_key,
                    "message": "Sign in to Google again to refresh your concentrations."}
    except MixMapError as exc:
        return {"state": "needs_sign_in", "client_key": client_key, "message": exc.title}
    return {"state": "saved", "client_key": client_key,
            "last_authenticated_at": metadata.get("last_authenticated_at"),
            "message": "Google sign-in is saved on this Mac. Refresh the Sheet to verify current access."}


def _save_auth(credentials, credentials_path, client_key, *, new_session=False):
    token_path, metadata_path = _auth_paths(client_key)
    old = read_json(metadata_path, {})
    metadata = {
        "state": "saved", "client_key": client_key,
        "credentials_path": str(credentials_path),
        "auth_session": str(uuid.uuid4()) if new_session else old.get("auth_session", str(uuid.uuid4())),
        "last_authenticated_at": now_iso(),
    }
    private_json(token_path, json.loads(credentials.to_json()))
    private_json(metadata_path, metadata)
    private_json(STATE_DIR / "auth" / "connection.json", {
        "credentials_path": str(credentials_path), "client_key": client_key,
    })
    return {**metadata, "message": "Google sign-in confirmed and saved on this Mac."}


def _mark_needs_sign_in(client_key):
    _, metadata_path = _auth_paths(client_key)
    metadata = read_json(metadata_path, {})
    private_json(metadata_path, {**metadata, "state": "needs_sign_in"})


def _refresh_token(credentials, client_key):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request

    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        _mark_needs_sign_in(client_key)
        raise _SignInRequired("Your Google sign-in has expired or was revoked", fixes=[
            "Sign in to Google again, then refresh the Sheet."
        ]) from exc
    except Exception as exc:
        raise MixMapError("Google sign-in could not be checked", fixes=[
            "Check your internet connection and try again."
        ]) from exc


def authenticate_google(credentials_path: str, force=False):
    """Explicit sign-in action. Tokens remain local and are never returned to the UI."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    path, config, client_key = _client_config(credentials_path)
    credentials = None
    if not force:
        try:
            _, metadata_path = _auth_paths(client_key)
            if read_json(metadata_path, {}).get("state") != "needs_sign_in":
                credentials = _saved_credentials(config, client_key)
        except MixMapError:
            pass
    if credentials is not None:
        if credentials.refresh_token:
            try:
                # The explicit confirmation button verifies access even if a cached token is valid.
                _refresh_token(credentials, client_key)
            except _SignInRequired:
                credentials = None
        else:
            credentials = None
    new_session = credentials is None or not credentials.valid
    if new_session:
        try:
            flow = InstalledAppFlow.from_client_config(config, SHEETS_SCOPES)
            credentials = flow.run_local_server(
                host="127.0.0.1", port=0, open_browser=True, timeout_seconds=180,
                prompt="consent", access_type="offline",
                authorization_prompt_message="Complete Google sign-in in the browser window that opened.",
                success_message="Google sign-in is complete. Return to Transfection mix maps.",
            )
        except Exception as exc:
            raise MixMapError("Google sign-in was not completed", fixes=[
                "Try signing in again. Confirm that your account is allowed to use this OAuth client."
            ]) from exc
    if not credentials.valid:
        raise MixMapError("Google did not return a usable sign-in", fixes=["Sign in to Google again."])
    if credentials.scopes and set(credentials.scopes) != set(SHEETS_SCOPES):
        raise MixMapError("Google sign-in did not use the expected read-only Sheets permission")
    return _save_auth(credentials, path, client_key, new_session=new_session)


def load_snapshot(value: str, credentials_path=None):
    sid = sheet_id(value)
    try:
        _, _, client_key = _client_config(credentials_path)
    except MixMapError:
        return None
    result = read_json(STATE_DIR / "cache" / client_key / f"{sid}.json")
    if result is None:
        return None
    _, metadata_path = _auth_paths(client_key)
    auth_session = read_json(metadata_path, {}).get("auth_session")
    if (result.get("client_key") != client_key or result.get("sheet_id") != sid
            or not isinstance(result.get("tables"), dict)):
        raise MixMapError("The saved concentrations are invalid", fixes=["Refresh concentrations from Google."])
    if not auth_session or result.get("auth_session") != auth_session:
        return None
    # Always evaluate the current validator, including snapshots from older app versions.
    result["validation"] = validate_sheet_tables(result["tables"])
    return result


def refresh_google(value: str, credentials_path: str):
    """Read the chosen Sheet using saved auth; sign-in is a separate, explicit action."""
    import gspread
    from google.auth.exceptions import RefreshError

    sid = sheet_id(value)
    path, config, client_key = _client_config(credentials_path)
    credentials = _saved_credentials(config, client_key)
    if credentials is None or auth_status(credentials_path)["state"] == "needs_sign_in":
        raise MixMapError("Sign in to Google before refreshing the Sheet")
    if not credentials.valid:
        _refresh_token(credentials, client_key)
        _save_auth(credentials, path, client_key)
    try:
        client = gspread.authorize(credentials)
        client.set_timeout(30)
        book = client.open_by_key(sid)
        tables = {ws.title: ws.get_all_values(value_render_option="UNFORMATTED_VALUE")
                  for ws in book.worksheets()}
    except RefreshError as exc:
        _mark_needs_sign_in(client_key)
        raise MixMapError("Your Google sign-in needs to be renewed", fixes=["Sign in to Google again."]) from exc
    except Exception as exc:
        raise MixMapError("The Google Sheet could not be refreshed", fixes=[
            "Check the Sheet URL and internet connection.",
            "Use a Google account with access to the Sheet, and enable the Google Sheets API for your OAuth client."
        ]) from exc
    _, metadata_path = _auth_paths(client_key)
    metadata = read_json(metadata_path, {})
    snapshot = {
        "sheet_id": sid, "title": book.title, "client_key": client_key,
        "auth_session": metadata.get("auth_session"), "fetched_at": now_iso(),
        "tables": tables, "validation": validate_sheet_tables(tables),
    }
    private_json(STATE_DIR / "cache" / client_key / f"{sid}.json", snapshot)
    return snapshot


def _numeric_concentration(value):
    """Accept a numeric cell, optionally with ng/uL units; reject text with embedded digits."""
    raw = str(value).strip()
    match = re.fullmatch(
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(?:ng\s*(?:/|per)\s*[uµμ]l)?",
        raw, flags=re.IGNORECASE,
    )
    if match is None:
        return None
    result = float(match.group(1))
    # A confirmed value must also be interpreted identically by the notebook engine.
    parsed = parse_float(value)
    return result if math.isfinite(result) and result > 0 and parsed == result else None


def validate_sheet_tables(tables):
    """Validate all candidate stock tabs using the same column mapping as the engine.

    Conflicting concentrations anywhere in the Sheet block confirmation, including
    names that differ only by case. Identical duplicates remain warnings. Source
    names and values are retained unchanged for the calculation engine.
    """
    worksheets, preview, records = [], [], []
    errors, warnings = [], []
    if not isinstance(tables, dict):
        tables = {}
    for title, values in tables.items():
        item = {"title": title, "status": "skipped", "header_row": None,
                "plasmid_column": None, "concentration_column": None,
                "valid_row_count": 0, "errors": [], "warnings": []}
        worksheets.append(item)
        try:
            frame = values_to_dataframe(values)
            columns = list(frame.columns)
        except (TypeError, ValueError):
            item["errors"].append("Worksheet cells could not be read as rows.")
            item["status"] = "invalid"
            continue
        if not columns:
            item["warnings"].append("Empty worksheet; skipped.")
            continue
        name_col = find_plasmid_name_column(columns)
        conc_col = find_concentration_column(columns)
        item.update(header_row=int(frame.attrs.get("header_row", 1)),
                    plasmid_column=name_col, concentration_column=conc_col)
        if name_col is None and conc_col is None:
            item["warnings"].append("No plasmid/concentration columns found; this worksheet is skipped.")
            continue
        if name_col is None or conc_col is None or name_col == conc_col:
            item["errors"].append("Use separate Plasmid and Concentration (ng/uL) columns in the header row.")
            item["status"] = "invalid"
            continue
        if columns.count(name_col) != 1 or columns.count(conc_col) != 1:
            item["errors"].append("The mapped plasmid/concentration column names must be unique.")
            item["status"] = "invalid"
            continue
        if re.search(r"(?:[uµμ]g|mg)\s*(?:/|per)|ng\s*(?:/|per)\s*ml", conc_col, re.I):
            item["errors"].append("Concentration units must be ng/uL. Convert the values and rename the column.")
        for row_index, row in frame.iterrows():
            row_number = int(row_index) + item["header_row"] + 1
            name = clean_cell(row.get(name_col))
            raw = clean_cell(row.get(conc_col))
            if not name and not raw:
                continue
            value = _numeric_concentration(row.get(conc_col))
            if not name:
                item["errors"].append(f"Row {row_number}: concentration has no plasmid name.")
            elif value is None:
                item["errors"].append(f"Row {row_number}: '{name}' needs a finite, positive numeric concentration in ng/uL.")
            else:
                record = {"Plasmid": name, "Concentration (ng/uL)": value,
                          "Worksheet": title, "Row": row_number}
                records.append(record)
                item["valid_row_count"] += 1
                if len(preview) < 20:
                    preview.append(record)
        if not item["valid_row_count"]:
            item["errors"].append("No valid plasmid concentration rows were found.")
        item["status"] = "invalid" if item["errors"] else "valid"

    exact, folded = {}, {}
    by_title = {item["title"]: item for item in worksheets}
    for record in records:
        name = record["Plasmid"]
        item = by_title[record["Worksheet"]]
        previous = exact.get(name) or folded.get(name.lower())
        if previous is not None:
            different_case = name != previous["Plasmid"]
            conflict = abs(record["Concentration (ng/uL)"] - previous["Concentration (ng/uL)"]) > 1e-9
            if conflict:
                message = (
                    f"Conflicting concentrations: '{name}' in {record['Worksheet']} row {record['Row']} "
                    f"is {record['Concentration (ng/uL)']:g} ng/uL, but '{previous['Plasmid']}' in "
                    f"{previous['Worksheet']} row {previous['Row']} is "
                    f"{previous['Concentration (ng/uL)']:g} ng/uL. "
                    + ("The plasmid names differ only in letter case. " if different_case else "")
                    + "Correct the Sheet so each plasmid has one concentration."
                )
                item["errors"].append(message)
                if previous["Worksheet"] != record["Worksheet"]:
                    by_title[previous["Worksheet"]]["errors"].append(message)
            elif different_case:
                item["warnings"].append(
                    f"Row {record['Row']}: '{name}' differs only in letter case from "
                    f"'{previous['Plasmid']}' in {previous['Worksheet']} row {previous['Row']}, "
                    "with the same concentration. Use exact plasmid names in the plate CSV "
                    "to avoid ambiguous matching."
                )
            else:
                item["warnings"].append(
                    f"Row {record['Row']}: '{name}' repeats {previous['Worksheet']} "
                    f"row {previous['Row']} with the same concentration."
                )
        exact.setdefault(name, record)
        folded.setdefault(name.lower(), record)
    for item in worksheets:
        errors.extend(f"{item['title']}: {message}" for message in item["errors"])
        warnings.extend(f"{item['title']}: {message}" for message in item["warnings"])
        if item["errors"]:
            item["status"] = "invalid"
        elif item["status"] == "valid" and item["warnings"]:
            item["status"] = "warning"
    if not records:
        errors.append("No usable concentrations found. Add Plasmid and Concentration (ng/uL) columns with positive numbers.")
    valid = bool(records) and not errors
    matched_tabs = sum(ws["valid_row_count"] > 0 for ws in worksheets)
    summary = (f"Format confirmed: {len(records)} valid concentration rows across {matched_tabs} worksheet(s)."
               if valid else "Sheet format needs attention before you can generate mix maps.")
    if valid and warnings:
        summary += " Review the warnings below."
    return {"valid": valid, "summary": summary, "worksheet_count": len(worksheets),
            "valid_row_count": len(records), "errors": errors, "warnings": warnings,
            "worksheets": worksheets, "preview": preview}
