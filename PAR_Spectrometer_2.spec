# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec of the 2.0.0-alpha: PAR_Spectrometer_2.exe, one exe for two processes (13_ section 3.1).
#   PAR_Spectrometer_2.exe                       desktop shell (pywebview window on WebView2)
#   PAR_Spectrometer_2.exe --service ...         local service (FastAPI on 127.0.0.1 + a Qt core loop running V1.0.3's
#                                                coordinator for tiers 1/2, par_app.service_main), started by the shell
#   PAR_Spectrometer_2.exe --alpha-self-test R   packaging self-test
# Built by build_alpha.ps1 (Windows); V1.0.3's PAR_Spectrometer.spec and build_release.ps1 are not touched (15_ section 4).
#
# Inputs:
#   web/dist/                 `npm ci && npm run build` in web/ (build_alpha.ps1 runs it); bundled as _internal/web
#                             with the fonts Vite copies there: Noto Sans SC, JetBrains Mono and their SIL OFL 1.1 texts
#   $PAR_ALPHA_BUILD_INFO     build_info.json written by build_alpha.ps1 (commit, build time); bundled at _internal/
#   logo.png                  the brand image of the calculation page's Excel export (resource_path("logo.png"))
#
# Tiers 1 and 2 (16_ 8.1, 17_): the service runs V1.0.3's coordinator on PySide6 (18_; owner 2026-10-19,
# S-6), so the package contains PySide6's QtCore (with the Qt 6 core library, libpyside6 and shiboken6), pymodbus,
# pyserial and par_app.protocol / coordinator / maintenance / device_hub / database / app_config / acquisition_host.
# QCoreApplication loads no platform plugin. NOT bundled: PyQt5 (and every other Qt binding), every other Qt module
# (QtGui, QtWidgets, QtNetwork, ...), Qt's plugins, QML and translations, the V1.0.x desktop UI, matplotlib, Tk.
# Without QtWidgets and QtGui pywebview cannot fall back to a Qt window either: WebView2 or the browser, nothing else.
# PySide6 and Qt 6 are LGPL-3.0; tools/alpha_release.py adds the licence texts and refuses a package with PyQt5.
import importlib.util
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT))
from tools.alpha_runtime import (  # noqa: E402
    BuildRoots,
    check_binary_sources,
    check_python_dlls,
    check_vc_runtime_sources,
    select_binaries,
    write_sources,
)
APP_NAME = 'PAR_Spectrometer_2'
WEB_DIST = ROOT / 'web' / 'dist'
WEB_REQUIRED = ('index.html', 'fonts/NotoSansSC.ttf', 'fonts/OFL.txt', 'fonts/JetBrainsMono.ttf',
                'fonts/JetBrainsMono-OFL.txt')

missing = [name for name in WEB_REQUIRED if not (WEB_DIST / name).is_file()]
if missing:
    raise SystemExit(f'web/dist is incomplete ({", ".join(missing)}): run `npm ci && npm run build` in web/ first')

datas = [(str(WEB_DIST), 'web'), (str(ROOT / 'logo.png'), '.')]
build_info = os.environ.get('PAR_ALPHA_BUILD_INFO')
if build_info:
    if not Path(build_info).is_file():
        raise SystemExit(f'PAR_ALPHA_BUILD_INFO points to a missing file: {build_info}')
    datas.append((build_info, '.'))
else:
    print('WARNING: PAR_ALPHA_BUILD_INFO not set; the health answer will name no build commit')

# uvicorn resolves its loop, protocol and lifespan implementations by name at run time.
hiddenimports = collect_submodules('uvicorn')
if sys.platform == 'win32':
    hiddenimports += ['webview.platforms.winforms', 'webview.platforms.edgechromium', 'clr']
elif sys.platform == 'darwin':
    hiddenimports += ['webview.platforms.cocoa']

