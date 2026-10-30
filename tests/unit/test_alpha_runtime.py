"""The Windows C/C++ runtime in the alpha package (#66: the frozen alpha.3 exe failed with "DLL load failed while
importing QtCore: 找不到指定的程序" while source runs worked).

The alpha.3 package carried its own ucrtbase.dll (older than the system's) and two VC++ runtime versions: Python's
VCRUNTIME140*.dll 14.38 at the top level, PySide6's and shiboken6's 14.44 in their folders. tools/alpha_runtime.py
(used by PAR_Spectrometer_2.spec) drops the Universal CRT and takes every VC++ runtime DLL from PySide6's own folder;
tools/alpha_release.py validate() refuses a package that still has either problem. Everything runs on fake TOC
entries and fake package trees, so on every platform; the real effect is only verifiable on Windows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import alpha_release, alpha_runtime

from .test_alpha_packaging import _fake_app

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("name", "crt"),
    [
        ("ucrtbase.dll", True),
        ("UCRTBASE.DLL", True),
        ("api-ms-win-crt-runtime-l1-1-0.dll", True),
        ("API-MS-WIN-CORE-SYNCH-L1-2-0.DLL", True),
        ("vcruntime140.dll", False),
        ("python311.dll", False),
        ("ucrtbased.dll", False),
    ],
)
def test_the_universal_crt_is_recognised_by_name(name: str, crt: bool) -> None:
    assert alpha_runtime.is_universal_crt(name) is crt


@pytest.mark.parametrize(
    ("name", "icu"),
    [
        ("icuuc.dll", True),
        ("ICUIN.DLL", True),
        ("icudt78.dll", True),
        ("icuuc78.dll", True),
        ("icu.dll", True),
        ("qt6core.dll", False),
        ("ic.dll", False),
    ],
)
def test_icu_is_recognised_by_name(name: str, icu: bool) -> None:
    """#66: Qt6Core on Windows uses the system's ICU; poppler's icuuc.dll/icudt78.dll came along from a tool folder."""
    assert alpha_runtime.is_icu(name) is icu


@pytest.mark.parametrize(
    ("name", "vc"),
    [
        ("VCRUNTIME140.dll", True),
        ("vcruntime140_1.dll", True),
        ("vcruntime140_threads.dll", True),
        ("MSVCP140.dll", True),
        ("msvcp140_1.dll", True),
        ("msvcp140_2.dll", True),
        ("msvcp140_codecvt_ids.dll", True),
        ("concrt140.dll", True),
        ("msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll", False),  # numpy.libs' vendored copy: left alone
        ("vcruntime140d.dll", False),
        ("python3.dll", False),
    ],
)
def test_the_vc_runtime_is_recognised_by_name(name: str, vc: bool) -> None:
    assert alpha_runtime.is_vc_runtime(name) is vc


def _pyside6(root: Path) -> Path:
    folder = root / "site-packages" / "PySide6"
    folder.mkdir(parents=True)
    for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll", "concrt140.dll"):
        (folder / name).write_bytes(b"14.44 " + name.encode())
    return folder


def test_binaries_lose_the_universal_crt_and_take_pyside6_s_vc_runtime(tmp_path: Path) -> None:
    """The alpha.3 inventory (issue #66 comment): top-level ucrtbase and Python's 14.38 VCRUNTIME140*, PySide6's and
    shiboken6's 14.44 copies, numpy's hashed msvcp140. Afterwards: no UCRT, every VC runtime from PySide6's folder
    (top level and subfolders alike), everything else unchanged and in the same order."""
    pyside6 = _pyside6(tmp_path)
    python = "C:/Python311"
    binaries = [
        ("python311.dll", f"{python}/python311.dll", "BINARY"),
        ("ucrtbase.dll", "C:/Windows/System32/downlevel/ucrtbase.dll", "BINARY"),
        ("api-ms-win-crt-runtime-l1-1-0.dll", "C:/x/api-ms-win-crt-runtime-l1-1-0.dll", "BINARY"),
        ("icuuc.dll", "C:/codex/poppler/Library/bin/icuuc.dll", "BINARY"),
        ("icudt78.dll", "C:/codex/poppler/Library/bin/icudt78.dll", "BINARY"),
        ("VCRUNTIME140.dll", f"{python}/VCRUNTIME140.dll", "BINARY"),
        ("VCRUNTIME140_1.dll", f"{python}/VCRUNTIME140_1.dll", "BINARY"),
        ("PySide6\\MSVCP140.dll", f"{pyside6}/msvcp140.dll", "BINARY"),
        ("shiboken6/VCRUNTIME140.dll", "C:/venv/shiboken6/vcruntime140.dll", "BINARY"),
        ("shiboken6/concrt140.dll", "C:/venv/shiboken6/concrt140.dll", "BINARY"),
        ("numpy.libs\\msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll", "C:/venv/numpy.libs/msvcp140-a4c2.dll", "BINARY"),
        ("PySide6\\Qt6Core.dll", f"{pyside6}/Qt6Core.dll", "BINARY"),
    ]
    selected = alpha_runtime.select_binaries(binaries, pyside6)
    assert selected == [
        ("python311.dll", f"{python}/python311.dll", "BINARY"),
        ("VCRUNTIME140.dll", str(pyside6 / "vcruntime140.dll"), "BINARY"),
        ("VCRUNTIME140_1.dll", str(pyside6 / "vcruntime140_1.dll"), "BINARY"),
        ("PySide6\\MSVCP140.dll", str(pyside6 / "msvcp140.dll"), "BINARY"),
        ("shiboken6/VCRUNTIME140.dll", str(pyside6 / "vcruntime140.dll"), "BINARY"),
        ("shiboken6/concrt140.dll", str(pyside6 / "concrt140.dll"), "BINARY"),
        ("numpy.libs\\msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll", "C:/venv/numpy.libs/msvcp140-a4c2.dll", "BINARY"),
        ("PySide6\\Qt6Core.dll", f"{pyside6}/Qt6Core.dll", "BINARY"),
    ]


