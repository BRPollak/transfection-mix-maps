"""Native dialogs for the app running locally on a Mac.

These dialogs appear on the computer running Streamlit. Call them only in
response to a button click, never while rendering the page or during tests.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


class NativeDialogError(RuntimeError):
    """A native file or folder chooser failed."""


class FolderPickerError(NativeDialogError):
    """The native folder chooser could not return a usable directory."""


class PlatePickerError(NativeDialogError):
    """The native plate chooser could not return an existing CSV file."""


# AppKit activates the dialog's own process; it does not control Finder or
# System Events and therefore does not ask for permission to automate them.
# The path is a process argument, never interpolated into AppleScript code.
_CHOOSE_FOLDER_SCRIPT = '''
use framework "Foundation"
use framework "AppKit"

on run argv
    set dialogApp to current application's NSApplication's sharedApplication()
    dialogApp's setActivationPolicy:1
    dialogApp's activateIgnoringOtherApps:true
    set folderPanel to current application's NSOpenPanel's openPanel()
    folderPanel's setTitle:"Save Excel files to"
    folderPanel's setMessage:"Choose the folder for your Excel mix maps."
    folderPanel's setPrompt:"Choose folder"
    folderPanel's setCanChooseDirectories:true
    folderPanel's setCanChooseFiles:false
    folderPanel's setAllowsMultipleSelection:false
    folderPanel's setCanCreateDirectories:false
    folderPanel's setDirectoryURL:(current application's NSURL's fileURLWithPath:(item 1 of argv))
    set modalResponse to folderPanel's runModal()
    if modalResponse is not 1 then return ""
    return (folderPanel's |URL|()'s |path|()) as text
end run
'''


_CHOOSE_PLATE_SCRIPT = '''
use framework "Foundation"
use framework "AppKit"
use framework "UniformTypeIdentifiers"

on run argv
    set dialogApp to current application's NSApplication's sharedApplication()
    dialogApp's setActivationPolicy:1
    dialogApp's activateIgnoringOtherApps:true
    set filePanel to current application's NSOpenPanel's openPanel()
    filePanel's setTitle:"Choose plate CSV"
    filePanel's setMessage:"Choose an existing plate CSV. Excel files will save beside it by default."
    filePanel's setPrompt:"Choose CSV"
    filePanel's setCanChooseDirectories:false
    filePanel's setCanChooseFiles:true
    filePanel's setAllowsMultipleSelection:false
    filePanel's setCanCreateDirectories:false
    set csvType to current application's UTType's typeWithFilenameExtension:"csv"
    filePanel's setAllowedContentTypes:{csvType}
    filePanel's setAllowsOtherFileTypes:false
    filePanel's setDirectoryURL:(current application's NSURL's fileURLWithPath:(item 1 of argv))
    set modalResponse to filePanel's runModal()
    if modalResponse is not 1 then return ""
    return (filePanel's |URL|()'s |path|()) as text
end run
'''


_CHOOSE_PLATES_SCRIPT = '''
use framework "Foundation"
use framework "AppKit"
use framework "UniformTypeIdentifiers"

on run argv
    set dialogApp to current application's NSApplication's sharedApplication()
    dialogApp's setActivationPolicy:1
    dialogApp's activateIgnoringOtherApps:true
    set filePanel to current application's NSOpenPanel's openPanel()
    filePanel's setTitle:"Choose plate CSVs"
    filePanel's setMessage:"Choose up to 5 existing plate CSV files."
    filePanel's setPrompt:"Choose CSVs"
    filePanel's setCanChooseDirectories:false
    filePanel's setCanChooseFiles:true
    filePanel's setAllowsMultipleSelection:true
    filePanel's setCanCreateDirectories:false
    set csvType to current application's UTType's typeWithFilenameExtension:"csv"
    filePanel's setAllowedContentTypes:{csvType}
    filePanel's setAllowsOtherFileTypes:false
    filePanel's setDirectoryURL:(current application's NSURL's fileURLWithPath:(item 1 of argv))
    set modalResponse to filePanel's runModal()
    if modalResponse is not 1 then return ""
    set selectedURLs to filePanel's URLs()
    set selectedPaths to selectedURLs's valueForKey:"path"
    set jsonData to current application's NSJSONSerialization's dataWithJSONObject:selectedPaths options:0 |error|:(missing value)
    if jsonData is missing value then error "Could not read the selected CSV paths."
    return (current application's NSString's alloc()'s initWithData:jsonData encoding:(current application's NSUTF8StringEncoding)) as text
end run
'''


def _initial_directory(current_folder: str) -> Path:
    """Use the saved directory, or its closest existing parent on first use."""
    try:
        location = Path(current_folder).expanduser().absolute()
        while not location.is_dir() and location != location.parent:
            location = location.parent
        if location.is_dir():
            return location
    except (OSError, RuntimeError, ValueError):
        pass
    return Path.cwd()


def _run_picker(script: str, current_folder: str,
                error_class: type[NativeDialogError], dialog_name: str,
                button_label: str) -> str | None:
    """Run a picker with a path argument, preserving cancellation and names."""
    if sys.platform != "darwin":
        raise error_class(
            f"The {dialog_name} requires macOS. Open this local app on your Mac "
            f"and click '{button_label}' to select an existing location."
        )

    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script,
             str(_initial_directory(current_folder))],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        raise error_class(
            f"The {dialog_name} closed after five minutes. Click "
            f"'{button_label}' again to make your selection."
        ) from exc
    except OSError as exc:
        raise error_class(
            f"Could not open the macOS {dialog_name}. Make sure the app is "
            f"running on your Mac, then try again. Details: {exc}"
        ) from exc

    if result.returncode != 0:
        detail = result.stderr.strip()
        if re.search(r"\(-128\)\s*$", detail):
            return None
        raise error_class(
            f"macOS could not open the {dialog_name}. Try again and check for "
            "a dialog behind the browser. "
            + (f"Details: {detail}" if detail else f"Exit code: {result.returncode}.")
        )

    # osascript appends one line ending. Preserve whitespace in folder names.
    selected = result.stdout.removesuffix("\n")
    return selected or None


def choose_output_folder(current_folder: str) -> str | None:
    """Choose an existing output folder; return None when canceled.

    The chosen path is returned without changing preferences or creating any
    directories. The caller should persist it only when a path is returned.
    """
    selected = _run_picker(_CHOOSE_FOLDER_SCRIPT, current_folder,
                           FolderPickerError, "folder chooser", "Save Excel files to")
    if not selected:
        return None
    try:
        folder = Path(selected)
        if not folder.is_absolute() or not folder.is_dir():
            raise FolderPickerError(
                "The selected folder is no longer available. Click 'Save Excel "
                "files to' again and choose an existing folder."
            )
        return str(folder)
    except (OSError, ValueError) as exc:
        raise FolderPickerError(
            "Could not access the selected folder. Choose another folder on "
            "your Mac and try again."
        ) from exc


def choose_plate_file(current_folder: str) -> str | None:
    """Choose one existing plate CSV; return None when canceled.

    The caller can read this local path and use its parent as the default
    output directory. This function creates no files or directories.
    """
    selected = _run_picker(_CHOOSE_PLATE_SCRIPT, current_folder,
                           PlatePickerError, "plate file chooser", "Choose plate CSV")
    if not selected:
        return None
    try:
        plate = Path(selected)
        if not plate.is_absolute() or not plate.is_file() or plate.suffix.lower() != ".csv":
            raise PlatePickerError(
                "The selected plate must be an existing CSV file. Click "
                "'Choose plate CSV' again and select a .csv file."
            )
        return str(plate)
    except (OSError, ValueError) as exc:
        raise PlatePickerError(
            "Could not access the selected plate CSV. Choose an existing CSV "
            "file on your Mac and try again."
        ) from exc


def choose_plate_files(current_folder: str) -> list[str] | None:
    """Choose up to five readable plate CSVs, preserving order and cancellation.

    JSON keeps each absolute path intact, including embedded newlines. Repeated
    paths (including symlink aliases) count only once. A bad selection rejects
    the entire batch; no file or directory is changed by this chooser.
    """
    selected = _run_picker(_CHOOSE_PLATES_SCRIPT, current_folder,
                           PlatePickerError, "plate file chooser", "Choose plate CSVs")
    if selected is None:
        return None
    try:
        paths = json.loads(selected)
    except (TypeError, ValueError) as exc:
        raise PlatePickerError(
            "Could not read the selected plate paths. Click 'Choose plate CSVs' "
            "again and choose up to 5 CSV files."
        ) from exc
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise PlatePickerError(
            "Could not read the selected plate paths. Click 'Choose plate CSVs' "
            "again and choose up to 5 CSV files."
        )
    if not paths:
        return None

    unique_paths, seen = [], set()
    for path in paths:
        try:
            plate = Path(path)
            if not plate.is_absolute() or not plate.is_file() or plate.suffix.lower() != ".csv":
                raise PlatePickerError(
                    "The selected plates must all be existing CSV files. Click "
                    "'Choose plate CSVs' again and select up to 5 .csv files. "
                    f"Invalid selection: {path!r}."
                )
            identity = plate.resolve(strict=True)
            if identity in seen:
                continue
            # Check readability here so a partially usable batch never escapes
            # the dialog validation. The caller reads and validates CSV content.
            with plate.open("rb") as stream:
                stream.read(1)
            seen.add(identity)
            unique_paths.append(str(plate))
        except (OSError, RuntimeError, ValueError) as exc:
            if isinstance(exc, PlatePickerError):
                raise
            raise PlatePickerError(
                f"Could not access the selected plate CSV {path!r}. Choose "
                "readable, existing CSV files on your Mac and try again."
            ) from exc
    if len(unique_paths) > 5:
        raise PlatePickerError("Choose no more than 5 plate CSV files at once.")
    return unique_paths