# The Qt modules the service does not use (only PySide6.QtCore is imported, 16_ 1.6, 18_); tools/alpha_release.py
# rejects a package that still contains one of them, a Qt plugin folder or another binding (tools/alpha_qt.py).
QT_UNUSED = [
    'PySide6.' + name
    for name in (
        'QtGui', 'QtWidgets', 'QtNetwork', 'QtSql', 'QtSvg', 'QtSvgWidgets', 'QtXml', 'QtPrintSupport', 'QtOpenGL',
        'QtOpenGLWidgets', 'QtMultimedia', 'QtMultimediaWidgets', 'QtQml', 'QtQuick', 'QtQuickWidgets',
        'QtQuickControls2', 'QtQuick3D', 'QtDBus', 'QtTest', 'QtBluetooth', 'QtNfc', 'QtSerialPort', 'QtSerialBus',
        'QtPositioning', 'QtLocation', 'QtSensors', 'QtWebChannel', 'QtWebSockets', 'QtWebEngineCore',
        'QtWebEngineWidgets', 'QtWebEngineQuick', 'QtHelp', 'QtDesigner', 'QtRemoteObjects', 'QtTextToSpeech',
        'QtConcurrent', 'QtStateMachine', 'QtUiTools', 'QtAxContainer', 'QtPdf', 'QtPdfWidgets', 'QtCharts',
        'QtDataVisualization', 'QtGraphs', 'QtNetworkAuth', 'QtHttpServer', 'QtSpatialAudio', 'QtScxml',
        'QtWebView', 'Qt3DCore', 'Qt3DRender', 'Qt3DInput', 'Qt3DLogic', 'Qt3DAnimation', 'Qt3DExtras', 'scripts',
    )
]
excludes = [
    *QT_UNUSED, 'PyQt5', 'PyQt6', 'PySide2', 'shiboken2', 'sip', 'qtpy',
    'matplotlib', 'tkinter', '_tkinter',
    'par_app.ui', 'par_app.ui_unconfigured', 'par_app.maintenance_dialog', 'par_app.device_maintenance_dialog',
    'par_app.release_self_test', 'par_app.theme', 'par_app.slot_errors',
    # Development tools that optional imports would otherwise drag in from a developer's environment
    # (pydantic's mypy plugin, uvicorn's rich tracebacks, pytest); requirements-build.lock does not install them.
    'mypy', 'pydantic.mypy', 'pydantic.v1.mypy', '_pytest', 'pytest', 'rich', 'pygments', 'IPython',
]

a = Analysis(
    [str(ROOT / 'main_v2.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
# The Windows C/C++ runtime (#66: the frozen alpha.3 failed with "DLL load failed while importing QtCore: 找不到指定的程序"
# while source runs worked; root cause still being confirmed on Windows, the bundled ICU is the current suspect).
# alpha.3 carried DLLs from a polluted build PATH (UCRT and ICU from build agents' tool folders) and two VC++ runtime
# versions. Nothing Windows provides is bundled: no Universal CRT (ucrtbase.dll, api-ms-win-*.dll) and no ICU
# (icuuc/icuin/icudt*/icu.dll); Windows 10 1809+, which the alpha requires, ships both. One VC++ runtime: every
# vcruntime140*/msvcp140*/concrt140 DLL, top level included, is PySide6's own copy. tools/alpha_runtime.py has the
# rules and what its checks do and do not prove; tools/alpha_release.py refuses a package that breaks them.
PYSIDE6_DIR = Path(importlib.util.find_spec('PySide6').origin).parent
a.binaries = select_binaries(a.binaries, PYSIDE6_DIR)
# Where every collected binary comes from (#66: the alpha.3 ucrtbase.dll came from a build agent's tool folder that
# was on PATH). Recorded for build_alpha.ps1's pre-package check (PAR_ALPHA_BINARY_SOURCES) and refused here already
# if a .dll/.pyd/.exe lies outside the build venv, its base Python and Windows, if python3.dll / python3XX.dll are not
# the build Python's own, or if a VC++ runtime DLL is not PySide6's copy.
BUILD_ROOTS = BuildRoots.of_this_python()
binary_sources = os.environ.get('PAR_ALPHA_BINARY_SOURCES')
if binary_sources:
    write_sources(Path(binary_sources), [*a.binaries, *a.datas], BUILD_ROOTS, PYSIDE6_DIR)
if sys.platform == 'win32':
    try:
        check_binary_sources([*a.binaries, *a.datas], BUILD_ROOTS)
        check_python_dlls(a.binaries, BUILD_ROOTS)
        check_vc_runtime_sources([*a.binaries, *a.datas], str(PYSIDE6_DIR))
    except ValueError as error:
        raise SystemExit(f'Refusing the build: {error}') from error
# Qt's translation catalogues (PyInstaller's QtCore hook adds them; several MB): the service shows no Qt text.
a.datas = [entry for entry in a.datas if '/translations/' not in '/' + entry[0].replace('\\', '/')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='_internal',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
