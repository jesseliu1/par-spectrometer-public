"""Release metadata, third-party notices and the delivery archive of the 2.0.0-alpha (build_alpha.ps1 calls it).

  python tools/alpha_release.py names
      JSON with the version and the names build_alpha.ps1 uses (from par_app/alpha_info.py, the one place to bump).
  python tools/alpha_release.py metadata <app folder> --toc <PYZ-00.toc> --web web --build-info <build_info.json>
                                         [--webview2 <webview2.json>]
      Writes build_manifest.json, THIRD_PARTY_NOTICES.txt and third_party_licenses/ into the app folder: the Python
      runtime licence, every Python distribution the PyInstaller module table names plus its declared runtime
      requirements, the npm production dependencies from web/package-lock.json, the build-tool helpers Vite emits
      into the bundle, the two bundled fonts, the Microsoft components and PySide6/Qt with the S-6 note. Licence
      texts a wheel does not ship are supplied from tools/alpha_licences/ (SUPPLIED_LICENCES: LGPL-3.0 and GPL-3.0
      for PySide6, shiboken6 and Qt; pyserial's BSD-3-Clause). With Qt in the package, the PySide6/Qt versions of the
      build environment are recorded (the self-test compares the frozen exe's) and must equal requirements.lock
      (the native name of V1.0.3's lock depends on Qt, 16_ 2.2). Fails, naming each one, if a component has no
      licence text and is not one of LICENCE_EXCEPTIONS, if the WebView2 installer record fails check_webview2
      (review of PR #50, majors 3 and 4) or if the Qt versions differ from the lock file.
  python tools/alpha_release.py check-webview2 <webview2.json>
      The installer identity check alone (build_alpha.ps1 runs it right after the signature check).
  python tools/alpha_release.py package <app folder> <release folder> [--no-webview2]
      Checks the folder (required files present, every resource the page loads present and non-empty, no licence gap
      outside LICENCE_EXCEPTIONS, PySide6 present, no PyQt5, no Qt module other than QtCore and no Qt plugin (16_ 8.2,
      18_), no Universal CRT, one VC++ runtime (#66), no runtime state or user data, no V1.0.x program), writes
      PAR_Spectrometer_2.0.0-alpha.N.zip and its .sha256 next to it.

V1.0.3's tools/release_metadata.py and package_release.py stay unchanged (15_ section 4).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import platform
import shutil
import sys
import textwrap
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from par_app.alpha_info import (  # noqa: E402  (after sys.path)
    ALPHA_CHANNEL,
    ALPHA_VERSION,
    APP_NAME,
    EXE_NAME,
    archive_name,
    window_title,
)
from par_shell.web_assets import WebAssetError, check_page  # noqa: E402
from par_shell.webview2 import WEBVIEW2_MIN_BYTES  # noqa: E402
from tools.alpha_qt import (  # noqa: E402
    check_qt,
    copy_supplied_licences,
    qt_bundled,
    qt_forbidden,
    qt_record,
    qt_section,
)
from tools.alpha_runtime import check_c_runtime  # noqa: E402

LICENSES_DIR = "third_party_licenses"
CPYTHON_DIR = "CPython"
PYPI_DIR = "pypi"
NPM_DIR = "npm"
"""Distinct names even on case-insensitive file systems (Windows, macOS)."""
WRAP = 112
NOTICES = "THIRD_PARTY_NOTICES.txt"
MANIFEST = "build_manifest.json"
INTERNAL = "_internal"
WEB_FONTS = "_internal/web/fonts"
REDIST_INSTALLER = "redist/MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
README_SOURCE = ROOT / "docs" / "release" / "2.0.0-alpha_包内说明.txt"
README = "软件说明.txt"
LICENSE_TOKENS = ("license", "licence", "copying", "notice")
PYTHON_SEEDS = (
    "fastapi",
    "uvicorn",
    "pywebview",
    "numpy",
    "pyinstaller",
    "PySide6-Essentials",
    "pymodbus",
    "pyserial",
)
"""Always listed, even without a module table: the service, the shell, numpy, PyInstaller's bootloader and what the
tier-1/2 service runs V1.0.3's coordinator with (PySide6's QtCore, pymodbus, pyserial; 16_ 8.1, 18_)."""
BUNDLER_HELPERS = ("vite", "rolldown", "@vitejs/plugin-vue")
"""Build tools (devDependencies) whose runtime helpers end up in assets/index-*.js: Vite's module-preload polyfill,
Rolldown's runtime helpers and @vitejs/plugin-vue's component export helper (review N-1)."""
VC_RUNTIME = ("vcruntime*.dll", "msvcp*.dll")
V1_PROGRAM = "PAR_Spectrometer.exe"
FORBIDDEN_TOP_LEVEL = ("config", "data", "logs", "exports")
FORBIDDEN_NAMES = ("app_config.json", "app_config_v2.json", "service.json", "shell.lock")
FORBIDDEN_SUFFIXES = (".sqlite3", ".sqlite", ".db", ".db3", ".wal", ".shm", ".jsonl", ".partial")
FONTS = (
    ("Noto Sans SC", "NotoSansSC.ttf", "OFL.txt"),
    ("JetBrains Mono 2.304", "JetBrainsMono.ttf", "JetBrainsMono-OFL.txt"),
)
WEBVIEW2_SDK_FILES = (
    "Microsoft.Web.WebView2.Core.dll",
    "Microsoft.Web.WebView2.WinForms.dll",
    "WebView2Loader.dll",
)
WEBVIEW2_SDK = "Microsoft.Web.WebView2 SDK"
WEB_ROOT = "_internal/web"
OFFICIAL_WEBVIEW2_X64_URL = "https://go.microsoft.com/fwlink/?linkid=2124701"
"""Microsoft's permanent link to the Evergreen Standalone Installer for x64 (same string as build_alpha.ps1)."""
WEBVIEW2_IDENTITY = "webview2"
# Since 2026-10 the standalone installer's VERSIONINFO reads as the Edge Update setup it wraps (issue #66); that fits
# any Edge Update setup, so it is accepted only from the official x64 link or under Microsoft's exact x64 file name.
EDGE_UPDATE_IDENTITY = ("microsoft edge update", "microsoft edge update setup")
MICROSOFT_SIGNER = "O=Microsoft Corporation"
X64_NAME = "x64"
OTHER_ARCHITECTURES = ("x86", "arm64")
PENDING = "pending owner's acceptance"
LICENCE_EXCEPTIONS: dict[str, str] = {
    "proxy_tools": (
        "MIT according to its PyPI metadata (pywebview requires it); the wheel ships no licence file and the "
        f"copyright line is not known here. Add the upstream LICENSE before 2.0 or accept the gap ({PENDING})."
    ),
    WEBVIEW2_SDK: (
        "Microsoft.Web.WebView2.Core.dll, .WinForms.dll and WebView2Loader.dll come inside pywebview; their NuGet "
        "package's licence text and exact version are not bundled with pywebview. Add them before 2.0 or accept "
        f"the gap ({PENDING})."
    ),
}
"""The only components allowed to ship without a licence text, each with its reason, for owner to accept (
review of PR #50, major 4). Any other gap stops the build; an entry here is listed in the notices and the manifest."""


