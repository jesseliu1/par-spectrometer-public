"""PySide6/Qt in the alpha package (tools/alpha_qt.py; 16_ section 8, 18_ section 6): supplied licence texts, Qt
versions against requirements.lock, no Qt module other than QtCore and no PyQt5. Shared fakes come from
test_alpha_packaging.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.utils import canonicalize_name

from tools import alpha_qt, alpha_release

from .test_alpha_packaging import ROOT, _fake_app, _fake_web, _metadata

pytestmark = pytest.mark.unit


def test_metadata_supplies_the_licence_texts_the_wheels_lack(tmp_path: Path) -> None:
    """16_ 8.2, 18_ 6: PySide6, shiboken6 (LGPL v3) and pyserial ship no licence file in their wheels; the LGPL v3
    goes with the GPL v3 it extends. The texts come from tools/alpha_licences/ and are counted, so no exception is
    needed for them. The runtime record is what a fresh interpreter loads: PySide6 and its Qt 6."""
    app = _fake_app(tmp_path)
    manifest = _metadata(app, _fake_web(tmp_path), {}, None)
    pypi = app / alpha_release.LICENSES_DIR / alpha_release.PYPI_DIR
    gpl = (ROOT / "tools/alpha_licences/GPL-3.0.txt").read_text(encoding="utf-8")
    lgpl = (ROOT / "tools/alpha_licences/LGPL-3.0.txt").read_text(encoding="utf-8")
    assert "Version 3, 29 June 2007" in gpl and "END OF TERMS AND CONDITIONS" in gpl
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in lgpl
    packages = {canonicalize_name(name): (name, info) for name, info in manifest["packages"].items()}
    for name in ("pyside6-essentials", "shiboken6"):
        key, info = packages[name]
        assert (pypi / key / "supplied/LGPL-3.0.txt").read_text(encoding="utf-8") == lgpl
        assert {"supplied/LGPL-3.0.txt", "supplied/GPL-3.0.txt"} <= set(info["supplied"])
    assert "Chris Liechti" in (pypi / "pyserial/supplied/pyserial-BSD-3-Clause.txt").read_text(encoding="utf-8")
    for name in ("pyside6-essentials", "shiboken6", "pyserial", "pymodbus"):
        key, info = packages[name]
        assert info["files"] > 0, name
        assert key not in manifest["licence_exceptions"]
    runtime = manifest["qt"]["runtime"]
    assert runtime["binding"] == "PySide6" and runtime["version"] == manifest["qt"]["locked"]["pyside6-essentials"]
    assert runtime["qt"].startswith("6.")


def test_qt_versions_must_equal_the_lock_file(tmp_path: Path) -> None:
    """The native name of V1.0.3's lock depends on Qt (16_ 2.2): the build environment must be requirements.lock's."""
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        "pyqt5==5.15.11  # via x\n"
        "pyside6-essentials==6.11.2 ; sys_platform == 'win32'\n"
        "pyside6-essentials==6.11.1 ; sys_platform != 'win32'\n"
        "shiboken6==6.11.2  # via pyside6-essentials\n",
        encoding="utf-8",
    )
    expected = "6.11.2" if sys.platform == "win32" else "6.11.1"
    assert alpha_qt.locked_versions(lock) == {"pyside6-essentials": expected, "shiboken6": "6.11.2"}
    packages = {"PySide6_Essentials": {"version": expected}, "shiboken6": {"version": "6.11.2"}}
    runtime = {"binding": "PySide6", "version": expected, "qt": expected}
    record = alpha_qt.qt_record(packages, lock, runtime)
    assert record["distributions"] == {"PySide6-Essentials": expected, "shiboken6": "6.11.2"}
    assert record["runtime"] == runtime
    packages["shiboken6"] = {"version": "6.11.99"}
    with pytest.raises(ValueError, match="requirements.lock"):
        alpha_qt.qt_record(packages, lock, runtime)


def test_the_runtime_record_comes_from_a_fresh_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    """This test session may hold PyQt5 (one binding per process): the probe runs in its own interpreter."""
    found = alpha_qt.runtime_versions()
    assert found["binding"] == "PySide6" and found["qt"].startswith("6.")
    failed = subprocess.CompletedProcess([], 1, "", "ModuleNotFoundError: No module named 'PySide6'")
    monkeypatch.setattr(alpha_qt.subprocess, "run", lambda *_args, **_kwargs: failed)
    with pytest.raises(ValueError, match="PySide6 cannot be loaded"):
        alpha_qt.runtime_versions()


@pytest.mark.parametrize("binding", ["PyQt5", "PyQt6", "PySide2", "shiboken2"])
def test_package_refuses_another_qt_binding(tmp_path: Path, binding: str) -> None:
    """18_ 6, S-6: the alpha contains PySide6 and no PyQt5."""
    app = _fake_app(tmp_path)
    (app / "_internal" / binding).mkdir()
    (app / "_internal" / binding / "QtCore.pyd").write_bytes(b"x")
    with pytest.raises(ValueError, match="contains PySide6 only"):
        alpha_qt.check_qt(app)
    assert alpha_qt.qt_forbidden(("_internal", binding, "QtCore.pyd"))


def test_package_refuses_a_manifest_recorded_on_another_binding(tmp_path: Path) -> None:
    app = _fake_app(tmp_path)
    manifest = json.loads((app / alpha_release.MANIFEST).read_text(encoding="utf-8"))
    manifest["qt"]["runtime"] = {"pyqt5": "5.15.11", "qt": "5.15.2"}
    (app / alpha_release.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="PySide6"):
        alpha_qt.check_qt(app)


@pytest.mark.parametrize(
    "name",
    [
        "_internal/PySide6/Qt6Gui.dll",
        "_internal/PySide6/QtWidgets.pyd",
        "_internal/PySide6/Qt/lib/QtGui.framework/QtGui",
        "_internal/PySide6/plugins/platforms/qwindows.dll",
        "_internal/PySide6/Qt/plugins/platforms/libqcocoa.dylib",
        "_internal/Qt6Network.dll",
        "_internal/PySide6/Qt6Sql.dll",
        "_internal/PySide6/QtSerialPort.pyd",
        "_internal/PySide6/Qt/lib/libQt6XmlPatterns.so.6",
        "_internal/PySide6/translations/qtbase_de.qm",
        "_internal/PySide6/Qt/qml/QtQuick/qmldir",
        "_internal/PySide6/libEGL.dll",
        "_internal/PySide6/opengl32sw.dll",
    ],
)
def test_package_refuses_qt_modules_other_than_qtcore(tmp_path: Path, name: str) -> None:
    """16_ 8.2: QCoreApplication needs no QtGui/QtWidgets and no platform plugin; the spec excludes them."""
    app = _fake_app(tmp_path)
    alpha_release.validate(app)
    (app / name).parent.mkdir(parents=True, exist_ok=True)
    (app / name).write_bytes(b"x")
    with pytest.raises(ValueError, match="Qt module other than QtCore"):
        alpha_release.validate(app)


@pytest.mark.parametrize(
    "parts",
    [
        ("_internal", "PySide6", "QtCore.pyd"),
        ("_internal", "PySide6", "QtCore.abi3.so"),
        ("_internal", "PySide6", "Qt6Core.dll"),
        ("_internal", "PySide6", "Qt", "lib", "QtCore.framework"),
        ("_internal", "PySide6", "pyside6.abi3.dll"),
        ("_internal", "PySide6", "Qt", "lib", "libpyside6.abi3.6.11.dylib"),
        ("_internal", "shiboken6", "Shiboken.pyd"),
        ("_internal", "QtCore"),
        ("_internal", "PySide6", "Qt"),
        ("_internal", "libEGL.dll"),
        ("_internal", "webview", "lib", "WebView2Loader.dll"),
    ],
)
def test_qtcore_and_unrelated_files_are_allowed(parts: tuple[str, ...]) -> None:
    assert not alpha_qt.qt_forbidden(parts)
