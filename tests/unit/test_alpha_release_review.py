"""tools/alpha_release.py after the review of PR #50: the page's resources (major 2), the WebView2 installer's
identity (major 3) and licence completeness (major 4). Shared fakes come from test_alpha_packaging.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from par_app import alpha_info
from tools import alpha_release

from .test_alpha_packaging import FAKE_ASSETS, FAKE_MANIFEST, INSTALLER, ROOT, _fake_app, _fake_web, _metadata

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("name", list(FAKE_ASSETS))
def test_package_refuses_a_page_whose_script_style_or_font_is_missing_or_empty(tmp_path: Path, name: str) -> None:
    """Major 2: index.html and the fonts alone are a blank window; every resource the page loads must be there."""
    app = _fake_app(tmp_path)
    (app / name).unlink()
    with pytest.raises(ValueError, match="/assets/"):
        alpha_release.validate(app)
    (app / name).write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        alpha_release.validate(app)


def test_package_refuses_a_page_without_a_script(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    (app / "_internal/web/index.html").write_text('<div id="app"></div>', encoding="utf-8")
    with pytest.raises(ValueError, match="names no script"):
        alpha_release.validate(app)


def test_the_real_front_end_build_names_only_files_it_contains() -> None:
    """The page Vite builds (web/dist, when built) passes the same check the package applies."""
    dist = ROOT / "web" / "dist"
    if not (dist / "index.html").is_file():
        pytest.skip("web/dist not built (npm run build)")
    loaded = alpha_release.check_web_folder(dist)
    assert any(path.endswith(".js") for path in loaded) and any(path.endswith(".css") for path in loaded)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"product": "Microsoft Edge", "description": "Microsoft Edge Installer"}, "not a WebView2"),
        ({"size": 1_700_000}, "online bootstrapper"),
        ({"source": "placed by hand", "original_name": "MicrosoftEdgeWebView2RuntimeInstallerX86.exe"}, "x64"),
        ({"source": "placed by hand", "original_name": "MicrosoftEdgeWebView2RuntimeInstallerARM64.exe"}, "x64"),
        ({"source": "placed by hand", "original_name": "webview2.exe"}, "x64"),
        ({"signer": "CN=Someone, O=Someone Else"}, "Microsoft Corporation"),
        ({"version": ""}, "version"),
    ],
)
def test_the_webview2_installer_must_be_the_x64_standalone_runtime_installer(
    change: dict[str, Any], message: str
) -> None:
    """Major 3: a valid Microsoft signature alone also fits Edge, the online bootstrapper or another architecture."""
    alpha_release.check_webview2(INSTALLER)
    alpha_release.check_webview2(
        INSTALLER | {"source": "placed by hand", "original_name": "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"}
    )
    with pytest.raises(ValueError, match=message):
        alpha_release.check_webview2(INSTALLER | change)


def test_metadata_refuses_an_installer_that_fails_the_check(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="online bootstrapper"):
        _metadata(_fake_app(tmp_path), _fake_web(tmp_path), {}, INSTALLER | {"size": 1_700_000})
    assert (tmp_path / alpha_info.APP_NAME / alpha_release.NOTICES).read_bytes() == b"x"  # _fake_app's, untouched


def test_check_webview2_command_feeds_the_build_script(tmp_path: Path) -> None:
    path = tmp_path / "webview2.json"
    path.write_text(json.dumps(INSTALLER | {"size": 10}), encoding="utf-8")
    with pytest.raises(ValueError, match="online bootstrapper"):
        alpha_release.main(["check-webview2", str(path)])
    path.write_text(json.dumps(INSTALLER), encoding="utf-8")
    assert alpha_release.main(["check-webview2", str(path)]) == 0


def test_metadata_fails_and_names_every_component_without_a_licence_text(tmp_path: Path) -> None:
    """Major 4: a component without its licence text stops the build (no silent package) unless it is an
    exception listed in alpha_release.LICENCE_EXCEPTIONS for owner to accept."""
    web = _fake_web(tmp_path)
    (web / "node_modules" / "vue" / "LICENSE").unlink()
    (web / "node_modules" / "echarts" / "LICENSE").unlink()
    (web / "node_modules" / "echarts" / "licenses" / "LICENSE-d3").unlink()
    app = _fake_app(tmp_path)
    with pytest.raises(alpha_release.LicenceIncomplete) as caught:
        _metadata(app, web, {}, INSTALLER)
    assert "vue@3.5.44" in str(caught.value) and "echarts@6.1.0" in str(caught.value)
    assert json.loads((app / alpha_release.MANIFEST).read_text(encoding="utf-8")) == FAKE_MANIFEST  # not rewritten
    assert (app / alpha_release.NOTICES).read_bytes() == b"x"  # _fake_app's, untouched


def test_without_an_exception_the_sdk_and_proxy_tools_gaps_fail(tmp_path: Path) -> None:
    with pytest.raises(alpha_release.LicenceIncomplete) as caught:
        alpha_release.write_metadata(_fake_app(tmp_path), None, _fake_web(tmp_path), {}, INSTALLER, exceptions={})
    assert alpha_release.WEBVIEW2_SDK in str(caught.value) and "proxy_tools" in str(caught.value)


def test_accepted_exceptions_are_listed_in_the_notices_and_manifest(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    manifest = _metadata(app, _fake_web(tmp_path), {}, INSTALLER)
    assert alpha_release.WEBVIEW2_SDK in manifest["licence_exceptions"]
    assert "proxy_tools" in manifest["licence_exceptions"]
    notices = (app / alpha_release.NOTICES).read_text(encoding="utf-8")
    assert "7. Licence texts not included" in notices and "pending owner" in notices
    assert "TO CHECK" not in notices


def test_package_refuses_a_manifest_with_an_unaccepted_licence_gap(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    manifest = FAKE_MANIFEST | {"packages": {"somelib": {"version": "1", "license": "MIT", "files": 0}}}
    (app / alpha_release.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="somelib"):
        alpha_release.validate(app)
    manifest["licence_exceptions"] = {"somelib": "made up here"}
    (app / alpha_release.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="somelib"):  # only LICENCE_EXCEPTIONS may excuse a gap
        alpha_release.validate(app)


def test_build_script_checks_the_installer_identity() -> None:
    script = (ROOT / "build_alpha.ps1").read_text(encoding="utf-8")
    assert "$Tool check-webview2 $WebView2Info" in script and "original_name" in script
    assert "--smoke" in script


EDGE_UPDATE_INSTALLER = INSTALLER | {
    # What Microsoft's x64 Evergreen Standalone Installer reports since 2026-10 (issue #66): the WebView2 name is gone
    # from its VERSIONINFO, which now reads as the Edge Update setup it wraps.
    "size": 214_156_024,
    "version": "1.3.287.9",
    "product": "Microsoft Edge Update",
    "description": "Microsoft Edge Update Setup",
}


def test_the_current_standalone_installer_identifies_as_edge_update_and_is_accepted_by_provenance() -> None:
    """Issue #66: accepted when it came from the official x64 WebView2 link, or was placed by hand under Microsoft's
    exact x64 file name; size and signature are still checked."""
    alpha_release.check_webview2(EDGE_UPDATE_INSTALLER)
    alpha_release.check_webview2(
        EDGE_UPDATE_INSTALLER
        | {"source": "placed by hand", "original_name": "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"}
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        # Edge Update identity without WebView2 provenance: could be any Edge (Update) setup.
        ({"source": "placed by hand", "original_name": "MicrosoftEdgeSetup.exe"}, "not a WebView2"),
        ({"source": "placed by hand", "original_name": "MicrosoftEdgeUpdateSetup_X64.exe"}, "not a WebView2"),
        ({"source": "placed by hand", "original_name": "x64-installer.exe"}, "not a WebView2"),
        ({"size": 1_700_000}, "online bootstrapper"),
        ({"signer": "CN=Someone, O=Someone Else"}, "Microsoft Corporation"),
        ({"description": "Microsoft Edge Installer"}, "not a WebView2"),
    ],
)
def test_an_edge_update_identity_still_needs_webview2_provenance_size_and_signature(
    change: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        alpha_release.check_webview2(EDGE_UPDATE_INSTALLER | change)
