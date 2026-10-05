import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import native_dialogs
import sources
from workflow import default_configs

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


def downloads(at):
    return [b for b in at.button if b.label.startswith("Download ")]


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
    monkeypatch.setattr(native_dialogs, "choose_plate_files", Mock(return_value=[str(plate)]))
    at = start(monkeypatch, tmp_path, {"sheet_url": SHEET_ID})
    button(at, "Choose plate CSVs…").click().run()
    assert not at.exception
    return at, snapshot


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


def test_invalid_sheet_url_reports_problem(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path)
    at.text_input(key="sheet_url").set_value("invalid").run()
    assert not at.exception
    assert at.error
    assert button(at, "Confirm Sheet & refresh concentrations").disabled


def test_missing_used_concentration_reports_one_error_only_on_generation(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path, valid=False)
    assert not at.exception
    assert not at.error
    assert not button(at, "Generate LT1 Excel mix map").disabled
    button(at, "Generate LT1 Excel mix map").click().run()
    assert not at.exception
    assert len(at.error) == 1
    assert "Example\\_A" in at.error[0].value
    assert "No output was created." in at.error[0].value
    assert "result" not in at.session_state
    assert not list(tmp_path.glob("*.xlsx"))


def test_unrelated_sheet_issues_do_not_block_or_show_errors(monkeypatch, tmp_path):
    at, snapshot = connected(monkeypatch, tmp_path)
    snapshot["tables"]["Stocks"] += [["Unused", ""], ["Conflict", 10], ["Conflict", 20]]
    snapshot["tables"]["Notes"] = [["Project", "Owner"], ["Inventory", "Lab"]]
    snapshot["validation"] = sources.validate_sheet_tables(snapshot["tables"])
    at.run()
    assert not at.exception
    assert not at.error
    assert not at.warning
    button(at, "Generate LT1 Excel mix map").click().run()
    assert not at.exception
    assert not at.error
    assert "result" in at.session_state


def test_preview_loads_without_google_and_clears_on_invalid_plate(monkeypatch, tmp_path):
    plate = tmp_path / "plate.csv"
    plate.write_bytes((FIXTURES / "plate.csv").read_bytes())
    monkeypatch.setattr(native_dialogs, "choose_plate_files", Mock(return_value=[str(plate)]))
    at = start(monkeypatch, tmp_path)
    empty_preview = at.get("html")[0].proto.body
    button(at, "Choose plate CSVs…").click().run()
    assert not at.exception
    populated_preview = at.get("html")[0].proto.body
    assert populated_preview != empty_preview
    assert "Example_A" in populated_preview
    assert "100 ng" in populated_preview
    plate.write_text("Well,Plasmid,Mass (ng)\nA1,Example_A,invalid\n")
    button(at, "Choose plate CSVs…").click().run()
    assert not at.exception
    assert at.error
    assert at.get("html")[0].proto.body == empty_preview
    assert button(at, "Generate LT1 Excel mix map").disabled


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
    assert not list(tmp_path.glob("*.xlsx"))
    assert "folder" not in at.session_state.result
    assert not at.get("download_button")
    assert len(downloads(at)) == 1


def test_download_saves_to_current_selected_folder_without_regenerating(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    button(at, "Generate LT1 Excel mix map").click().run()
    artifact = at.session_state.result["artifacts"][0]
    workbook_bytes = artifact["bytes"]
    fingerprint = at.session_state.result_fingerprint
    assert not list(tmp_path.glob("*.xlsx"))
    assert any("generated" in message.value for message in at.success)
    assert not any("workbook" in message.value.lower() and "saved" in message.value for message in at.success)

    destination = tmp_path / "Chosen workbooks"
    destination.mkdir()
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(destination)))
    button(at, "Save Excel files to…").click().run()
    assert not at.exception
    assert at.session_state.result_fingerprint == fingerprint
    assert at.session_state.result["artifacts"][0]["bytes"] == workbook_bytes
    assert not list(destination.iterdir())
    button(at, "Download LT1 workbook").click().run()
    assert not at.exception
    assert not at.error
    assert not at.get("download_button")
    assert not list(tmp_path.glob("*.xlsx"))
    saved = destination / artifact["name"]
    assert saved.read_bytes() == workbook_bytes
    assert any(str(saved) in caption.value for caption in at.caption)
    assert any("Workbook saved" in message.value for message in at.success)

    at.run()
    assert list(destination.iterdir()) == [saved]
    button(at, "Download LT1 workbook").click().run()
    assert not at.exception
    files = list(destination.iterdir())
    assert len(files) == 2
    assert all(path.read_bytes() == workbook_bytes for path in files)
    latest_save = at.session_state.result["artifacts"][0]["saved"]["path"]
    assert latest_save != str(saved)
    assert any(latest_save in caption.value for caption in at.caption)
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(tmp_path)))
    button(at, "Save Excel files to…").click().run()
    assert not at.exception
    assert not list(tmp_path.glob("*.xlsx"))
    assert not any("Workbook saved" in message.value for message in at.success)
    assert at.session_state.result_fingerprint == fingerprint
    button(at, "Download LT1 workbook").click().run()
    assert not at.exception
    assert (tmp_path / artifact["name"]).read_bytes() == workbook_bytes
    assert len(list(destination.iterdir())) == 2


