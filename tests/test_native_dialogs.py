"""No test launches an actual native dialog."""
import subprocess
from unittest.mock import Mock

import pytest

import native_dialogs
from native_dialogs import (
    FolderPickerError, NativeDialogError, PlatePickerError,
    choose_output_folder, choose_plate_file,
)


@pytest.fixture
def run_dialog(monkeypatch):
    monkeypatch.setattr(native_dialogs.sys, "platform", "darwin")
    runner = Mock()
    monkeypatch.setattr(native_dialogs.subprocess, "run", runner)
    return runner


def test_selected_folder_and_script_arguments_are_safe(run_dialog, tmp_path):
    # This must remain one process argument, including quotes and shell syntax.
    folder = tmp_path / 'Plates "today" \' $(touch INJECTED); `echo nope`'
    folder.mkdir()
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 0, stdout=str(folder) + "/\n", stderr=""
    )

    assert choose_output_folder(str(folder)) == str(folder)
    args, kwargs = run_dialog.call_args
    assert args[0] == [
        "/usr/bin/osascript", "-e", native_dialogs._CHOOSE_FOLDER_SCRIPT, str(folder)
    ]
    assert str(folder) not in native_dialogs._CHOOSE_FOLDER_SCRIPT
    assert kwargs == {
        "capture_output": True, "text": True, "check": False, "timeout": 300
    }


def test_new_output_folder_starts_at_existing_parent(run_dialog, tmp_path):
    run_dialog.return_value = subprocess.CompletedProcess([], 0, stdout="\n", stderr="")
    missing = tmp_path / "new" / "generated"
    assert choose_output_folder(str(missing)) is None
    assert run_dialog.call_args.args[0][-1] == str(tmp_path)
    assert not missing.exists()


@pytest.mark.parametrize("output", ["", "\n"])
def test_cancel_keeps_saved_folder_unchanged(run_dialog, tmp_path, output):
    run_dialog.return_value = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
    assert choose_output_folder(str(tmp_path)) is None


def test_native_cancel_error_is_not_reported_as_failure(run_dialog, tmp_path):
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 1, stdout="", stderr="execution error: User canceled. (-128)\n"
    )
    assert choose_output_folder(str(tmp_path)) is None


def test_whitespace_and_newlines_in_directory_name_are_preserved(run_dialog, tmp_path):
    folder = tmp_path / " folder\nname "
    folder.mkdir()
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 0, stdout=str(folder) + "/\n", stderr=""
    )
    assert choose_output_folder(str(tmp_path)) == str(folder)


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


def test_plate_selection_passes_path_safely_and_returns_existing_csv(run_dialog, tmp_path):
    folder = tmp_path / 'Plates "today" \' $(touch INJECTED); `echo nope`'
    folder.mkdir()
    plate = folder / "run\n01.CSV"
    plate.write_text("Well,Plasmid,Mass (ng)\n")
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 0, stdout=str(plate) + "\n", stderr=""
    )

    assert choose_plate_file(str(folder)) == str(plate)
    assert run_dialog.call_args.args[0] == [
        "/usr/bin/osascript", "-e", native_dialogs._CHOOSE_PLATE_SCRIPT, str(folder)
    ]
    assert str(folder) not in native_dialogs._CHOOSE_PLATE_SCRIPT
    assert not run_dialog.call_args.kwargs.get("shell", False)


@pytest.mark.parametrize("output", ["", "\n"])
def test_plate_cancel_returns_none(run_dialog, tmp_path, output):
    run_dialog.return_value = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
    assert choose_plate_file(str(tmp_path)) is None


def test_plate_native_cancel_error_returns_none(run_dialog, tmp_path):
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 1, stdout="", stderr="execution error: User canceled. (-128)\n"
    )
    assert choose_plate_file(str(tmp_path)) is None


@pytest.mark.parametrize("selection", ["missing.csv", "plate.xlsx", "folder.csv", "relative.csv"])
def test_plate_requires_existing_absolute_csv_file(run_dialog, tmp_path, selection):
    selected = tmp_path / selection
    if selection == "plate.xlsx":
        selected.write_text("not a CSV")
    elif selection == "folder.csv":
        selected.mkdir()
    output = selection if selection == "relative.csv" else str(selected)
    run_dialog.return_value = subprocess.CompletedProcess(
        [], 0, stdout=output + "\n", stderr=""
    )
    with pytest.raises(PlatePickerError, match="existing CSV file"):
        choose_plate_file(str(tmp_path))


def test_plate_timeout_raises_specific_error(run_dialog, tmp_path):
    run_dialog.side_effect = subprocess.TimeoutExpired("osascript", 300)
    with pytest.raises(PlatePickerError, match="Choose plate CSV"):
        choose_plate_file(str(tmp_path))


def test_plate_non_mac_error_does_not_launch_process(run_dialog, monkeypatch):
    monkeypatch.setattr(native_dialogs.sys, "platform", "linux")
    with pytest.raises(PlatePickerError, match="requires macOS"):
        choose_plate_file("/tmp")
    run_dialog.assert_not_called()


def test_picker_errors_share_a_common_base():
    assert issubclass(FolderPickerError, NativeDialogError)
    assert issubclass(PlatePickerError, NativeDialogError)


def test_native_pickers_allow_only_existing_selections():
    for script in (native_dialogs._CHOOSE_FOLDER_SCRIPT, native_dialogs._CHOOSE_PLATE_SCRIPT):
        assert "setCanCreateDirectories:false" in script
        assert "setCanCreateDirectories:true" not in script
        assert "setAllowsMultipleSelection:false" in script
    assert "setCanChooseDirectories:false" in native_dialogs._CHOOSE_PLATE_SCRIPT
    assert "setCanChooseFiles:true" in native_dialogs._CHOOSE_PLATE_SCRIPT
    assert 'typeWithFilenameExtension:"csv"' in native_dialogs._CHOOSE_PLATE_SCRIPT
    assert "setAllowsOtherFileTypes:false" in native_dialogs._CHOOSE_PLATE_SCRIPT