class LicenceIncomplete(ValueError):
    """Components without a licence text that are not in LICENCE_EXCEPTIONS."""


def check_web_folder(web_root: Path) -> list[str]:
    """Every resource index.html loads (scripts, stylesheets, fonts, chunks) exists and is non-empty."""

    def read(path: str) -> bytes:
        target = web_root / path.lstrip("/")
        if not target.is_file():
            raise WebAssetError(f"index.html loads {path}, which is not in the package")
        return target.read_bytes()

    return check_page((web_root / "index.html").read_text(encoding="utf-8"), read)


def check_webview2(info: dict[str, Any]) -> None:
    """build_alpha.ps1's installer record describes Microsoft's x64 Evergreen Standalone Installer: not Edge, the
    bootstrapper, x86 or ARM64 (PR #50 review major 3). Authenticode is checked in build_alpha.ps1."""
    problems = []
    if MICROSOFT_SIGNER not in str(info.get("signer", "")):
        problems.append(f"signer {info.get('signer')!r} is not {MICROSOFT_SIGNER}")
    product, description = str(info.get("product") or "").strip(), str(info.get("description") or "").strip()
    identity = f"{product} | {description}"
    named = str(info.get("original_name", "")).lower() == "microsoftedgewebview2runtimeinstallerx64.exe"
    edge_update = (product.lower(), description.lower()) == EDGE_UPDATE_IDENTITY
    if WEBVIEW2_IDENTITY not in identity.lower() and not (
        edge_update and (named or info.get("source") == OFFICIAL_WEBVIEW2_X64_URL)
    ):
        problems.append(f"product/description {identity!r}: not a WebView2 Runtime installer")
    if int(info.get("size") or 0) < WEBVIEW2_MIN_BYTES:
        problems.append(f"{info.get('size')} bytes, below {WEBVIEW2_MIN_BYTES}: the online bootstrapper")
    if info.get("source") != OFFICIAL_WEBVIEW2_X64_URL:
        name = str(info.get("original_name", "")).lower()
        if X64_NAME not in name or any(other in name for other in OTHER_ARCHITECTURES):
            problems.append(
                f"placed by hand as {info.get('original_name')!r}: use Microsoft's x64 file "
                "(MicrosoftEdgeWebView2RuntimeInstallerX64.exe) or the official x64 download"
            )
    if not info.get("version"):
        problems.append("no product version in the file")
    if problems:
        raise ValueError("WebView2 installer rejected: " + "; ".join(problems))