def test_removed_destination_disables_download_and_new_folder_keeps_preview(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    destination = tmp_path / "Removed folder"
    destination.mkdir()
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(destination)))
    button(at, "Save Excel files to…").click().run()
    button(at, "Generate LT1 Excel mix map").click().run()
    artifact = at.session_state.result["artifacts"][0]
    destination.rmdir()
    button(at, "Download LT1 workbook").click().run()
    assert not at.exception
    assert not destination.exists()
    assert "result" in at.session_state
    assert button(at, "Download LT1 workbook").disabled
    assert not list(tmp_path.glob("*.xlsx"))
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(tmp_path)))
    button(at, "Save Excel files to…").click().run()
    assert at.session_state.result["artifacts"][0]["name"] == artifact["name"]
    button(at, "Download LT1 workbook").click().run()
    assert not at.exception
    assert not at.error
    assert (tmp_path / artifact["name"]).read_bytes() == artifact["bytes"]


def test_l2000_results_show_separate_recipes_and_well_assignments(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    plate = tmp_path / "plate.csv"
    plate.write_text("Well,Plasmid,Mass (ng)\nB2,Example_A,300\nA2,Example_A,100\nA1,Example_A,100\n")
    button(at, "Choose plate CSVs…").click().run()
    at.radio(key="reagent_choice").set_value("L2000").run()
    button(at, "Generate L2000 Excel mix map").click().run()
    assert not at.exception
    assert not at.error
    recipes = next(table.value for table in at.dataframe if "Assigned wells" in table.value.columns)
    assert recipes["Mix"].tolist() == ["Bulk transfectant mix 1", "Bulk transfectant mix 2"]
    assert recipes["Assigned wells"].tolist() == ["A1, A2", "B2"]
    assert recipes["L2000 to prepare (µL)"].tolist() == pytest.approx([0.576, 0.864])
    assert recipes["Total to prepare (µL)"].tolist() == pytest.approx([36, 18])
    assert recipes["Aliquot per DNA mixture (µL)"].tolist() == pytest.approx([15, 15])
    assignment = at.dataframe[-1].value
    assert assignment.loc["A", 1] == "Bulk transfectant mix 1"
    assert assignment.loc["A", 2] == "Bulk transfectant mix 1"
    assert assignment.loc["B", 2] == "Bulk transfectant mix 2"
    assert assignment.loc["B", 1] == ""
    assert not list(tmp_path.glob("*.xlsx"))


def test_l2000_six_mass_groups_clear_previous_result_without_new_output(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    at.radio(key="reagent_choice").set_value("L2000").run()
    button(at, "Generate L2000 Excel mix map").click().run()
    assert not at.exception
    assert "result" in at.session_state
    button(at, "Download L2000 workbook").click().run()
    existing_outputs = {path.name: path.read_bytes() for path in tmp_path.glob("*.xlsx")}
    plate = tmp_path / "plate.csv"
    plate.write_text("Well,Plasmid,Mass (ng)\n" + "".join(
        f"A{index},Example_A,{index * 100}\n" for index in range(1, 7)))
    button(at, "Choose plate CSVs…").click().run()
    button(at, "Generate L2000 Excel mix map").click().run()
    assert not at.exception
    assert len(at.error) == 1
    assert "No output was created." in at.error[0].value
    assert "result" not in at.session_state
    assert not downloads(at)
    assert {path.name: path.read_bytes() for path in tmp_path.glob("*.xlsx")} == existing_outputs


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


def test_old_calculation_fingerprint_clears_lt1_result_without_removing_workbook(monkeypatch, tmp_path):
    at, snapshot = connected(monkeypatch, tmp_path)
    button(at, "Generate LT1 Excel mix map").click().run()
    assert not at.exception
    assert "result" in at.session_state
    button(at, "Download LT1 workbook").click().run()
    existing_outputs = {path.name: path.read_bytes() for path in tmp_path.glob("*.xlsx")}
    # Recreate the pre-revision fingerprint using exactly the same run inputs.
    old_fingerprint = hashlib.sha256(json.dumps({
        "plates": [{"path": plate["path"], "name": plate["name"],
                    "hash": hashlib.sha256(plate["bytes"]).hexdigest()}
                   for plate in at.session_state.plates],
        "snapshot": snapshot, "reagent": "LT1", "config": default_configs()["LT1"],
        "output": str(tmp_path), "sheet_ready": True,
        "calculation_revision": 2,
    }, sort_keys=True).encode()).hexdigest()
    assert at.session_state.result_fingerprint != old_fingerprint
    at.session_state.result_fingerprint = old_fingerprint
    at.run()
    assert not at.exception
    assert "result" not in at.session_state
    assert not downloads(at)
    assert {path.name: path.read_bytes() for path in tmp_path.glob("*.xlsx")} == existing_outputs


@pytest.mark.parametrize("reagent", ["LT1", "L2000"])
def test_mass_markers_follow_preview_plate_without_invalidating_results(monkeypatch, tmp_path, reagent):
    from core import BULK_MIX_SYMBOLS

    at, _ = connected(monkeypatch, tmp_path)
    mixed = tmp_path / "mixed.csv"
    single = tmp_path / "single.csv"
    mixed.write_text("Well,Plasmid,Mass (ng)\nA1,Example_A,100\nA2,Example_A,200\n")
    single.write_text("Well,Plasmid,Mass (ng)\nB1,Example_A,300\nB2,Example_A,300\n")
    monkeypatch.setattr(native_dialogs, "choose_plate_files", Mock(return_value=[str(mixed), str(single)]))
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(tmp_path)))
    button(at, "Choose plate CSVs…").click().run()
    at.radio(key="reagent_choice").set_value(reagent).run()
    initial_preview = at.get("html")[0].proto.body
    assert all(symbol in initial_preview for symbol in BULK_MIX_SYMBOLS[:2])
    button(at, "Save Excel files to…").click().run()
    button(at, f"Generate 2 {reagent} Excel mix maps").click().run()
    assert not at.exception
    assert not at.error
    fingerprint = at.session_state.result_fingerprint
    outputs = {p.name: p.read_bytes() for p in tmp_path.glob("*.xlsx")}
    at.selectbox(key="preview_plate").set_value(str(single)).run()
    assert not at.exception
    preview = at.get("html")[0].proto.body
    assert not any(symbol in preview for symbol in BULK_MIX_SYMBOLS)
    assert "result" in at.session_state
    assert at.session_state.result_fingerprint == fingerprint
    at.selectbox(key="preview_plate").set_value(str(mixed)).run()
    assert at.get("html")[0].proto.body == initial_preview
    assert at.session_state.result_fingerprint == fingerprint
    assert {p.name: p.read_bytes() for p in tmp_path.glob("*.xlsx")} == outputs


