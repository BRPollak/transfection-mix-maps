"""No test launches an actual native dialog."""
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

import native_dialogs
from native_dialogs import (
    FolderPickerError, PlatePickerError, choose_output_folder, choose_plate_files,
)


@pytest.fixture
def run_dialog(monkeypatch):
    monkeypatch.setattr(native_dialogs.sys, "platform", "darwin")
    runner = Mock()
    monkeypatch.setattr(native_dialogs.subprocess, "run", runner)
    return runner


def test_selected_folder_and_script_arguments_are_safe(run_dialog, tmp_path):
    # This must remain one process argument, including quotes and shell syntax.
    folder = tmp_path / ' Plates\n"today" \' $(touch INJECTED); `echo nope`'
    folder.mkdir()
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 0, stdout=str(folder) + "/\n", stderr=""
    )

    assert choose_output_folder(str(folder)) == str(folder)
    args, kwargs = run_dialog.call_args
    assert args[0][-1] == str(folder)
    assert not kwargs.get("shell", False)


def test_new_output_folder_starts_at_existing_parent(run_dialog, tmp_path):
    run_dialog.return_value = subprocess.CompletedProcess([], 0, stdout="\n", stderr="")
    missing = tmp_path / "new" / "generated"
    assert choose_output_folder(str(missing)) is None
    assert run_dialog.call_args.args[0][-1] == str(tmp_path)
    assert not missing.exists()


def test_native_cancel_error_is_not_reported_as_failure(run_dialog, tmp_path):
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 1, stdout="", stderr="execution error: User canceled. (-128)\n"
    )
    assert choose_output_folder(str(tmp_path)) is None


def test_picker_error_is_actionable(run_dialog, tmp_path):
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 1, stdout="", stderr="execution error: Dialog unavailable. (-600)\n"
    )
    with pytest.raises(FolderPickerError, match="Try again.*Dialog unavailable"):
        choose_output_folder(str(tmp_path))


def test_timeout_is_actionable(run_dialog, tmp_path):
    run_dialog.side_effect = subprocess.TimeoutExpired("osascript", 300)
    with pytest.raises(FolderPickerError, match="five minutes"):
        choose_output_folder(str(tmp_path))


def test_missing_osascript_is_actionable(run_dialog, tmp_path):
    run_dialog.side_effect = FileNotFoundError("osascript is missing")
    with pytest.raises(FolderPickerError, match="running on your Mac"):
        choose_output_folder(str(tmp_path))


@pytest.mark.parametrize("invalid_path", ["relative/path", "/missing-output-folder-581624"])
def test_unusable_returned_path_is_rejected(run_dialog, tmp_path, invalid_path):
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 0, stdout=invalid_path + "\n", stderr=""
    )
    with pytest.raises(FolderPickerError, match="choose an existing folder"):
        choose_output_folder(str(tmp_path))


def test_non_mac_platform_has_clear_error_without_subprocess(run_dialog, monkeypatch):
    monkeypatch.setattr(native_dialogs.sys, "platform", "linux")
    with pytest.raises(FolderPickerError, match="requires macOS"):
        choose_output_folder("/tmp")
    run_dialog.assert_not_called()


def plate_result(paths):
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(paths) + "\n", stderr="")


def test_multiple_plate_selection_preserves_names_and_passes_folder_safely(run_dialog, tmp_path):
    folder = tmp_path / 'Plates "today" \' $(touch INJECTED); `echo nope`'
    folder.mkdir()
    plates = [folder / ' first\nplate.CSV', folder / 'second "plate".csv']
    for plate in plates:
        plate.write_text("Well,Plasmid,Mass (ng)\n")
    run_dialog.return_value = plate_result([str(plate) for plate in plates])

    assert choose_plate_files(str(folder)) == [str(plate) for plate in plates]
    assert run_dialog.call_args.args[0][-1] == str(folder)
    assert not run_dialog.call_args.kwargs.get("shell", False)


@pytest.mark.parametrize("output", ["\n", "[]\n"])
def test_multiple_plate_cancel_returns_none(run_dialog, tmp_path, output):
    run_dialog.return_value = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
    assert choose_plate_files(str(tmp_path)) is None


def test_multiple_plate_accepts_five_and_rejects_six(run_dialog, tmp_path):
    plates = [tmp_path / f"plate-{index}.csv" for index in range(6)]
    for plate in plates:
        plate.write_text("Well,Plasmid,Mass (ng)\n")
    run_dialog.return_value = plate_result([str(plate) for plate in plates[:5]])
    assert choose_plate_files(str(tmp_path)) == [str(plate) for plate in plates[:5]]
    run_dialog.return_value = plate_result([str(plate) for plate in plates])
    with pytest.raises(PlatePickerError, match="no more than 5"):
        choose_plate_files(str(tmp_path))


def test_multiple_plate_deduplicates_paths_and_aliases_in_order(run_dialog, tmp_path):
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    first.touch()
    second.touch()
    alias = tmp_path / "alias.csv"
    alias.symlink_to(first)
    run_dialog.return_value = plate_result([str(first), str(first), str(alias), str(second)])
    assert choose_plate_files(str(tmp_path)) == [str(first), str(second)]


@pytest.mark.parametrize("selection", ["missing.csv", "plate.xlsx", "folder.csv", "relative.csv"])
def test_multiple_plate_rejects_entire_batch_for_unusable_path(run_dialog, tmp_path, selection):
    valid = tmp_path / "valid.csv"
    valid.touch()
    selected = tmp_path / selection
    if selection == "plate.xlsx":
        selected.write_text("not a CSV")
    elif selection == "folder.csv":
        selected.mkdir()
    output = selection if selection == "relative.csv" else str(selected)
    run_dialog.return_value = plate_result([str(valid), output])
    with pytest.raises(PlatePickerError, match="existing CSV files"):
        choose_plate_files(str(tmp_path))


def test_multiple_plate_rejects_unreadable_file(run_dialog, tmp_path, monkeypatch):
    selected = tmp_path / "unreadable.csv"
    selected.touch()
    run_dialog.return_value = plate_result([str(selected)])
    monkeypatch.setattr(Path, "open", Mock(side_effect=PermissionError("Permission denied")))
    with pytest.raises(PlatePickerError, match="readable, existing CSV files"):
        choose_plate_files(str(tmp_path))


@pytest.mark.parametrize("output", ["not json", '"/tmp/plate.csv"', '[null]'])
def test_multiple_plate_rejects_malformed_or_wrong_type_response(run_dialog, tmp_path, output):
    run_dialog.return_value = subprocess.CompletedProcess([], 0, stdout=output + "\n", stderr="")
    with pytest.raises(PlatePickerError, match="Could not read the selected plate paths"):
        choose_plate_files(str(tmp_path))