def test_a_vc_runtime_pyside6_does_not_ship_keeps_its_source(tmp_path: Path) -> None:
    """Nothing is made up: a name PySide6's folder lacks stays as found (validate() then compares the bytes)."""
    pyside6 = _pyside6(tmp_path)
    entry = ("msvcp140_atomic_wait.dll", "C:/x/msvcp140_atomic_wait.dll", "BINARY")
    assert alpha_runtime.select_binaries([entry], pyside6) == [entry]


@pytest.mark.parametrize("renderer", ["PySide6/opengl32sw.dll", "PySide6\\OPENGL32SW.DLL"])
def test_qtcore_build_omits_the_hook_s_software_renderer(tmp_path: Path, renderer: str) -> None:
    """The Windows PySide6 hook collects this QtGui helper even for a QtCore-only app (#66)."""
    pyside6 = _pyside6(tmp_path)
    needed = [
        ("PySide6/Qt6Core.dll", str(pyside6 / "Qt6Core.dll"), "BINARY"),
        ("PySide6/QtCore.pyd", str(pyside6 / "QtCore.pyd"), "EXTENSION"),
        ("PySide6/pyside6.abi3.dll", str(pyside6 / "pyside6.abi3.dll"), "BINARY"),
        ("shiboken6/shiboken6.abi3.dll", "shiboken6.abi3.dll", "BINARY"),
        ("other/opengl32sw.dll", "other/opengl32sw.dll", "BINARY"),
    ]
    selected = alpha_runtime.select_binaries(
        [needed[0], (renderer, str(pyside6 / "opengl32sw.dll"), "BINARY"), *needed[1:]], pyside6
    )
    assert selected == needed
    app = _fake_app(tmp_path / "package")
    (app / "_internal/PySide6/opengl32sw.dll").write_bytes(b"renderer")
    with pytest.raises(ValueError, match="Qt module other than QtCore"):
        alpha_release.validate(app)  # the final-package guard remains strict


def test_the_spec_applies_the_runtime_selection() -> None:
    spec = (ROOT / "PAR_Spectrometer_2.spec").read_text(encoding="utf-8")
    assert "from tools.alpha_runtime import (" in spec and "    select_binaries,\n" in spec
    assert "a.binaries = select_binaries(a.binaries, " in spec
    assert "#66" in spec


@pytest.mark.parametrize(
    "name",
    [
        "_internal/ucrtbase.dll",
        "_internal/api-ms-win-crt-runtime-l1-1-0.dll",
        "_internal/PySide6/UCRTBASE.DLL",
        "_internal/icuuc.dll",
        "_internal/icudt78.dll",
        "_internal/PySide6/ICUIN.dll",
    ],
)
def test_package_refuses_what_windows_provides(tmp_path: Path, name: str) -> None:
    """The Universal CRT and ICU are Windows' own (#66); a bundled copy is loaded first by the frozen exe."""
    app = _fake_app(tmp_path)
    alpha_release.validate(app)
    (app / name).write_bytes(b"x")
    with pytest.raises(ValueError, match="Windows provides it"):
        alpha_release.validate(app)