def required_files(exe_name: str = EXE_NAME, webview2: bool = True) -> list[str]:
    files = [exe_name, README, MANIFEST, NOTICES, f"{LICENSES_DIR}/{CPYTHON_DIR}/LICENSE.txt"]
    files.append("_internal/web/index.html")
    files += [f"{WEB_FONTS}/{name}" for _title, font, licence in FONTS for name in (font, licence)]
    return files + ([REDIST_INSTALLER] if webview2 else [])


# ---------------------------------------------------------------- Python


def python_license() -> Path:
    """CPython's LICENSE.txt (python.org Windows installs keep it in the prefix, POSIX builds under lib/)."""
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for candidate in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "lib" / version / "LICENSE.txt"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"CPython LICENSE.txt not found under {sys.base_prefix}; use a python.org install")


def toc_distributions(toc: Path | None) -> list[str]:
    """Distribution names of the site-packages modules in PyInstaller's PYZ-00.toc."""
    if toc is None:
        return []
    modules = ast.literal_eval(toc.read_text(encoding="utf-8"))[1]
    mapping = importlib.metadata.packages_distributions()
    names: list[str] = []
    for name, source, _kind in modules:
        if "site-packages" in str(source).lower():
            names.extend(mapping.get(name.split(".")[0], []))
    return names


def _license_of(distribution: importlib.metadata.Distribution) -> str:
    meta = distribution.metadata
    expression = meta.get("License-Expression")
    if expression:
        return str(expression)
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    text = (meta.get("License") or "").strip().splitlines()
    return "; ".join(classifiers) or (text[0][:80] if text else "see licence files")


def _copy_python_licences(distribution: importlib.metadata.Distribution, target: Path) -> int:
    copied = 0
    for item in distribution.files or []:
        if not any(token in item.name.lower() for token in LICENSE_TOKENS):
            continue
        source = Path(str(distribution.locate_file(item)))
        if source.is_file() and source.suffix not in (".py", ".pyc", ".so", ".dll", ".pyd"):
            relative = Path(*[part for part in item.parts if part not in ("..", ".")])
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied += 1
    return copied


