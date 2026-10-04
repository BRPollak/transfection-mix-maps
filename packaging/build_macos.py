"""Build a self-contained Apple Silicon testing release from the locked environment.

Run with this project's .venv/bin/python. Nothing is installed on the build Mac.
The Python runtime and dependency licenses are retained; private state is excluded.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import plistlib
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from app_version import VERSION

APP_FILES = ["app.py", "app_version.py", "core.py", "sources.py", "native_dialogs.py",
             "workflow.py", "plate_preview.py", "launch.py", ".streamlit/config.toml"]
DEV_FILES = {"_virtualenv.pth", "_virtualenv.py", "_pytest", "pytest", "pluggy", "iniconfig", "py.py"}
DEV_PREFIXES = ("pytest-", "pluggy-", "iniconfig-")


def ignore(directory, names):
    return {n for n in names if n == "__pycache__" or n == ".DS_Store" or n.endswith(".pyc")}


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def finish_package(staging, dmg):
    app = staging / "Transfection Mix Maps.app"
    resources = app / "Contents" / "Resources"
    for name in ["README.md", "VALIDATION.md", "CHANGELOG.md"]:
        shutil.copy2(PROJECT / name, resources / name)
    shutil.copy2(PROJECT / "packaging" / "Read Me.txt", staging / "Read Me.txt")
    run("/usr/bin/codesign", "--force", "--deep", "--sign", "-", "--timestamp=none", app)
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", app)
    if not (staging / "Applications").is_symlink():
        (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
    dmg.parent.mkdir(parents=True, exist_ok=True)
    run("/usr/bin/hdiutil", "create", "-volname", f"Transfection Mix Maps {VERSION}",
        "-srcfolder", staging, "-format", "UDZO", "-ov", dmg)
    run("/usr/bin/hdiutil", "verify", dmg)
    with dmg.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    dmg.with_suffix(".dmg.sha256").write_text(f"{digest}  {dmg.name}\n")
    print(json.dumps({"app": str(app), "dmg": str(dmg), "bytes": dmg.stat().st_size,
                      "version": VERSION, "sha256": digest}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--bundle-only", action="store_true")
    modes.add_argument("--package-only", action="store_true")
    args = parser.parse_args()
    staging = args.staging.resolve()
    app = staging / "Transfection Mix Maps.app"
    if args.package_only:
        if not app.is_dir() or args.dmg.exists():
            parser.error("Packaging requires an existing staged app and a new DMG filename.")
        finish_package(staging, args.dmg)
        return
    if app.exists() or args.dmg.exists():
        parser.error("Build destinations already exist; use a fresh staging folder and DMG filename.")
    resources = app / "Contents" / "Resources"
    bundled_app = resources / "app"
    runtime = resources / "runtime"
    executable = app / "Contents" / "MacOS" / "MixMaps"
    bundled_app.mkdir(parents=True)
    executable.parent.mkdir()
    (runtime / "bin").mkdir(parents=True)

    base = Path(sys.base_prefix)
    python_minor = f"python{sys.version_info.major}.{sys.version_info.minor}"
    if sys.platform != "darwin" or sys.version_info[:2] != (3, 12):
        parser.error("Build with the app's macOS Python 3.12 environment.")
    shutil.copy2(base / "bin" / python_minor, runtime / "bin" / python_minor)
    (runtime / "bin" / "python3").symlink_to(python_minor)
    (runtime / "bin" / "python").symlink_to(python_minor)

    def runtime_ignore(directory, names):
        excluded = ignore(directory, names)
        if Path(directory) == base / "lib":
            excluded.add("pkgconfig")  # Build-only metadata contains absolute symlinks.
        if Path(directory) == base / "lib" / python_minor:
            excluded.add("site-packages")
        return excluded

    shutil.copytree(base / "lib", runtime / "lib", symlinks=True, ignore=runtime_ignore)
    if (base / "share").exists():
        shutil.copytree(base / "share", runtime / "share", symlinks=True,
                        ignore=lambda directory, names: ignore(directory, names) | {"man"})
    packages = runtime / "lib" / python_minor / "site-packages"
    source_packages = Path(sysconfig.get_paths()["purelib"])

    def package_ignore(directory, names):
        excluded = ignore(directory, names)
        if Path(directory) == source_packages:
            excluded.update(n for n in names if n in DEV_FILES or n.startswith(DEV_PREFIXES))
        return excluded

    shutil.copytree(source_packages, packages, symlinks=True, ignore=package_ignore)
    for name in APP_FILES:
        target = bundled_app / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT / name, target)
    for name in ["README.md", "VALIDATION.md", "CHANGELOG.md"]:
        shutil.copy2(PROJECT / name, resources / name)
    package_inventory = sorted(
        [{"name": d.metadata["Name"], "version": d.version}
         for d in importlib.metadata.distributions(path=[str(packages)])],
        key=lambda d: d["name"].lower(),
    )
    (resources / "dependencies.json").write_text(json.dumps(package_inventory, indent=2) + "\n")
    (resources / "THIRD_PARTY_NOTICES.txt").write_text(
        "This testing release includes CPython and third-party Python packages.\n"
        "CPython's license is in runtime/lib/python3.12/LICENSE.txt.\n"
        "Package copyright notices and licenses are retained in runtime/lib/python3.12/"
        "site-packages/*dist-info/ and the package directories.\n"
        "See dependencies.json for the exact included package versions.\n"
    )
    if not (runtime / "lib" / python_minor / "LICENSE.txt").is_file():
        raise RuntimeError("The Python license must be included in the distribution.")
    # A bundle must not depend on symlinks into the builder's machine.
    for path in resources.rglob("*"):
        if path.is_symlink() and not path.resolve().is_relative_to(resources):
            raise RuntimeError(f"Nonportable symlink: {path}")
    plist = {
        "CFBundleName": "Transfection Mix Maps",
        "CFBundleDisplayName": "Transfection Mix Maps",
        "CFBundleIdentifier": "edu.uscd.brpollak.transfection-mix-maps",
        "CFBundleExecutable": "MixMaps",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "14.0",
        "LSArchitecturePriority": ["arm64"],
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
        "NSHumanReadableCopyright": "Benjamin Pollak",
    }
    with (app / "Contents" / "Info.plist").open("wb") as handle:
        plistlib.dump(plist, handle)
    run("/usr/bin/xcrun", "swiftc", "-swift-version", "5", "-O",
        "-module-cache-path", staging.parent / "swift-module-cache",
        "-target", "arm64-apple-macos14.0", "-framework", "AppKit",
        PROJECT / "packaging" / "Launcher.swift", "-o", executable)
    # Ad-hoc signing is for this local test release, not Developer ID/notarization.
    run("/usr/bin/codesign", "--force", "--deep", "--sign", "-", "--timestamp=none", app)
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", app)
    if args.bundle_only:
        print(json.dumps({"app": str(app), "version": VERSION}, indent=2))
    else:
        finish_package(staging, args.dmg)


if __name__ == "__main__":
    main()
