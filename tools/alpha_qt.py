"""PySide6/Qt in the 2.0.0-alpha package (16_ section 8, 18_ section 6; split from tools/alpha_release.py).

The tier-1/2 service runs V1.0.3's coordinator on PySide6's QtCore (owner 2026-10-19, S-6: the alpha uses
PySide6 under the LGPL and contains no PyQt5), so the package carries PySide6's QtCore, the Qt 6 core library and
shiboken6:
  * the wheels ship no licence text: LGPL-3.0 and the GPL-3.0 it extends are supplied from tools/alpha_licences/
    (SUPPLIED_LICENCES);
  * the PySide6/shiboken6 versions of the build environment must equal requirements.lock and are recorded in
    build_manifest.json with the binding and Qt versions a fresh interpreter reports, for the frozen self-test (the
    native name of V1.0.3's lock depends on Qt, 16_ 2.2);
  * no Qt module other than QtCore, no Qt plugin and no PyQt5 (or other Qt binding) may be packaged (qt_forbidden);
  * the notices carry the S-6 note: the alpha uses PySide6 (LGPL) and contains no PyQt5.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from packaging.markers import Marker
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
INTERNAL = "_internal"
MANIFEST = "build_manifest.json"
LICENSES_DIR = "third_party_licenses"
PYPI_DIR = "pypi"
BINDING = "PySide6"
"""The only Qt binding the alpha may contain (par_shell/self_test.ALPHA_QT_BINDING checks it at run time)."""
QT_DISTRIBUTIONS = ("PySide6-Essentials", "shiboken6")
SUPPLIED_DIR = ROOT / "tools" / "alpha_licences"
SUPPLIED_LICENCES: dict[str, tuple[str, ...]] = {
    "PySide6-Essentials": ("LGPL-3.0.txt", "GPL-3.0.txt"),
    "shiboken6": ("LGPL-3.0.txt", "GPL-3.0.txt"),
    "pyserial": ("pyserial-BSD-3-Clause.txt",),
}
"""Licence texts copied from tools/alpha_licences/ into third_party_licenses/pypi/<name>/supplied/: the PySide6 and
shiboken6 wheels ship none (their metadata: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; the alpha uses them under
LGPL-3.0, which is GPL-3.0 plus permissions, so both texts go with them, and with the Qt 6 libraries inside the
PySide6 wheel), and pyserial's wheel ships none (BSD-3-Clause per the SPDX line in its sources; the copyright line is
taken from serial/__init__.py). GPL-3.0.txt holds the terms and conditions (sections 0-17) without the "How to Apply"
appendix; the canonical file is https://www.gnu.org/licenses/gpl-3.0.txt."""
QT_LOCK_NAMES = {"PySide6-Essentials": "pyside6-essentials", "shiboken6": "shiboken6"}
"""Distributions whose version must equal requirements.lock (16_ 2.2: the native name of the lock depends on Qt)."""
FOREIGN_BINDINGS = ("PyQt5", "PyQt6", "PySide2", "shiboken2")
"""Folders under _internal that would mean a second Qt binding (18_: the alpha contains no PyQt5)."""
QT_MODULE = re.compile(r"^(lib)?qt[56]?(?P<module>[a-z]+)", re.IGNORECASE)
"""File or folder names under _internal that name a Qt module (Qt6Gui.dll, QtWidgets.pyd, QtGui.framework,
libQt6Network.so, qtbase_de.qm, ...): only the module "core" (QtCore, Qt6Core) may be packaged (16_ 8.2:
QCoreApplication needs no other; PAR_Spectrometer_2.spec excludes them). An allowlist, so a new Qt module is caught."""
QT_ALLOWED_MODULES = ("core",)
QT_ONLY_IN_BINDING = (
    "plugins",
    "platforms",
    "qml",
    "translations",
    "libegl.dll",
    "libglesv2.dll",
    "opengl32sw.dll",
    "d3dcompiler_47.dll",
)
"""Inside PySide6/: Qt's plugin, QML and translation folders and the OpenGL/ANGLE libraries QtGui brings on Windows."""
VERSION_PROBE = (
    "import json, PySide6, shiboken6\n"
    "from PySide6.QtCore import qVersion\n"
    "print(json.dumps({'binding': 'PySide6', 'version': PySide6.__version__, 'qt': qVersion()}))\n"
)
"""Run in a fresh interpreter: this tool's own process may hold another binding (a PyQt5 test session)."""