def python_packages(seeds: Iterable[str], licences: Path) -> dict[str, dict[str, Any]]:
    """Each distribution reachable from `seeds` through runtime requirements: version, licence, files copied."""
    pending = list(seeds)
    packages: dict[str, dict[str, Any]] = {}
    while pending:
        try:
            distribution = importlib.metadata.distribution(pending.pop())
        except importlib.metadata.PackageNotFoundError:
            continue  # a requirement for another platform or an extra that is not installed
        name = distribution.metadata["Name"]
        if name in packages:
            continue
        copied = _copy_python_licences(distribution, licences / name)
        supplied = copy_supplied_licences(name, licences / name)
        packages[name] = {"version": distribution.version, "license": _license_of(distribution), "files": copied}
        if supplied:
            packages[name]["files"] += len(supplied)
            packages[name]["supplied"] = supplied
        for text in distribution.requires or []:
            requirement = Requirement(text)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    return dict(sorted(packages.items(), key=lambda item: item[0].lower()))


# ---------------------------------------------------------------- npm


def npm_packages(web: Path, licences: Path) -> dict[str, dict[str, Any]]:
    """Production dependencies in web/package-lock.json (dev and devOptional excluded) plus BUNDLER_HELPERS."""
    lock = json.loads((web / "package-lock.json").read_text(encoding="utf-8"))
    packages: dict[str, dict[str, Any]] = {}
    for key, entry in lock["packages"].items():
        if not key:
            continue
        name = key.rsplit("node_modules/", 1)[-1]
        helper = name in BUNDLER_HELPERS
        if (entry.get("dev") or entry.get("devOptional")) and not helper:
            continue
        label = f"{name}@{entry['version']}"
        copied = _copy_npm_licences(web / key, licences / label.replace("/", "__"))
        packages[label] = {
            "license": entry.get("license", "UNKNOWN"),
            "files": copied,
            "role": "build-tool helpers emitted into the bundle" if helper else "production dependency",
        }
    return dict(sorted(packages.items()))


def _copy_npm_licences(package: Path, target: Path) -> int:
    if not package.is_dir():
        raise FileNotFoundError(f"{package} is missing: run `npm ci` in web/ before collecting licences")
    copied = 0
    for entry in sorted(package.iterdir()):
        if not any(entry.name.lower().startswith(token) for token in LICENSE_TOKENS):
            continue
        if entry.is_dir():
            shutil.copytree(entry, target / entry.name, dirs_exist_ok=True)
            copied += sum(1 for item in entry.rglob("*") if item.is_file())
        else:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target / entry.name)
            copied += 1
    return copied


# ---------------------------------------------------------------- notices


def webview2_section(app_root: Path, installer: dict[str, Any] | None) -> list[str]:
    lines = []
    sdk = sorted(
        str(path.relative_to(app_root)).replace("\\", "/")
        for name in WEBVIEW2_SDK_FILES
        for path in (app_root / INTERNAL).rglob(name)
    )
    if sdk:
        lines.append(
            "Microsoft Edge WebView2 SDK binaries shipped inside pywebview: "
            + ", ".join(sdk)
            + ". Copyright Microsoft Corporation; licence terms of the Microsoft.Web.WebView2 NuGet package "
            f"(https://www.nuget.org/packages/Microsoft.Web.WebView2). Licence text not included: see section 7 "
            f"({WEBVIEW2_SDK})."
        )
    if installer:
        lines.append(
            f"{REDIST_INSTALLER}: Microsoft Edge WebView2 Runtime, Evergreen Standalone Installer (x64), unmodified "
            f"Microsoft software; installing it means accepting Microsoft's licence terms shown by the installer. "
            f"Source {installer.get('source')}, version {installer.get('version')}, SHA-256 {installer.get('sha256')}, "
            f"signed by {installer.get('signer')}."
        )
    else:
        lines.append("No WebView2 Runtime installer is shipped in this build.")
    lines.append(".NET Framework 4.6.2+ (used by pythonnet) is part of Windows and is not shipped.")
    runtime = sorted(path.name for pattern in VC_RUNTIME for path in (app_root / INTERNAL).glob(pattern))
    if runtime:
        lines.append(
            "Microsoft Visual C++ runtime shipped with CPython (" + ", ".join(runtime) + "): redistributed under the "
            "Visual C++ redistribution terms that CPython's licence carries "
            f"({LICENSES_DIR}/{CPYTHON_DIR}/LICENSE.txt)."
        )
    return lines


