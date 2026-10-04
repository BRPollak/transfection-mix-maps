import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.oauth2.credentials import Credentials

import sources
from core import MixMapError, load_plasmid_concentrations


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    target = tmp_path / "state"
    monkeypatch.setattr(sources, "STATE_DIR", target)
    return target


@pytest.fixture
def client_file(tmp_path):
    def create(client_id="client-one"):
        path = tmp_path / f"{client_id}.json"
        path.write_text(json.dumps({"installed": {
            "client_id": client_id, "client_secret": "test-client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }}))
        return str(path)
    return create


def credentials(client_id="client-one", expired=False):
    return Credentials(
        "test-access-token", refresh_token="test-refresh-token",
        token_uri="https://oauth2.googleapis.com/token", client_id=client_id,
        client_secret="test-client-secret", scopes=sources.SHEETS_SCOPES,
        expiry=datetime(2000 if expired else 2999, 1, 1),
    )


def save_auth(path, client_id="client-one"):
    client_path, _, key = sources._client_config(path)
    return sources._save_auth(credentials(client_id), client_path, key, new_session=True)


def test_disconnected_status_has_no_filesystem_side_effects(state):
    assert sources.auth_status()["state"] == "not_connected"
    assert not state.exists()


def test_saved_status_is_local_and_contains_no_tokens(client_file, monkeypatch, state):
    path = client_file()
    metadata = save_auth(path)
    monkeypatch.setattr(Credentials, "refresh", Mock(side_effect=AssertionError("Network not allowed")))
    result = sources.auth_status(path)
    assert result["state"] == "saved"
    assert result["last_authenticated_at"] == metadata["last_authenticated_at"]
    assert "test-access-token" not in json.dumps(result)
    assert "test-refresh-token" not in json.dumps(result)
    token_path, _ = sources._auth_paths(metadata["client_key"])
    assert token_path.stat().st_mode & 0o777 == 0o600
    assert token_path.parent.stat().st_mode & 0o777 == 0o700
    assert sources.auth_status()["state"] == "saved"


def test_changing_oauth_client_does_not_reuse_auth(client_file):
    first, second = client_file(), client_file("client-two")
    save_auth(first)
    assert sources.auth_status(first)["state"] == "saved"
    assert sources.auth_status(second)["state"] == "not_connected"


def test_expired_refreshable_credentials_report_saved_without_network(client_file):
    path = client_file()
    saved = save_auth(path)
    token_path, _ = sources._auth_paths(saved["client_key"])
    sources.private_json(token_path, json.loads(credentials(expired=True).to_json()))
    assert sources.auth_status(path)["state"] == "saved"


def test_bad_or_overbroad_token_requires_sign_in(client_file):
    path = client_file()
    metadata = save_auth(path)
    token_path, _ = sources._auth_paths(metadata["client_key"])
    token = json.loads(token_path.read_text())
    token["scopes"] = ["https://www.googleapis.com/auth/spreadsheets"]
    sources.private_json(token_path, token)
    assert sources.auth_status(path)["state"] == "needs_sign_in"
    token_path.write_text("not json")
    assert sources.auth_status(path)["state"] == "needs_sign_in"


def test_authenticate_uses_read_only_scope_and_persists_private_token(client_file, monkeypatch):
    from google_auth_oauthlib.flow import InstalledAppFlow

    path = client_file()
    flow = SimpleNamespace(run_local_server=Mock(return_value=credentials()))
    factory = Mock(return_value=flow)
    monkeypatch.setattr(InstalledAppFlow, "from_client_config", factory)
    result = sources.authenticate_google(path)
    assert result["state"] == "saved"
    assert factory.call_args.args[1] == sources.SHEETS_SCOPES
    assert flow.run_local_server.call_args.kwargs["host"] == "127.0.0.1"
    assert "test-access-token" not in json.dumps(result)
    assert sources.auth_status(path)["state"] == "saved"
    # A normal second click checks the saved credentials live without opening a browser.
    refresh = Mock()
    monkeypatch.setattr(Credentials, "refresh", refresh)
    again = sources.authenticate_google(path)
    assert again["auth_session"] == result["auth_session"]
    assert factory.call_count == 1
    refresh.assert_called_once()
    # Explicit sign-in again can switch accounts, so previous snapshots are invalidated.
    reconnected = sources.authenticate_google(path, force=True)
    assert reconnected["auth_session"] != result["auth_session"]
    assert factory.call_count == 2


def test_refresh_does_not_open_sign_in_implicitly(client_file, monkeypatch):
    from google_auth_oauthlib.flow import InstalledAppFlow

    factory = Mock(side_effect=AssertionError("Implicit sign-in"))
    monkeypatch.setattr(InstalledAppFlow, "from_client_config", factory)
    with pytest.raises(MixMapError, match="Sign in to Google before"):
        sources.refresh_google("a-valid-sheet-id-for-testing", client_file())
    factory.assert_not_called()


def test_refresh_scopes_cache_by_sheet_and_client(client_file, monkeypatch, state):
    import gspread

    path = client_file()
    auth = save_auth(path)
    worksheets = [
        SimpleNamespace(title="Stocks", get_all_values=Mock(return_value=[
            ["Plasmid", "Concentration (ng/uL)"], ["A", 1000], ["B", 50]
        ]))
    ]
    book = SimpleNamespace(title="Lab DNA stocks", worksheets=lambda: worksheets)
    client = SimpleNamespace(set_timeout=Mock(), open_by_key=Mock(return_value=book))
    authorize = Mock(return_value=client)
    monkeypatch.setattr(gspread, "authorize", authorize)
    result = sources.refresh_google("a-valid-sheet-id-for-testing", path)
    assert result["title"] == "Lab DNA stocks"
    assert result["validation"]["valid"]
    assert result["validation"]["valid_row_count"] == 2
    assert result["tables"]["Stocks"][1][1] == 1000
    worksheets[0].get_all_values.assert_called_once_with(value_render_option="UNFORMATTED_VALUE")
    assert result["client_key"] == auth["client_key"]
    assert authorize.call_args.args[0].scopes == sources.SHEETS_SCOPES
    assert sources.load_snapshot("a-valid-sheet-id-for-testing", path) == result
    assert sources.load_snapshot("another-sheet-id-for-testing", path) is None
    assert sources.load_snapshot("a-valid-sheet-id-for-testing", client_file("client-two")) is None
    assert (state / "cache" / auth["client_key"] / "a-valid-sheet-id-for-testing.json").is_file()
    save_auth(path)  # A new sign-in session cannot reuse another account's cached Sheet.
    assert sources.load_snapshot("a-valid-sheet-id-for-testing", path) is None


def test_refresh_failure_leaves_previous_snapshot(client_file, monkeypatch):
    import gspread

    path = client_file()
    metadata = save_auth(path)
    cached = {
        "sheet_id": "existing-sheet-id-for-testing", "client_key": metadata["client_key"],
        "auth_session": metadata["auth_session"], "title": "Saved stocks",
        "fetched_at": "2026-01-01T12:00:00-08:00", "tables": {
            "Stocks": [["Plasmid", "Concentration"], ["A", "50"]]
        },
    }
    sources.private_json(sources.STATE_DIR / "cache" / metadata["client_key"] / "existing-sheet-id-for-testing.json", cached)
    monkeypatch.setattr(gspread, "authorize", Mock(side_effect=RuntimeError("private-provider-detail")))
    with pytest.raises(MixMapError) as caught:
        sources.refresh_google("existing-sheet-id-for-testing", path)
    assert "private-provider-detail" not in str(caught.value.details)
    assert sources.load_snapshot("existing-sheet-id-for-testing", path)["fetched_at"] == cached["fetched_at"]


def test_revoked_refresh_requires_sign_in(client_file, monkeypatch):
    from google.auth.exceptions import RefreshError

    path = client_file()
    metadata = save_auth(path)
    token_path, _ = sources._auth_paths(metadata["client_key"])
    sources.private_json(token_path, json.loads(credentials(expired=True).to_json()))
    monkeypatch.setattr(Credentials, "refresh", Mock(side_effect=RefreshError("revoked")))
    with pytest.raises(MixMapError, match="expired or was revoked"):
        sources.refresh_google("existing-sheet-id-for-testing", path)
    assert sources.auth_status(path)["state"] == "needs_sign_in"


def test_validation_reports_columns_rows_preview_and_ignored_tabs():
    report = sources.validate_sheet_tables({
        "Stocks": [["Lab stocks"], [], ["Plasmid name", "ng/uL"], ["A", "100"], ["B", "50 ng/µL"]],
        "Notes": [["Date", "Operator"], ["Oct 4", "Lab"]],
        "Empty": [],
    })
    assert report["valid"]
    assert report["valid_row_count"] == 2
    stock = report["worksheets"][0]
    assert stock["header_row"] == 3
    assert stock["plasmid_column"] == "Plasmid name"
    assert stock["concentration_column"] == "ng/uL"
    assert report["preview"][0]["Row"] == 4
    assert report["warnings"]
    assert len(report["worksheets"]) == 3


@pytest.mark.parametrize("bad", ["", "nan", "inf", "1e999", "0", "-2", "text100", "100-ish", "50 ng per uL"])
def test_validation_does_not_certify_bad_numeric_rows(bad):
    report = sources.validate_sheet_tables({
        "Stocks": [["Plasmid", "Concentration"], ["Good", "50"], ["Bad", bad]]
    })
    assert not report["valid"]
    assert report["valid_row_count"] == 1
    assert any("Row 3" in item for item in report["errors"])


def test_validation_rejects_orphan_concentration_and_partial_headers():
    report = sources.validate_sheet_tables({
        "Stocks": [["Plasmid", "Concentration"], ["A", "50"], ["", "50"]],
        "Missing concentration": [["Plasmid", "Location"], ["B", "Freezer"]],
    })
    assert not report["valid"]
    assert any("no plasmid name" in item for item in report["errors"])
    assert any("separate Plasmid" in item for item in report["errors"])


def test_conflicting_duplicates_block_sheet_confirmation_even_if_unused_by_plate():
    tables = {
        "Stocks": [["Plasmid", "Concentration"], ["Used", "25"], ["Unused", "50"], ["Unused", "100"]]
    }
    report = sources.validate_sheet_tables(tables)
    assert not report["valid"]
    assert report["worksheets"][0]["status"] == "invalid"
    assert any("Conflicting concentrations" in item for item in report["errors"])
    assert any("row 3" in item and "row 4" in item for item in report["errors"])
    # The sheet-level gate is intentionally stricter than the original engine;
    # the engine's arithmetic and matching behavior remain unchanged.
    _, lookup, _ = load_plasmid_concentrations(tables, used_plasmids=["Used"])
    assert lookup["Used"]["Concentration_ng_per_uL"] == 25


@pytest.mark.parametrize("second_name", ["A", "a"])
def test_cross_worksheet_numeric_conflicts_mark_both_worksheets_invalid(second_name):
    tables = {
        "Stock 1": [["Plasmid", "Concentration"], ["A", "50"]],
        "Stock 2": [["Plasmid", "Concentration"], [second_name, "100"]],
    }
    report = sources.validate_sheet_tables(tables)
    assert not report["valid"]
    assert all(item["status"] == "invalid" for item in report["worksheets"])
    assert all(item["errors"] for item in report["worksheets"])
    if second_name == "a":
        assert any("letter case" in item for item in report["errors"])
        # Validation neither merges case-distinct names nor rewrites concentrations.
        _, lookup, _ = load_plasmid_concentrations(tables)
        assert lookup["A"]["Concentration_ng_per_uL"] == 50
        assert lookup["a"]["Concentration_ng_per_uL"] == 100


@pytest.mark.parametrize("second_name", ["A", "a"])
def test_identical_concentrations_remain_nonblocking_duplicate_warnings(second_name):
    tables = {
        "Stock 1": [["Plasmid", "Concentration"], ["A", "50"]],
        "Stock 2": [["Plasmid", "Concentration"], [second_name, "50"]],
    }
    report = sources.validate_sheet_tables(tables)
    assert report["valid"]
    assert not report["errors"]
    assert report["worksheets"][1]["status"] == "warning"
    assert any("same concentration" in item for item in report["warnings"])
    if second_name == "a":
        assert any("letter case" in item for item in report["warnings"])


@pytest.mark.parametrize("tables", [
    {}, {"Stock": []}, {"Stock": [["Plasmid", "Concentration"]]},
    {"Stock": [["Thing", "Amount"], ["A", "20"]]},
    {"Stock": [["Plasmid", "Concentration (ug/uL)"], ["A", "20"]]},
    {"Stock": [["Plasmid", "Concentration", "Concentration"], ["A", "20", "30"]]},
])
def test_no_valid_format_is_not_confirmed(tables):
    report = sources.validate_sheet_tables(tables)
    assert not report["valid"]
    assert report["errors"]


def test_saved_paths_reject_unexpected_oauth_endpoints(client_file):
    from pathlib import Path

    path = Path(client_file())
    data = json.loads(path.read_text())
    data["installed"]["token_uri"] = "https://untrusted.invalid/token"
    path.write_text(json.dumps(data))
    assert sources.auth_status(str(path))["state"] == "not_connected"
    with pytest.raises(MixMapError, match="valid Desktop"):
        sources.authenticate_google(str(path))


def test_authenticate_does_not_clear_needs_sign_in_by_inspecting_valid_token(client_file, monkeypatch):
    from google_auth_oauthlib.flow import InstalledAppFlow

    path = client_file()
    metadata = save_auth(path)
    sources._mark_needs_sign_in(metadata["client_key"])
    flow = SimpleNamespace(run_local_server=Mock(return_value=credentials()))
    factory = Mock(return_value=flow)
    monkeypatch.setattr(InstalledAppFlow, "from_client_config", factory)
    result = sources.authenticate_google(path)
    factory.assert_called_once()
    assert result["state"] == "saved"
    assert result["auth_session"] != metadata["auth_session"]


def test_transient_auth_verification_failure_does_not_start_oauth(client_file, monkeypatch):
    from google.auth.exceptions import TransportError
    from google_auth_oauthlib.flow import InstalledAppFlow

    path = client_file()
    save_auth(path)
    refresh = Mock(side_effect=TransportError("network down"))
    factory = Mock(side_effect=AssertionError("Unexpected browser sign-in"))
    monkeypatch.setattr(Credentials, "refresh", refresh)
    monkeypatch.setattr(InstalledAppFlow, "from_client_config", factory)
    with pytest.raises(MixMapError, match="could not be checked"):
        sources.authenticate_google(path)
    factory.assert_not_called()
    assert sources.auth_status(path)["state"] == "saved"


@pytest.mark.parametrize("override", [None, "relative-state", "~/Library/Application Support/Transfection Mix Maps/local_state"])
def test_state_directory_override_is_absolute_expanded_and_does_not_write_on_import(override, tmp_path):
    # A fresh interpreter tests import-time configuration without poisoning the
    # module-global state shared by the rest of the test suite.
    env = dict(os.environ)
    env.pop("MIXMAP_STATE_DIR", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(sources.APP_DIR)
    if override is not None:
        env["MIXMAP_STATE_DIR"] = override
    result = subprocess.run(
        [sys.executable, "-c", "import sources; print(sources.STATE_DIR)"],
        cwd=tmp_path, env=env, check=True, capture_output=True, text=True,
    )
    if override is None:
        expected = sources.APP_DIR / "local_state"
    elif override.startswith("~"):
        expected = Path(override).expanduser().resolve()
    else:
        expected = (tmp_path / override).resolve()
    assert Path(result.stdout.strip()) == expected
    assert Path(result.stdout.strip()).is_absolute()
    assert not list(tmp_path.iterdir())


def test_writable_override_keeps_settings_and_saved_auth_outside_app_bundle(tmp_path):
    target = tmp_path / "Application Support" / "Transfection Mix Maps" / "local_state"
    env = dict(os.environ, MIXMAP_STATE_DIR=str(target),
               PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(sources.APP_DIR))
    # Use synthetic preference data only. Real OAuth files are never read or copied.
    script = ("import sources; sources.save_settings({'sheet_url': 'test-sheet'}); "
              "print(sources.load_settings()['sheet_url'])")
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "test-sheet"
    assert json.loads((target / "settings.json").read_text()) == {"sheet_url": "test-sheet"}
    assert (target / "settings.json").stat().st_mode & 0o777 == 0o600