def test_plate_folder_auto_selection_manual_override_and_cancel(monkeypatch, tmp_path):
    plate_dir = tmp_path / "Input plates"
    plate_dir.mkdir()
    plate = plate_dir / "Plate one.csv"
    plate.write_bytes((FIXTURES / "plate.csv").read_bytes())
    other = tmp_path / "Workbooks"
    other.mkdir()
    picker = Mock(return_value=[str(plate)])
    monkeypatch.setattr(native_dialogs, "choose_plate_files", picker)
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(other)))
    at = start(monkeypatch, tmp_path)
    button(at, "Choose plate CSVs…").click().run()
    assert not at.exception
    assert sources.load_settings()["output_folder"] == str(plate_dir)
    assert any(plate.name in m.value for m in at.markdown)
    button(at, "Save Excel files to…").click().run()
    assert sources.load_settings()["output_folder"] == str(other)
    at.radio(key="reagent_choice").set_value("L2000").run()
    assert at.session_state.output_folder == str(other)
    picker.return_value = None
    button(at, "Choose plate CSVs…").click().run()
    assert at.session_state.output_folder == str(other)
    assert at.session_state.plates[0]["path"] == str(plate)
    picker.return_value = [str(plate)]
    button(at, "Choose plate CSVs…").click().run()
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