def _wrapped(text: str) -> list[str]:
    return textwrap.wrap(text, WRAP, initial_indent="   ", subsequent_indent="     ")


def _files_note(info: dict[str, Any]) -> str:
    return "" if info["files"] else " [no licence text: see section 7]"


def licence_gaps(packages: dict[str, dict[str, Any]], npm: dict[str, dict[str, Any]], sdk: bool) -> list[str]:
    """Components shipped without a licence text: Python distributions and npm packages with no licence file
    copied, and the WebView2 SDK binaries pywebview carries (their licence text is not in pywebview)."""
    gaps = [name for name, info in packages.items() if not info["files"]]
    gaps += [label for label, info in npm.items() if not info["files"]]
    return gaps + ([WEBVIEW2_SDK] if sdk else [])


def _npm_name(label: str) -> str:
    return label.rsplit("@", 1)[0] if label.count("@") > (1 if label.startswith("@") else 0) else label


def _unaccepted(gaps: Iterable[str], exceptions: dict[str, str]) -> list[str]:
    return [gap for gap in gaps if gap not in exceptions and _npm_name(gap) not in exceptions]


def _webview2_sdk_shipped(app_root: Path) -> bool:
    return any(any((app_root / INTERNAL).rglob(name)) for name in WEBVIEW2_SDK_FILES)


def notices_text(manifest: dict[str, Any], app_root: Path) -> str:
    python = manifest["packages"]
    npm = manifest["npm_packages"]
    out = [
        window_title(manifest["version"]),
        f"{APP_NAME} {manifest['version']} (channel {manifest['channel']}) - THIRD-PARTY NOTICES",
        "INTERNAL TEST BUILD - NOT FOR RELEASE (15_阶段二版本管理.md; S-6 in section 6).",
        "",
        *textwrap.wrap(
            "Third-party components keep their own licences; the application's terms do not override them. Full "
            f"licence texts are in {LICENSES_DIR}/ ({CPYTHON_DIR}/, {PYPI_DIR}/<distribution>/, {NPM_DIR}/<package>/); "
            f"versions are also in {MANIFEST}.",
            WRAP + 3,
        ),
        "",
        "1. Python runtime",
        *_wrapped(
            f"CPython {manifest['python']} - PSF License Version 2 ({LICENSES_DIR}/{CPYTHON_DIR}/LICENSE.txt; that "
            "file also carries the notices of libraries built into CPython, such as OpenSSL, SQLite, zlib, expat)."
        ),
        "",
        f"2. Python packages ({len(python)})",
        *_wrapped(
            "Every distribution in the PyInstaller module table and its declared runtime requirements (a superset: "
            "PyInstaller's own build-time requirements are listed too). PyInstaller's bootloader inside the exe is "
            "GPL-2.0 with the bootloader exception, which allows distributing the frozen program under any terms."
        ),
    ]
    out += [f"   {name} {info['version']} - {info['license']}{_files_note(info)}" for name, info in python.items()]
    out += [
        "",
        f"3. Web front end, bundled in _internal/web ({len(npm)})",
        *_wrapped(
            "Production dependencies of web/package-lock.json (a superset: Vue's compiler packages are build-time "
            "only) and the build tools whose runtime helpers Vite emits into assets/index-*.js."
        ),
    ]
    out += [f"   {label} - {info['license']} ({info['role']}){_files_note(info)}" for label, info in npm.items()]
    out += ["", "4. Fonts (served from _internal/web/fonts, never online)"]
    out += [f"   {title} ({font}) - SIL Open Font License 1.1, see {WEB_FONTS}/{text}" for title, font, text in FONTS]
    out += ["", "5. Microsoft components"]
    out += [line for item in webview2_section(app_root, manifest.get("webview2_installer")) for line in _wrapped(item)]
    out += ["", "6. Qt / PySide6 (S-6)"]
    out += [line for item in qt_section(manifest["qt_bundled"], python) for line in _wrapped(item)]
    exceptions = manifest["licence_exceptions"]
    out += ["", f"7. Licence texts not included ({len(exceptions)}; listed exceptions, {PENDING})"]
    out += [line for name, reason in exceptions.items() for line in _wrapped(f"{name}: {reason}")] or ["   none"]
    return "\n".join(out) + "\n"