def qt_forbidden(parts: tuple[str, ...]) -> bool:
    """True for a path (relative to the app folder, under _internal) that is a Qt module other than QtCore, a Qt
    plugin, QML or translation folder, a QtGui companion library, or part of another Qt binding."""
    if len(parts) > 1 and parts[1] in FOREIGN_BINDINGS:
        return True
    name = parts[-1]
    found = QT_MODULE.match(name)
    if found and found.group("module").lower() not in QT_ALLOWED_MODULES:
        return True
    return BINDING in parts and name.lower() in QT_ONLY_IN_BINDING


def copy_supplied_licences(name: str, target: Path) -> list[str]:
    """SUPPLIED_LICENCES for `name` into <target>/supplied/; the relative paths written."""
    written = []
    supplied = {canonicalize_name(key): files for key, files in SUPPLIED_LICENCES.items()}
    for file_name in supplied.get(canonicalize_name(name), ()):
        destination = target / "supplied" / file_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SUPPLIED_DIR / file_name, destination)
        written.append(f"supplied/{file_name}")
    return written


def package_entry(packages: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    """The entry of distribution `name` whatever its spelling in the metadata (PySide6_Essentials for
    PySide6-Essentials)."""
    wanted = canonicalize_name(name)
    return next((info for key, info in packages.items() if canonicalize_name(key) == wanted), None)


def qt_bundled(app_root: Path) -> bool:
    """True if this build contains Qt bindings in _internal (PySide6, the only one the service may use; the others
    count too, so that a wrong build is reported as containing Qt and then refused by `package`)."""
    return any((app_root / INTERNAL / name).exists() for name in (BINDING, *FOREIGN_BINDINGS[:3]))


S6_ALPHA = "alpha 使用 PySide6（LGPL-3.0），不含 PyQt5（S-6，负责人 2026-10-19 批准）。"
"""The S-6 sentence of the notices (18_ section 6)."""


def qt_section(bundled: bool, packages: dict[str, dict[str, Any]]) -> list[str]:
    s6 = (
        "S-6 (13_阶段二方案_路线C.md 3.3;负责人 2026-10-19): the alpha runs on PySide6 under the LGPL v3 and "
        "contains no PyQt5. V1.0.3's own package still contains PyQt5 (GPL v3 or Riverbank commercial licence); "
        "that is not part of this build. How the 2.0 release meets the LGPL's source and relinking terms (source "
        "offer, notices) is settled before any 2.0 build leaves the company."
    )
    if bundled:
        found = {name: package_entry(packages, name) for name in QT_DISTRIBUTIONS}
        versions = ", ".join(f"{name} {info['version']}" for name, info in found.items() if info)
        return [
            f"This build CONTAINS PySide6/Qt 6 ({versions or 'files in _internal'}): the local service runs "
            "V1.0.3's acquisition coordinator for tiers 1 and 2 on PySide6's QtCore (16_ 8.1, 18_). Only QtCore, the "
            "Qt 6 core library, libpyside6 and shiboken6 are packaged; no other Qt module, no Qt plugin and no "
            "PyQt5.",
            S6_ALPHA,
            f"PySide6 and shiboken6 - LGPL v3 ({LICENSES_DIR}/{PYPI_DIR}/<PySide6_Essentials, shiboken6>/supplied/: "
            "LGPL-3.0 and the GPL-3.0 it extends). Qt 6 (QtCore) - LGPL v3, the same texts. The Qt "
            "and PySide6 libraries are separate shared libraries in _internal that can be replaced. Their source "
            "code for these versions is published by The Qt Company (download.qt.io: qt-everywhere-src and "
            "pyside-setup).",
            s6,
        ]
    return [
        "This build does NOT contain PySide6 or Qt files, so its service cannot run tiers 1 and 2 (V1.0.3's "
        "coordinator needs QtCore); `package` refuses such a folder.",
        s6,
    ]


def locked_versions(lock: Path = ROOT / "requirements.lock") -> dict[str, str]:
    """The pins of QT_LOCK_NAMES in requirements.lock that apply to this platform (environment markers)."""
    pins: dict[str, str] = {}
    for raw in lock.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if "==" not in line:
            continue
        requirement, _, marker = line.partition(";")
        name, _, version = requirement.strip().partition("==")
        canonical = canonicalize_name(name.strip())
        if canonical in QT_LOCK_NAMES.values() and (not marker.strip() or Marker(marker).evaluate()):
            pins[canonical] = version.strip()
    return pins


def runtime_versions(python: str = sys.executable) -> dict[str, str]:
    """What a fresh interpreter of the build environment loads: the binding, its version and qVersion() (the QtCore
    library actually loaded, not the Qt the binding was compiled against). The frozen self-test compares its own."""
    done = subprocess.run([python, "-c", VERSION_PROBE], capture_output=True, text=True, timeout=120, check=False)
    if done.returncode != 0:
        raise ValueError(f"PySide6 cannot be loaded in the build environment: {done.stderr.strip()[-500:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])  # type: ignore[no-any-return]


def qt_record(
    packages: dict[str, dict[str, Any]],
    lock: Path = ROOT / "requirements.lock",
    runtime: dict[str, str] | None = None,
) -> dict[str, Any]:
    """PySide6/Qt versions of the build environment (what PyInstaller packaged): distributions, the versions at run
    time and the lock file's pins. Raises ValueError when a distribution differs from requirements.lock."""
    locked = locked_versions(lock)
    installed = {name: (package_entry(packages, name) or {}).get("version") for name in QT_DISTRIBUTIONS}
    mismatched = [
        f"{name} {installed[name]} != requirements.lock {locked.get(pin)}"
        for name, pin in QT_LOCK_NAMES.items()
        if installed[name] != locked.get(pin)
    ]
    if mismatched:
        raise ValueError("PySide6/Qt of the build environment differ from requirements.lock: " + "; ".join(mismatched))
    return {
        "distributions": {name: version for name, version in installed.items() if version},
        "runtime": runtime if runtime is not None else runtime_versions(),
        "locked": locked,
    }


def check_qt(app_root: Path) -> None:
    """Tiers 1 and 2 run V1.0.3's coordinator on PySide6's QtCore (16_ 8.2, 18_): the package must contain PySide6
    and the manifest the Qt versions the self-test compares (written by metadata after the requirements.lock check),
    and must not contain PyQt5 or another binding."""
    try:
        manifest = json.loads((app_root / MANIFEST).read_text(encoding="utf-8"))
        runtime = manifest["qt"]["runtime"] if manifest.get("qt_bundled") else None
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(f"{MANIFEST} records no Qt versions: {error!r}") from error
    foreign = [name for name in FOREIGN_BINDINGS if (app_root / INTERNAL / name).exists()]
    if foreign:
        raise ValueError(f"{', '.join(foreign)} in {INTERNAL}: the alpha contains PySide6 only (18_, S-6)")
    if not runtime or runtime.get("binding") != BINDING or not (app_root / INTERNAL / BINDING).is_dir():
        raise ValueError(f"PySide6 (QtCore) missing from {INTERNAL} or {MANIFEST}: the service could not run tier 1")