def test_missing_output_folder_blocks_download_but_allows_generation(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    missing = tmp_path / "does-not-exist"
    at.session_state.output_folder = str(missing)
    at.run()
    assert not at.exception
    assert not button(at, "Generate LT1 Excel mix map").disabled
    button(at, "Generate LT1 Excel mix map").click().run()
    assert not at.exception
    assert "result" in at.session_state
    assert button(at, "Download LT1 workbook").disabled
    assert not missing.exists()
    assert any("Choose an existing folder" in e.value for e in at.error)


def test_unreadable_plate_clears_previous_selection(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    monkeypatch.setattr(native_dialogs, "choose_plate_files", Mock(return_value=[str(tmp_path / "missing.csv")]))
    button(at, "Choose plate CSVs…").click().run()
    assert not at.exception
    assert at.error
    assert "plates" not in at.session_state
    assert button(at, "Generate LT1 Excel mix map").disabled


def make_plates(tmp_path, count=2):
    plates = []
    for i in range(count):
        path = tmp_path / f"Plate {i + 1}.csv"
        path.write_text(f"Well,Plasmid,Mass (ng)\n{chr(65 + i)}{i + 1},Example_A,{100 + i}\n")
        plates.append(str(path))
    return plates


def test_multiple_plates_require_manual_folder_for_download_and_switch_previews(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    assert at.session_state.output_folder == str(tmp_path)
    plates = make_plates(tmp_path)
    picker = Mock(return_value=plates)
    monkeypatch.setattr(native_dialogs, "choose_plate_files", picker)
    button(at, "Choose plate CSVs…").click().run()
    assert not at.exception
    assert at.session_state.output_folder == ""
    assert sources.load_settings()["output_folder"] == ""
    assert not button(at, "Generate 2 LT1 Excel mix maps").disabled
    button(at, "Generate 2 LT1 Excel mix maps").click().run()
    assert all(b.disabled for b in downloads(at))
    fingerprint = at.session_state.result_fingerprint
    assert at.selectbox(key="preview_plate").options == ["Plate 1.csv", "Plate 2.csv"]
    assert all(any(p == caption.value for caption in at.caption) for p in plates)
    assert "Well A1. Example_A: 100 ng" in at.get("html")[0].proto.body
    at.selectbox(key="preview_plate").set_value(plates[1]).run()
    assert "Well B2. Example_A: 101 ng" in at.get("html")[0].proto.body
    assert "Well A1. Example_A" not in at.get("html")[0].proto.body
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=None))
    button(at, "Save Excel files to…").click().run()
    assert all(b.disabled for b in downloads(at))
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(tmp_path)))
    button(at, "Save Excel files to…").click().run()
    assert not button(at, "Generate 2 LT1 Excel mix maps").disabled
    assert len(downloads(at)) == 2
    assert all(not b.disabled for b in downloads(at))
    assert at.session_state.result_fingerprint == fingerprint
    picker.return_value = None
    button(at, "Choose plate CSVs…").click().run()
    assert len(at.session_state.plates) == 2
    assert at.session_state.output_folder == str(tmp_path)
    assert at.selectbox(key="preview_plate").value == plates[1]
    picker.return_value = plates
    button(at, "Choose plate CSVs…").click().run()
    assert at.session_state.output_folder == ""
    assert not button(at, "Generate 2 LT1 Excel mix maps").disabled
    assert "result" not in at.session_state
    picker.return_value = plates[:1]
    button(at, "Choose plate CSVs…").click().run()
    assert at.session_state.output_folder == str(tmp_path)
    assert [widget.key for widget in at.selectbox] == ["plate_type"]