def write_metadata(
    app_root: Path,
    toc: Path | None,
    web: Path,
    build_info: dict[str, Any],
    installer: dict[str, Any] | None,
    exceptions: dict[str, str] = LICENCE_EXCEPTIONS,
) -> dict[str, Any]:
    """Raises (writing neither the manifest nor the notices) on a rejected installer or an unexcepted licence gap."""
    if installer is not None:
        check_webview2(installer)
    licences = app_root / LICENSES_DIR
    if licences.exists():
        shutil.rmtree(licences)  # a rerun on the same folder starts from a clean list
    (licences / CPYTHON_DIR).mkdir(parents=True)
    shutil.copy2(python_license(), licences / CPYTHON_DIR / "LICENSE.txt")
    packages = python_packages([*PYTHON_SEEDS, *toc_distributions(toc)], licences / PYPI_DIR)
    npm = npm_packages(web, licences / NPM_DIR)
    gaps = licence_gaps(packages, npm, _webview2_sdk_shipped(app_root))
    missing = _unaccepted(gaps, exceptions)
    if missing:
        raise LicenceIncomplete(
            f"{len(missing)} component(s) without a licence text: {', '.join(missing)}. Add the text, or add an "
            "entry with its reason to LICENCE_EXCEPTIONS in tools/alpha_release.py for owner to accept."
        )
    bundled = qt_bundled(app_root)
    shutil.copy2(README_SOURCE, app_root / README)
    manifest: dict[str, Any] = {
        "version": ALPHA_VERSION,
        "channel": ALPHA_CHANNEL,
        "not_for_release": True,
        "app_name": APP_NAME,
        "exe": EXE_NAME,
        "window_title": window_title(),
        "commit": build_info.get("commit"),
        "dirty": build_info.get("dirty"),
        "built_at": build_info.get("built_at") or datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "platform": sys.platform,
        "qt_bundled": bundled,
        "qt": qt_record(packages) if bundled else None,
        "webview2_installer": installer,
        "packages": packages,
        "npm_packages": npm,
        "licence_exceptions": {gap: exceptions.get(gap) or exceptions[_npm_name(gap)] for gap in gaps},
    }
    (app_root / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (app_root / NOTICES).write_text(notices_text(manifest, app_root), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------- package


def validate(app_root: Path, exe_name: str = EXE_NAME, webview2: bool = True) -> None:
    """Raise ValueError if a required file is missing or the folder holds runtime state, user data or V1.0.x."""
    for name in required_files(exe_name, webview2):
        if not (app_root / name).is_file():
            raise ValueError(f"required file missing: {name}")
    try:
        check_web_folder(app_root / WEB_ROOT)
    except WebAssetError as error:
        raise ValueError(f"web front end incomplete: {error}") from error
    _check_licences(app_root)
    check_qt(app_root)
    if exe_name.lower().endswith(".exe"):  # the Windows window back end: pywebview's WebView2 SDK binaries
        for name in WEBVIEW2_SDK_FILES:
            if not any((app_root / INTERNAL).rglob(name)):
                raise ValueError(f"required file missing: {name} (pywebview's WebView2 SDK) under {INTERNAL}")
    check_c_runtime(app_root)
    for source in app_root.rglob("*"):
        relative = source.relative_to(app_root)
        lower = source.name.lower()
        if relative.parts[0] == INTERNAL and qt_forbidden(relative.parts):
            raise ValueError(f"Qt module other than QtCore or a Qt plugin folder must not be shipped: {relative}")
        if relative.parts[0].lower() in FORBIDDEN_TOP_LEVEL:
            raise ValueError(f"runtime state must not be shipped: {relative}")
        if lower == V1_PROGRAM.lower():
            raise ValueError(f"V1.0.x program must not be shipped in the alpha: {relative}")
        if source.is_file() and (
            lower in FORBIDDEN_NAMES or source.suffix.lower() in FORBIDDEN_SUFFIXES or lower.endswith(("-wal", "-shm"))
        ):
            raise ValueError(f"possible user data must not be shipped: {relative}")


def _check_licences(app_root: Path) -> None:
    """The manifest metadata wrote: every component without a licence text is an exception of LICENCE_EXCEPTIONS
    (an exception made up in the manifest itself does not count)."""
    try:
        manifest = json.loads((app_root / MANIFEST).read_text(encoding="utf-8"))
        gaps = licence_gaps(manifest["packages"], manifest["npm_packages"], sdk=False)
        recorded = dict(manifest["licence_exceptions"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(f"{MANIFEST} unreadable or from an older tool: {error!r}") from error
    accepted = {name: reason for name, reason in recorded.items() if name in LICENCE_EXCEPTIONS}
    missing = _unaccepted(gaps, accepted)
    if missing:
        raise ValueError(f"components without a licence text and not in LICENCE_EXCEPTIONS: {', '.join(missing)}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package(app_root: Path, release_dir: Path, exe_name: str = EXE_NAME, webview2: bool = True) -> Path:
    """Validate, then write <release>/PAR_Spectrometer_2.0.0-alpha.N.zip (folder PAR_Spectrometer_2/ inside) and
    its .sha256 ("<hash>  <file name>", like V1.0.3). An existing archive is replaced."""
    validate(app_root, exe_name, webview2)
    archive = release_dir / archive_name()
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as stream:
        for source in sorted(app_root.rglob("*")):
            if source.is_file():
                stream.write(source, Path(APP_NAME) / source.relative_to(app_root))
    with zipfile.ZipFile(archive) as stream:
        broken = stream.testzip()
    if broken is not None:
        raise ValueError(f"archive check failed at {broken}")
    archive.with_name(archive.name + ".sha256").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="ascii")
    return archive


# ---------------------------------------------------------------- command line


def _json_file(path: Path | None) -> dict[str, Any] | None:
    return None if path is None else dict(json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("names")
    meta = commands.add_parser("metadata")
    meta.add_argument("app_root", type=Path)
    meta.add_argument("--toc", type=Path, default=None)
    meta.add_argument("--web", type=Path, default=ROOT / "web")
    meta.add_argument("--build-info", type=Path, required=True)
    meta.add_argument("--webview2", type=Path, default=None)
    check = commands.add_parser("check-webview2")
    check.add_argument("record", type=Path)
    pack = commands.add_parser("package")
    pack.add_argument("app_root", type=Path)
    pack.add_argument("release_dir", type=Path)
    pack.add_argument("--exe", default=EXE_NAME, help="program file name (default %(default)s; tests use others)")
    pack.add_argument("--no-webview2", action="store_true", help="allow a folder without the offline installer")
    args = parser.parse_args(argv)
    if args.command == "names":
        names = {"version": ALPHA_VERSION, "app_name": APP_NAME, "exe": EXE_NAME, "archive": archive_name()}
        print(json.dumps(names))
    elif args.command == "check-webview2":
        check_webview2(_json_file(args.record) or {})
        print("PASS: WebView2 installer is the x64 Evergreen Standalone Installer")
    elif args.command == "metadata":
        build_info = _json_file(args.build_info) or {}
        manifest = write_metadata(args.app_root, args.toc, args.web, build_info, _json_file(args.webview2))
        qt = "contains" if manifest["qt_bundled"] else "no"
        print(
            f"PASS: {MANIFEST} and {NOTICES} written ({len(manifest['packages'])} Python, "
            f"{len(manifest['npm_packages'])} npm packages; {qt} PySide6/Qt)"
        )
        for name in manifest["licence_exceptions"]:
            print(f"LICENCE EXCEPTION ({PENDING}): {name}")
    else:
        archive = package(args.app_root, args.release_dir, args.exe, not args.no_webview2)
        print(f"PASS: {archive} and {archive.name}.sha256 written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