def test_package_refuses_two_versions_of_a_vc_runtime_dll(tmp_path: Path) -> None:
    """Same name, different bytes (case-insensitive): Python's 14.38 at the top level, PySide6's 14.44 below."""
    app = _fake_app(tmp_path)
    for name in (
        "_internal/VCRUNTIME140.dll",
        "_internal/PySide6/vcruntime140.dll",
        "_internal/shiboken6/VCRUNTIME140.dll",
    ):
        (app / name).parent.mkdir(parents=True, exist_ok=True)
        (app / name).write_bytes(b"14.44")
    (app / "_internal/numpy.libs").mkdir()
    (app / "_internal/numpy.libs/msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll").write_bytes(b"14.40")
    (app / "_internal/msvcp140.dll").write_bytes(b"14.44 msvcp")
    alpha_release.validate(app)  # one version of each name; numpy's hashed copy is another name
    (app / "_internal/VCRUNTIME140.dll").write_bytes(b"14.38")
    with pytest.raises(ValueError, match="vcruntime140.dll") as raised:
        alpha_release.validate(app)
    assert "VCRUNTIME140.dll" in str(raised.value) and "PySide6" in str(raised.value)


# ------------------------------------------------- where binaries come from (#66: foreign tool folders on PATH)

VENV = "C:/build/par2/.venv"
BASE = "C:/Users/builder/AppData/Local/Programs/Python/Python311"
WINDOWS = "C:/Windows"
ROOTS = alpha_runtime.BuildRoots(venv=VENV, base_python=BASE, windows=WINDOWS, python_version=(3, 11))
CODEX = "C:/Users/builder/.codex-runtime/dependencies/native/libheif/bin"
PYSIDE6 = f"{VENV}/Lib/site-packages/PySide6"


def _good_binaries() -> list[alpha_runtime.Entry]:
    return [
        ("python311.dll", f"{BASE}/python311.dll", "BINARY"),
        ("python3.dll", f"{BASE}/python3.dll", "BINARY"),
        ("_ctypes.pyd", f"{BASE}\\DLLs\\_ctypes.pyd", "EXTENSION"),
        ("PySide6\\Qt6Core.dll", f"{VENV}/Lib/site-packages/PySide6/Qt6Core.dll", "BINARY"),
        ("VCRUNTIME140.dll", f"{VENV}/Lib/site-packages/PySide6/vcruntime140.dll", "BINARY"),
        ("webview\\lib\\WebView2Loader.dll", f"{VENV}/Lib/site-packages/webview/lib/WebView2Loader.dll", "DATA"),
        ("web\\index.html", "C:/build/par2/web/dist/index.html", "DATA"),
        ("dbghelp.dll", "c:\\windows\\system32\\dbghelp.dll", "BINARY"),
    ]


def test_binaries_from_the_build_venv_base_python_and_windows_pass() -> None:
    alpha_runtime.check_binary_sources(_good_binaries(), ROOTS)


@pytest.mark.parametrize(
    "entry",
    [
        ("python3.dll", f"{CODEX}/python3.dll", "BINARY"),  # another program's abi3 forwarder (#66)
        ("ucrtbase.dll", f"{CODEX}/ucrtbase.dll", "BINARY"),
        ("libheif.dll", f"{CODEX}\\libheif.dll", "BINARY"),
        ("tool.exe", "D:/tools/bin/tool.exe", "BINARY"),
        ("x.pyd", "C:/build/par2/.venv-other/x.pyd", "EXTENSION"),  # a sibling folder is not the venv
        ("PySide6\\extra.dll", "C:/Windows.old/System32/extra.dll", "DATA"),
    ],
)
def test_a_binary_from_any_other_folder_is_refused(entry: alpha_runtime.Entry) -> None:
    with pytest.raises(ValueError, match="outside the build Python") as raised:
        alpha_runtime.check_binary_sources([*_good_binaries(), entry], ROOTS)
    assert entry[1] in str(raised.value)


