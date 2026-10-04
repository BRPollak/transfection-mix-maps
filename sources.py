"""Plate input, Google Sheets snapshots, and private local preferences."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from core import MixMapError, extract_spreadsheet_id, scan_concentration_tables

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


def validate_sheet_tables(tables):
    """Inspect available stocks; only the selected plate determines run errors.

    The compatibility ``valid`` flag means the snapshot may be selected. It does
    not certify every cell or imply that all plasmids required by a plate exist.
    """
    scan = scan_concentration_tables(tables)
    worksheets, records = scan["worksheets"], scan["records"]
    matched_tabs = sum(item["valid_row_count"] > 0 for item in worksheets)
    preview = [{"Plasmid": record["Plasmid"],
                "Concentration (ng/uL)": record["Concentration_ng_per_uL"],
                "Worksheet": record["Source worksheet"], "Row": record["Source row"]}
               for record in records[:20]]
    summary = (f"Sheet loaded: {len(records)} usable concentration rows across {matched_tabs} worksheet(s). "
               "Only plasmids in your plate layout are checked when generating.")
    return {"valid": True, "summary": summary, "worksheet_count": len(worksheets),
            "valid_row_count": len(records), "errors": [], "warnings": [],
            "worksheets": worksheets, "preview": preview}
