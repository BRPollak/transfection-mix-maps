"""Build a self-contained Apple Silicon release from the locked environment.

Run with an isolated, locked Python 3.12 environment (see BUILDING.md).
Nothing is installed in Applications on the build Mac.
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
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from app_version import VERSION

APP_FILES = ["app.py", "app_version.py", "core.py", "sources.py", "native_dialogs.py",
             "workflow.py", "plate_preview.py", "plate_formats.py", "launch.py", ".streamlit/config.toml",
             "assets/mix-maps-icon.png"]
DEV_FILES = {"_virtualenv.pth", "_virtualenv.py", "_pytest", "pytest", "pluggy", "iniconfig", "py.py"}
DEV_PREFIXES = ("pytest-", "pluggy-", "iniconfig-")
APP_NAME = "Transfection Mix Maps.app"
BUNDLE_ICON = "mix-maps.icns"
BUNDLE_ID = "edu.uscd.brpollak.transfection-mix-maps"
PACKAGE_ID = BUNDLE_ID + ".installer"


def ignore(directory, names):
    return {n for n in names if n == "__pycache__" or n == ".DS_Store" or n.endswith(".pyc")}


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def validate_build_environment():
    if sys.platform != "darwin" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("Build with the app's macOS Python 3.12 environment.")
    packages = Path(sysconfig.get_paths()["purelib"]).resolve()
    external = sorted({d.metadata["Name"] for d in importlib.metadata.distributions()
                       if not Path(d.locate_file("")).resolve().is_relative_to(packages)})
    if external:
        raise RuntimeError(
            "Build with an isolated uv sync --locked environment. Dependencies inherited "
            "from outside this environment would be omitted: " + ", ".join(external)
        )
    for name in ["streamlit", "pandas", "openpyxl", "gspread", "google-auth-oauthlib"]:
        importlib.metadata.distribution(name)  # Fail before creating an incomplete bundle.


def checksum(artifact):
    with artifact.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    artifact.with_suffix(artifact.suffix + ".sha256").write_text(f"{digest}  {artifact.name}\n")
    return {"path": str(artifact), "bytes": artifact.stat().st_size, "sha256": digest}


def build_installer(app, pkg):
    """Use Installer's atomic bundle upgrade; never touch Application Support.

    The fixed destination matches the installed drag-and-drop v0.1 app. No
    uninstall script is needed: upgrade replaces the whole bundle, including
    files removed since v0.1. Disable relocation so a mounted DMG or build copy
    cannot become the installation target. No user data is in the payload.
    """
    pkg.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="installer-", dir=app.parent.parent) as work:
        work = Path(work)
        root = work / "payload"
        shutil.copytree(app, root / APP_NAME, symlinks=True)
        components = [{
            "RootRelativeBundlePath": APP_NAME,
            "BundleIsRelocatable": False,
            "BundleIsVersionChecked": True,
            "BundleHasStrictIdentifier": True,
            "BundleOverwriteAction": "upgrade",
        }]
        component_plist = work / "components.plist"
        component_plist.write_bytes(plistlib.dumps(components))
        component = work / "Application.pkg"
        run("/usr/bin/pkgbuild", "--root", root, "--component-plist", component_plist,
            "--identifier", PACKAGE_ID, "--version", VERSION,
            "--install-location", "/Applications", "--ownership", "recommended", component)

        distribution = ET.Element("installer-gui-script", minSpecVersion="2")
        ET.SubElement(distribution, "title").text = f"Transfection Mix Maps {VERSION}"
        ET.SubElement(distribution, "options", customize="never",
                      **{"require-scripts": "false", "hostArchitectures": "arm64"})
        ET.SubElement(distribution, "domains", enable_anywhere="false",
                      enable_currentUserHome="false", enable_localSystem="true")
        versions = ET.SubElement(ET.SubElement(distribution, "volume-check"), "allowed-os-versions")
        ET.SubElement(versions, "os-version", min="14.0")
        ET.SubElement(distribution, "readme", file="Read Me.txt")
        outline = ET.SubElement(distribution, "choices-outline")
        ET.SubElement(outline, "line", choice="application")
        choice = ET.SubElement(distribution, "choice", id="application", visible="false",
                               title="Transfection Mix Maps")
        ET.SubElement(choice, "pkg-ref", id=PACKAGE_ID)
        ET.SubElement(distribution, "pkg-ref", id=PACKAGE_ID, version=VERSION,
                      onConclusion="none").text = component.name
        close = ET.SubElement(ET.SubElement(distribution, "pkg-ref", id=PACKAGE_ID), "must-close")
        ET.SubElement(close, "app", id=BUNDLE_ID)
        distribution_path = work / "Distribution.xml"
        ET.ElementTree(distribution).write(distribution_path, encoding="utf-8", xml_declaration=True)
        installer_resources = work / "resources"
        installer_resources.mkdir()
        shutil.copy2(PROJECT / "packaging" / "Read Me.txt", installer_resources / "Read Me.txt")
        run("/usr/bin/productbuild", "--distribution", distribution_path,
            "--package-path", work, "--resources", installer_resources, pkg)


def finish_package(staging, dmg=None, pkg=None):
    app = staging / APP_NAME
    resources = app / "Contents" / "Resources"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    if info["CFBundleIdentifier"] != BUNDLE_ID or info["CFBundleShortVersionString"] != VERSION:
        raise RuntimeError("The staged app identity/version does not match this source.")
    bundled_files = {str(p.relative_to(resources / "app"))
                     for p in (resources / "app").rglob("*") if p.is_file()}
    if bundled_files != set(APP_FILES):
        raise RuntimeError("The staged app must contain only the allowlisted application files.")
    for name in APP_FILES:
        if (resources / "app" / name).read_bytes() != (PROJECT / name).read_bytes():
            raise RuntimeError(f"Rebuild the staged app: {name} differs from this source.")
    icon = resources / BUNDLE_ICON
    if (info.get("CFBundleIconFile") != BUNDLE_ICON or not icon.is_file()
            or icon.read_bytes() != (PROJECT / "assets" / BUNDLE_ICON).read_bytes()):
        raise RuntimeError("Rebuild the staged app: its app icon is missing or differs from this source.")
    for name in ["LICENSE", "README.md", "BUILDING.md", "VALIDATION.md", "CHANGELOG.md"]:
        shutil.copy2(PROJECT / name, resources / name)
    shutil.copy2(PROJECT / "packaging" / "Read Me.txt", staging / "Read Me.txt")
    run("/usr/bin/codesign", "--force", "--deep", "--sign", "-", "--timestamp=none", app)
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", app)
    artifacts = []
    if pkg:
        build_installer(app, pkg)
        artifacts.append(checksum(pkg))
    if dmg:
        if not (staging / "Applications").is_symlink():
            (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
        dmg.parent.mkdir(parents=True, exist_ok=True)
        run("/usr/bin/hdiutil", "create", "-volname", f"Transfection Mix Maps {VERSION}",
            "-srcfolder", staging, "-format", "UDZO", "-ov", dmg)
        run("/usr/bin/hdiutil", "verify", dmg)
        artifacts.append(checksum(dmg))
    print(json.dumps({"app": str(app), "version": VERSION, "artifacts": artifacts}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--dmg", type=Path)
    parser.add_argument("--pkg", type=Path, help="Installer that replaces the app in /Applications")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--bundle-only", action="store_true")
    modes.add_argument("--package-only", action="store_true")
    args = parser.parse_args()
    if not args.bundle_only and not (args.dmg or args.pkg):
        parser.error("Specify --pkg and/or --dmg, or --bundle-only.")
    staging = args.staging.resolve()
    app = staging / APP_NAME
    outputs = [p.resolve() for p in (args.dmg, args.pkg) if p]
    if any(p.exists() for p in outputs):
        parser.error("Build output already exists; use a new filename.")
    if any(p.is_relative_to(staging) for p in outputs):
        parser.error("Build outputs must be outside the staging directory.")
    if args.package_only:
        if not app.is_dir():
            parser.error("Packaging requires an existing staged app.")
        finish_package(staging, args.dmg, args.pkg)
        return
    if app.exists():
        parser.error("Build destination already exists; use a fresh staging folder.")
    validate_build_environment()
    resources = app / "Contents" / "Resources"
    bundled_app = resources / "app"
    runtime = resources / "runtime"
    executable = app / "Contents" / "MacOS" / "MixMaps"
    bundled_app.mkdir(parents=True)
    executable.parent.mkdir()
    (runtime / "bin").mkdir(parents=True)

    base = Path(sys.base_prefix)
    python_minor = f"python{sys.version_info.major}.{sys.version_info.minor}"
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
    shutil.copy2(PROJECT / "assets" / BUNDLE_ICON, resources / BUNDLE_ICON)
    for name in ["LICENSE", "README.md", "BUILDING.md", "VALIDATION.md", "CHANGELOG.md"]:
        shutil.copy2(PROJECT / name, resources / name)
    package_inventory = sorted(
        [{"name": d.metadata["Name"], "version": d.version}
         for d in importlib.metadata.distributions(path=[str(packages)])],
        key=lambda d: d["name"].lower(),
    )
    (resources / "dependencies.json").write_text(json.dumps(package_inventory, indent=2) + "\n")
    (resources / "THIRD_PARTY_NOTICES.txt").write_text(
        "This release includes CPython and third-party Python packages.\n"
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
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": "MixMaps",
        "CFBundleIconFile": BUNDLE_ICON,
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
    # The app uses an ad hoc signature; it is not Developer ID signed or notarized.
    run("/usr/bin/codesign", "--force", "--deep", "--sign", "-", "--timestamp=none", app)
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", app)
    if args.bundle_only:
        print(json.dumps({"app": str(app), "version": VERSION}, indent=2))
    else:
        finish_package(staging, args.dmg, args.pkg)


if __name__ == "__main__":
    main()
