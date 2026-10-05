"""Exercise the real macOS package policy without installing on the host."""
import importlib.util
import plistlib
import re
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location(
    "build_macos", Path(__file__).resolve().parents[1] / "packaging" / "build_macos.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_release_version_matches_project_lock_and_launcher():
    project = tomllib.loads((builder.PROJECT / "pyproject.toml").read_text())["project"]
    lock = tomllib.loads((builder.PROJECT / "uv.lock").read_text())
    locked_project = next(package for package in lock["package"] if package["name"] == project["name"])
    launcher = (builder.PROJECT / "packaging" / "Launcher.swift").read_text()
    fallback = re.search(
        r'forInfoDictionaryKey: "CFBundleShortVersionString"\) as\? String \?\? "([^"]+)"',
        launcher,
    )
    assert fallback is not None, "Check the launcher's fallback version when its version lookup changes."
    assert builder.VERSION == project["version"] == locked_project["version"] == fallback.group(1)


def test_build_rejects_dependencies_borrowed_from_an_installed_app(monkeypatch, tmp_path):
    monkeypatch.setattr(builder.sys, "platform", "darwin")
    monkeypatch.setattr(builder.sys, "version_info", (3, 12))
    monkeypatch.setattr(builder.sysconfig, "get_paths", lambda: {"purelib": str(tmp_path / "venv")})
    external = SimpleNamespace(metadata={"Name": "pandas"}, locate_file=lambda _: tmp_path / "old-app")
    monkeypatch.setattr(builder.importlib.metadata, "distributions", lambda: [external])
    with pytest.raises(RuntimeError, match="inherited.*pandas"):
        builder.validate_build_environment()


def make_app(staging):
    app = staging / builder.APP_NAME
    (app / "Contents" / "MacOS").mkdir(parents=True)
    info = {
        "CFBundleIdentifier": builder.BUNDLE_ID,
        "CFBundleVersion": builder.VERSION,
        "CFBundleShortVersionString": builder.VERSION,
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "Test",
    }
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
    executable = app / "Contents" / "MacOS" / "Test"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    return app


@pytest.mark.skipif(sys.platform != "darwin", reason="Uses Apple's packaging tools")
def test_real_installer_replaces_only_app_and_requires_quit(tmp_path):
    staging = tmp_path / "staging"
    app = make_app(staging)
    # Unrelated/private staging siblings must never enter the Installer payload.
    (staging / "local_state").mkdir()
    private = staging / "local_state" / "authorized_user.json"
    private.write_text('{"token": "synthetic-must-not-be-packaged"}')
    package = tmp_path / "test.pkg"
    builder.build_installer(app, package)
    expanded = tmp_path / "expanded"
    subprocess.run(["/usr/sbin/pkgutil", "--expand-full", package, expanded], check=True)
    component = expanded / "Application.pkg"
    info = ET.parse(component / "PackageInfo").getroot()
    assert info.attrib["version"] == builder.VERSION
    assert info.attrib["install-location"] == "/Applications"
    assert info.attrib["relocatable"] == "false"
    assert info.find("upgrade-bundle/bundle").attrib["id"] == builder.BUNDLE_ID
    assert info.find("strict-identifier/bundle").attrib["id"] == builder.BUNDLE_ID
    assert info.find("bundle-version/bundle").attrib["id"] == builder.BUNDLE_ID
    assert list(info.find("relocate")) == []
    assert not (component / "Scripts").exists()
    assert {p.name for p in (component / "Payload").iterdir()} == {builder.APP_NAME}
    assert private.read_text() == '{"token": "synthetic-must-not-be-packaged"}'
    distribution = ET.parse(expanded / "Distribution").getroot()
    assert distribution.find("title").text == f"Transfection Mix Maps {builder.VERSION}"
    assert distribution.find("pkg-ref").attrib["version"] == builder.VERSION
    assert distribution.find("pkg-ref/must-close/app").attrib["id"] == builder.BUNDLE_ID
    assert distribution.find("options").attrib["hostArchitectures"] == "arm64"
    assert distribution.find("volume-check/allowed-os-versions/os-version").attrib["min"] == "14.0"
    assert distribution.find("domains").attrib == {
        "enable_anywhere": "false", "enable_currentUserHome": "false", "enable_localSystem": "true"
    }


@pytest.mark.parametrize("problem", ["wrong_version", "private_state", "stale_source"])
def test_repackaging_rejects_stale_or_private_app_before_signing(tmp_path, problem):
    app = make_app(tmp_path)
    resources = app / "Contents" / "Resources"
    for name in builder.APP_FILES:
        target = resources / "app" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((builder.PROJECT / name).read_bytes())
    if problem == "wrong_version":
        info_path = app / "Contents" / "Info.plist"
        info = plistlib.loads(info_path.read_bytes())
        info["CFBundleShortVersionString"] = "0.1"
        info_path.write_bytes(plistlib.dumps(info))
    elif problem == "private_state":
        private = resources / "app" / "local_state" / "token.json"
        private.parent.mkdir()
        private.write_text('{"token": "synthetic-private-data"}')
    else:
        (resources / "app" / "app_version.py").write_text('VERSION = "0.1"\n')
    output = tmp_path / "test.pkg"
    with pytest.raises(RuntimeError):
        builder.finish_package(tmp_path, pkg=output)
    assert not output.exists()
