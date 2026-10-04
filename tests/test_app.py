from pathlib import Path
import tomllib
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from app_version import VERSION
import native_dialogs
import sources

APP = Path(__file__).resolve().parents[1] / "app.py"
FIXTURES = APP.parent / "tests" / "fixtures"
SHEET_ID = "test-google-sheet-id-for-local-tests"


def start(monkeypatch, tmp_path, saved=None):
    monkeypatch.setattr(sources, "STATE_DIR", tmp_path / "state")
    if saved is not None:
        sources.save_settings(saved)
    at = AppTest.from_file(str(APP), default_timeout=15).run()
    assert not at.exception
    return at


def button(at, label):
    return next(b for b in at.button if b.label == label)


def connected(monkeypatch, tmp_path, *, valid=True):
    tables = {"Stocks": [["Plasmid", "Concentration (ng/uL)"],
                          ["Example_A", 100], ["Example_B", 50], ["Example_C", 75]]}
    if not valid:
        tables["Stocks"][1][1] = "missing"
    snapshot = {"sheet_id": SHEET_ID, "title": "Test stock inventory", "fetched_at": sources.now_iso(),
                "tables": tables, "validation": sources.validate_sheet_tables(tables)}
    monkeypatch.setattr(sources, "auth_status", lambda path: {"state": "saved", "message": "Sign-in saved."})
    monkeypatch.setattr(sources, "load_snapshot", lambda value, path: snapshot if value == SHEET_ID else None)
    plate = tmp_path / "plate.csv"
    plate.write_bytes((FIXTURES / "plate.csv").read_bytes())
    monkeypatch.setattr(native_dialogs, "choose_plate_file", Mock(return_value=str(plate)))
    at = start(monkeypatch, tmp_path, {"sheet_url": SHEET_ID})
    button(at, "Choose plate CSV…").click().run()
    assert not at.exception
    return at, snapshot


def test_one_page_has_no_demo_local_concentrations_or_combined_mode(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path, {"reagent_choice": "L2000 + LT1"})
    assert len(at.sidebar.children) == 0
    assert at.radio(key="reagent_choice").options == ["LT1", "L2000"]
    assert at.radio(key="reagent_choice").value == "LT1"
    assert not at.toggle
    assert {w.label for w in at.get("file_uploader")} == {"Google desktop client file (.json)"}
    assert not at.selectbox
    assert at.title[0].value == "Generate transfection mix maps"
    assert any(c.value == f"v{VERSION}" for c in at.caption)
    assert any(c.value == "Benjamin Pollak | brpollak@uscd.edu" for c in at.caption)
    assert [h.value for h in at.subheader] == ["1 · Connect your Google Sheet", "2 · Plate layout", "3 · Reagent settings", "4 · Save your workbook"]
    assert not any(w.label == "Save Excel files to" for w in at.text_input)
    assert button(at, "Generate LT1 Excel mix map").disabled


def test_distribution_metadata_matches_app_version():
    project = tomllib.loads((APP.parent / "pyproject.toml").read_text())
    lock = tomllib.loads((APP.parent / "uv.lock").read_text())
    locked_project = next(package for package in lock["package"]
                          if package["name"] == project["project"]["name"])
    assert VERSION == "0.1"
    assert project["project"]["version"] == locked_project["version"] == VERSION