def test_plate_type_defaults_each_session_without_persisting(monkeypatch, tmp_path):
    at = start(monkeypatch, tmp_path, {"plate_type": 96})
    assert at.selectbox(key="plate_type").value == 48
    at.selectbox(key="plate_type").set_value(6).run()
    assert not at.exception
    at.number_input(key="LT1_final_volume_ul").set_value(30.0).run()
    assert at.selectbox(key="plate_type").value == 6
    assert "plate_type" not in sources.load_settings()
    assert at.get("html")[0].proto.body.count('data-well="') == 6
    fresh = AppTest.from_file(str(APP)).run()
    assert not fresh.exception
    assert fresh.selectbox(key="plate_type").value == 48


def test_plate_type_change_revalidates_loaded_csv_and_invalidates_result(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    plate = tmp_path / "plate.csv"
    plate.write_text("Well,Plasmid,Mass (ng)\nA1,Example_A,100\nC8,Example_A,100\n")
    button(at, "Choose plate CSVs…").click().run()
    button(at, "Generate LT1 Excel mix map").click().run()
    assert "result" in at.session_state
    original_plates = at.session_state.plates
    at.selectbox(key="plate_type").set_value(6).run()
    assert not at.exception
    assert at.session_state.plates == original_plates
    assert "result" not in at.session_state
    assert not downloads(at)
    assert button(at, "Generate LT1 Excel mix map").disabled
    assert len(at.error) == 1
    assert "C8" in at.error[0].value and "plate\\.csv" in at.error[0].value
    at.selectbox(key="plate_type").set_value(96).run()
    assert not at.error
    assert not button(at, "Generate LT1 Excel mix map").disabled
    button(at, "Generate LT1 Excel mix map").click().run()
    assert not at.exception
    assert at.session_state.result["artifacts"][0]["plate_type"] == 96
    grid = next(table.value for table in at.dataframe if table.value.index.name == "Row")
    assert list(grid.index) == list("ABCDEFGH")
    assert list(grid.columns) == list(range(1, 13))


def test_one_plate_type_applies_to_entire_batch(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    first.write_text("Well,Plasmid,Mass (ng)\nB3,Example_A,100\nC8,,\nC8,,\n")
    second.write_text("Well,Plasmid,Mass (ng)\nC8,Example_A,100\n")
    monkeypatch.setattr(native_dialogs, "choose_plate_files", Mock(return_value=[str(first), str(second)]))
    at.selectbox(key="plate_type").set_value(6).run()
    button(at, "Choose plate CSVs…").click().run()
    assert not at.exception
    assert button(at, "Generate 2 LT1 Excel mix maps").disabled
    assert "second\\.csv" in at.error[0].value
    assert "first\\.csv" not in at.error[0].value
    at.selectbox(key="plate_type").set_value(48).run()
    button(at, "Generate 2 LT1 Excel mix maps").click().run()
    assert not at.exception
    assert not at.error
    assert [artifact["plate_type"] for artifact in at.session_state.result["artifacts"]] == [48, 48]


def test_valid_type_change_clears_results_and_dish_shows_a1(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    plate = tmp_path / "plate.csv"
    plate.write_text("Well,Plasmid,Mass (ng)\nA1,Example_A,100\nH12,,\n")
    button(at, "Choose plate CSVs…").click().run()
    button(at, "Generate LT1 Excel mix map").click().run()
    at.selectbox(key="plate_type").set_value(1).run()
    assert not at.exception
    assert not at.error
    assert "result" not in at.session_state
    assert not button(at, "Generate LT1 Excel mix map").disabled
    assert 'class="tmm-dish-label" aria-hidden="true">A1</span>' in at.get("html")[0].proto.body
    button(at, "Generate LT1 Excel mix map").click().run()
    assert not at.exception
    assert at.session_state.result["artifacts"][0]["plate_type"] == 1


def test_five_plate_batch_downloads_individually_and_preview_switch_keeps_results(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    plates = make_plates(tmp_path, 5)
    monkeypatch.setattr(native_dialogs, "choose_plate_files", Mock(return_value=plates))
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(tmp_path)))
    button(at, "Choose plate CSVs…").click().run()
    button(at, "Save Excel files to…").click().run()
    button(at, "Generate 5 LT1 Excel mix maps").click().run()
    assert not at.exception
    assert not at.error
    artifacts = at.session_state.result["artifacts"]
    assert len(artifacts) == 5
    assert len({artifact["name"] for artifact in artifacts}) == 5
    assert not list(tmp_path.glob("*.xlsx"))
    assert not at.get("download_button")
    assert len(downloads(at)) == 5
    fingerprint = at.session_state.result_fingerprint
    at.selectbox(key="preview_plate").set_value(plates[-1]).run()
    assert not at.exception
    assert "result" in at.session_state
    assert at.session_state.result_fingerprint == fingerprint
    assert "Well E5. Example_A: 104 ng" in at.get("html")[0].proto.body
    for index, artifact in enumerate(artifacts, 1):
        at.button(key="download_" + artifact["name"]).click().run()
        assert not at.exception
        assert not at.error
        assert len(list(tmp_path.glob("*.xlsx"))) == index
        assert (tmp_path / artifact["name"]).read_bytes() == artifact["bytes"]
    at.run()
    assert len(list(tmp_path.glob("*.xlsx"))) == 5


def test_batch_failure_identifies_plate_without_saving_other_workbooks(monkeypatch, tmp_path):
    at, _ = connected(monkeypatch, tmp_path)
    plates = make_plates(tmp_path)
    Path(plates[1]).write_text("Well,Plasmid,Mass (ng)\nF8,Missing,100\n")
    monkeypatch.setattr(native_dialogs, "choose_plate_files", Mock(return_value=plates))
    monkeypatch.setattr(native_dialogs, "choose_output_folder", Mock(return_value=str(tmp_path)))
    button(at, "Choose plate CSVs…").click().run()
    button(at, "Save Excel files to…").click().run()
    button(at, "Generate 2 LT1 Excel mix maps").click().run()
    assert not at.exception
    assert len(at.error) == 1
    assert "Plate 2\\.csv" in at.error[0].value
    assert "Missing" in at.error[0].value
    assert "No output was created." in at.error[0].value
    assert "result" not in at.session_state
    assert not list(tmp_path.glob("*.xlsx"))


def test_duplicate_filenames_have_distinct_preview_options(monkeypatch, tmp_path):
    plates = []
    for folder in ("First", "Second"):
        directory = tmp_path / folder
        directory.mkdir()
        plate = directory / "plate.csv"
        plate.write_bytes((FIXTURES / "plate.csv").read_bytes())
        plates.append(str(plate))
    monkeypatch.setattr(native_dialogs, "choose_plate_files", Mock(return_value=plates))
    at = start(monkeypatch, tmp_path)
    button(at, "Choose plate CSVs…").click().run()
    options = at.selectbox(key="preview_plate").options
    assert len(set(options)) == 2
    assert all("plate.csv" in option for option in options)
    assert "First" in options[0] and "Second" in options[1]
    at.selectbox(key="preview_plate").set_value(plates[1]).run()
    assert not at.exception


def test_download_failure_keeps_preview_and_allows_retry(monkeypatch, tmp_path):
    import workflow
    at, _ = connected(monkeypatch, tmp_path)
    button(at, "Generate LT1 Excel mix map").click().run()
    artifact = at.session_state.result["artifacts"][0]
    original_save = workflow.save_artifact
    failure = PermissionError("The selected folder is read-only")
    failure.cleanup_warnings = ["Temporary file could not be removed."]
    monkeypatch.setattr(workflow, "save_artifact", Mock(side_effect=failure))
    button(at, "Download LT1 workbook").click().run()
    assert not at.exception
    assert len(at.error) == 1
    assert "selected folder is read" in at.error[0].value
    assert any("Temporary file" in warning.value for warning in at.warning)
    assert "result" in at.session_state
    assert not any("Workbook saved" in message.value for message in at.success)
    assert not list(tmp_path.glob("*.xlsx"))
    monkeypatch.setattr(workflow, "save_artifact", original_save)
    button(at, "Download LT1 workbook").click().run()
    assert not at.exception
    assert not at.error
    assert not at.warning
    assert (tmp_path / artifact["name"]).read_bytes() == artifact["bytes"]