@pytest.mark.parametrize(
    ("binaries", "problem"),
    [
        ([("python311.dll", f"{BASE}/python311.dll", "BINARY")], "python3.dll"),
        ([("python3.dll", f"{BASE}/python3.dll", "BINARY")], "python311.dll"),
        (
            [
                ("python311.dll", f"{BASE}/python311.dll", "BINARY"),
                ("python3.dll", f"{VENV}/Scripts/python3.dll", "BINARY"),
            ],
            "python3.dll",
        ),
        (
            [
                ("python311.dll", f"{BASE}/python311.dll", "BINARY"),
                ("python3.dll", f"{BASE}/python3.dll", "BINARY"),
                ("python312.dll", f"{BASE}/python312.dll", "BINARY"),
            ],
            "python312.dll",
        ),
    ],
)
def test_python_dlls_must_come_from_the_build_s_base_python(binaries: list[alpha_runtime.Entry], problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        alpha_runtime.check_python_dlls(binaries, ROOTS)


def test_the_sources_record_round_trips_and_is_checked(tmp_path: Path) -> None:
    """The spec writes what it collected (PAR_ALPHA_BINARY_SOURCES); build_alpha.ps1 checks that file before the
    package step (`python tools/alpha_runtime.py check <file>`)."""
    record = tmp_path / "binary_sources.json"
    alpha_runtime.write_sources(record, _good_binaries(), ROOTS, PYSIDE6)
    assert alpha_runtime.main(["check", str(record)]) == 0
    foreign = ("python3.dll", f"{CODEX}/python3.dll", "BINARY")
    alpha_runtime.write_sources(record, [*_good_binaries(), foreign], ROOTS, PYSIDE6)
    with pytest.raises(ValueError, match="libheif"):
        alpha_runtime.main(["check", str(record)])


def test_the_spec_records_and_checks_the_binary_sources() -> None:
    spec = (ROOT / "PAR_Spectrometer_2.spec").read_text(encoding="utf-8")
    assert "BuildRoots.of_this_python()" in spec
    assert "check_binary_sources(" in spec and "check_python_dlls(" in spec and "check_vc_runtime_sources(" in spec
    assert "BUILD_ROOTS, PYSIDE6_DIR)" in spec
    assert "PAR_ALPHA_BINARY_SOURCES" in spec and "write_sources(" in spec


def test_the_build_script_runs_on_a_clean_path_and_checks_the_sources() -> None:
    script = (ROOT / "build_alpha.ps1").read_text(encoding="utf-8")
    assert script.isascii()
    assert "sys.base_prefix" in script and "$CleanPath" in script and "$env:Path = $CleanPath" in script
    assert 'Write-Host "PATH for the build: $CleanPath"' in script
    assert "PAR_ALPHA_BINARY_SOURCES" in script
    assert "tools\\alpha_runtime.py" in script and " check $BinarySources" in script
    npm = script.index("$NpmCommand.Source ci --no-audit --no-fund")
    pyinstaller = script.index("-m PyInstaller --noconfirm")
    assert script.index("$env:Path = $CleanPath") < pyinstaller  # the build itself never sees the caller's PATH
    assert script.rindex("$NodeDir;$CleanPath", 0, npm) >= 0  # Node only around the npm steps
    assert script.index("$env:Path = $CleanPath", npm) < pyinstaller  # and taken off again before PyInstaller
    assert "& $Git -C $ProjectRoot rev-parse HEAD" in script  # git by its full path, not from PATH


def test_vc_runtime_sources_must_be_pyside6_s_folder() -> None:
    """rv-68c: identical bytes everywhere could still all be the wrong version; the record shows where they came
    from. Python's own VCRUNTIME140 (14.38) or a tool folder's copy is refused, PySide6's passes."""
    good = [
        ("VCRUNTIME140.dll", f"{PYSIDE6}/vcruntime140.dll", "BINARY"),
        ("shiboken6\\MSVCP140.dll", f"{PYSIDE6}\\msvcp140.dll", "BINARY"),
        ("numpy.libs\\msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll", f"{VENV}/numpy.libs/msvcp140-a4c2.dll", "BINARY"),
        ("python311.dll", f"{BASE}/python311.dll", "BINARY"),
    ]
    alpha_runtime.check_vc_runtime_sources(good, PYSIDE6)
    for wrong in (f"{BASE}/vcruntime140.dll", f"{VENV}/Lib/site-packages/shiboken6/vcruntime140.dll", f"{CODEX}/x.dll"):
        with pytest.raises(ValueError, match="not taken from PySide6"):
            alpha_runtime.check_vc_runtime_sources([*good, ("vcruntime140_threads.dll", wrong, "BINARY")], PYSIDE6)


def test_the_check_command_also_checks_the_vc_runtime_source(tmp_path: Path) -> None:
    record = tmp_path / "binary_sources.json"
    python_vc = ("VCRUNTIME140.dll", f"{BASE}/VCRUNTIME140.dll", "BINARY")
    alpha_runtime.write_sources(record, [*_good_binaries(), python_vc], ROOTS, PYSIDE6)
    with pytest.raises(ValueError, match="VCRUNTIME140.dll <- "):
        alpha_runtime.main(["check", str(record)])