def test_reagent_settings_are_conditional_and_persist_between_uses(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    assert len(at.number_input) == 3
    at.number_input(key="LT1_final_volume_ul").set_value(30.0).run()
    at.radio(key="reagent_choice").set_value("L2000").run()
    assert not at.exception
    assert len(at.number_input) == 4
    assert all(w.key.startswith("L2000_") for w in at.number_input)
    at.number_input(key="L2000_final_volume_ul").set_value(1000.0).run()
    at.radio(key="reagent_choice").set_value("LT1").run()
    assert at.number_input(key="LT1_final_volume_ul").value == 30.0
    fresh = AppTest.from_file(str(APP)).run()
    assert fresh.radio(key="reagent_choice").value == "LT1"
    assert fresh.number_input(key="LT1_final_volume_ul").value == 30.0
    fresh.radio(key="reagent_choice").set_value("L2000").run()
    assert fresh.number_input(key="L2000_final_volume_ul").value == 1000.0
    assert not fresh.exception


def test_sheet_selection_saves_without_generation(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    at.text_input(key="sheet_url").set_value(SHEET_ID).run()
    assert sources.load_settings()["sheet_url"] == SHEET_ID
    fresh = AppTest.from_file(str(APP)).run()
    assert fresh.text_input(key="sheet_url").value == SHEET_ID
    assert not fresh.exception


def test_folder_picker_selection_and_cancel(monkeypatch, tmp_path):
    folder = tmp_path / "My selected output folder"
    folder.mkdir()
    picker = Mock(return_value=str(folder))
    monkeypatch.setattr(native_dialogs, "choose_output_folder", picker)
    at = start(monkeypatch, tmp_path)
    button(at, "Save Excel files to…").click().run()
    assert not at.exception
    assert any(folder.name in m.value for m in at.markdown)
    assert sources.load_settings()["output_folder"] == str(folder)
    picker.return_value = None
    button(at, "Save Excel files to…").click().run()
    assert sources.load_settings()["output_folder"] == str(folder)
    fresh = AppTest.from_file(str(APP)).run()
    assert any(folder.name in m.value for m in fresh.markdown)


def test_invalid_sheet_url_reports_problem(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    at.text_input(key="sheet_url").set_value("invalid").run()
    assert not at.exception
    assert at.error
    assert button(at, "Confirm Sheet & refresh concentrations").disabled


def test_invalid_sheet_format_blocks_generation(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path, valid=False)
    assert not at.exception
    assert button(at, "Generate LT1 Excel mix map").disabled
    assert any("format needs attention" in e.value for e in at.error)


def test_verified_sheet_generates_only_selected_reagent(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    assert not button(at, "Generate LT1 Excel mix map").disabled
    button(at, "Generate LT1 Excel mix map").click().run()
    assert not at.exception
    assert not at.error
    assert len(at.session_state.result["artifacts"]) == 1
    assert at.session_state.result["artifacts"][0]["reagent"] == "LT1"
    assert "demo" not in at.session_state.result
    at.radio(key="reagent_choice").set_value("L2000").run()
    assert "result" not in at.session_state
    button(at, "Generate L2000 Excel mix map").click().run()
    assert not at.exception
    assert at.session_state.result["artifacts"][0]["reagent"] == "L2000"
    assert len(list(tmp_path.glob("*.xlsx"))) == 2
    assert at.session_state.result["folder"] == str(tmp_path)


def test_refresh_failure_blocks_saved_snapshot(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    monkeypatch.setattr(sources, "refresh_google", Mock(side_effect=sources.MixMapError("Cannot refresh Sheet")))
    button(at, "Confirm Sheet & refresh concentrations").click().run()
    assert not at.exception
    assert at.error
    assert button(at, "Generate LT1 Excel mix map").disabled
    at.number_input(key="LT1_final_volume_ul").set_value(30.0).run()
    assert button(at, "Generate LT1 Excel mix map").disabled


def test_generation_failure_clears_result(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    button(at, "Generate LT1 Excel mix map").click().run()
    assert "result" in at.session_state
    at.number_input(key="LT1_final_volume_ul").set_value(0.01).run()
    button(at, "Generate LT1 Excel mix map").click().run()
    assert not at.exception
    assert at.error
    assert "result" not in at.session_state


def test_plate_folder_auto_selection_manual_override_and_cancel(monkeypatch, tmp_path):
    plate_dir = tmp_path / "Input plates"
    plate_dir.mkdir()
    plate = plate_dir / "Plate one.csv"
    plate.write_bytes((FIXTURES / "plate.csv").read_bytes())
    other = tmp_path / "Workbooks"
    other.mkdir()
    picker = Mock(return_value=str(plate))
    monkeypatch.setattr(native_dialogs, "choose_plate_file", picker)
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(other)))
    at = start(monkeypatch, tmp_path)
    button(at, "Choose plate CSV…").click().run()
    assert not at.exception
    assert sources.load_settings()["output_folder"] == str(plate_dir)
    assert any(plate.name in m.value for m in at.markdown)
    button(at, "Save Excel files to…").click().run()
    assert sources.load_settings()["output_folder"] == str(other)
    at.radio(key="reagent_choice").set_value("L2000").run()
    assert at.session_state.output_folder == str(other)
    picker.return_value = None
    button(at, "Choose plate CSV…").click().run()
    assert at.session_state.output_folder == str(other)
    assert at.session_state.plate_path == str(plate)
    picker.return_value = str(plate)
    button(at, "Choose plate CSV…").click().run()
    assert at.session_state.output_folder == str(plate_dir)


def test_old_default_migrates_and_customized_volume_survives(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path, {"reagent_choice": "L2000", "L2000_final_volume_ul": 1500,
                                     "duplicate_policy": "last"})
    assert at.number_input(key="L2000_final_volume_ul").value == 25
    assert "duplicate_policy" not in sources.load_settings()
    at.number_input(key="L2000_final_volume_ul").set_value(40).run()
    fresh = AppTest.from_file(str(APP)).run()
    assert fresh.number_input(key="L2000_final_volume_ul").value == 40
    button(fresh, "Restore L2000 defaults").click().run()
    assert fresh.number_input(key="L2000_final_volume_ul").value == 25


def test_missing_output_folder_blocks_generation_without_creating_it(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    missing = tmp_path / "does-not-exist"
    at.session_state.output_folder = str(missing)
    at.run()
    assert not at.exception
    assert button(at, "Generate LT1 Excel mix map").disabled
    assert not missing.exists()
    assert any("Choose an existing folder" in e.value for e in at.error)


def test_unreadable_plate_clears_previous_selection(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    monkeypatch.setattr(native_dialogs, "choose_plate_file", Mock(return_value=str(tmp_path / "missing.csv")))
    button(at, "Choose plate CSV…").click().run()
    assert not at.exception
    assert at.error
    assert "plate_bytes" not in at.session_state
    assert button(at, "Generate LT1 Excel mix map").disabled
