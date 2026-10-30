"""The Windows C/C++ runtime DLLs of the alpha package (PAR_Spectrometer_2.spec; tools/alpha_release.py checks them).

Issue #66: the frozen alpha.3 exe stopped with "DLL load failed while importing QtCore: 找不到指定的程序" (a procedure
not found) while the same code ran from source. Its _internal/ held DLLs from a polluted build PATH: ucrtbase.dll
and 44 api-ms-win-*.dll from a build agent's tool folder (<codex-runtime>/.../libheif/bin), icuuc.dll and icudt78.dll
from another (<codex-runtime>/.../poppler/Library/bin); and two VC++ runtimes (Python's VCRUNTIME140*.dll 14.38 at
the top level, PySide6's and shiboken6's 14.44 in their folders). The root cause is still being confirmed on Windows:
unifying the VC++ runtime and removing ucrtbase.dll alone did not fix it; the bundled ICU is the current suspect
(Qt6Core uses the system's ICU). Whatever the cause, these files do not belong in the package, so:

1. Never bundle what Windows provides: the Universal CRT (ucrtbase.dll, api-ms-win-*.dll) and ICU (icuuc, icuin,
   icudt*, icu.dll). Both are part of Windows 10 1809 and later, which the alpha requires (Microsoft documents that
   Windows 10/11 use the system's UCRT; a bundled copy is at best unused and here came from a foreign tool).
2. One VC++ runtime version: every vcruntime140*.dll (incl. _1, _threads), msvcp140*.dll and concrt140.dll in the
   package - top level, PySide6/ and shiboken6/ - comes from PySide6's own folder in the build environment. PySide6
   6.11 is built with the newest toolset of all bundled binaries (14.44; Python 3.11.9 ships 14.38) and the VC++
   runtime is backward compatible. Chosen by where the file comes from, not by reading version resources, so it
   behaves the same wherever the spec or this test runs. A name PySide6 does not ship keeps its source (the checks
   below then refuse it). Vendored copies with a hash in the name (numpy.libs/msvcp140-<hash>.dll) are other names
   to Windows and stay as they are.
3. Build PATH and binary sources: build_alpha.ps1 runs the build on a clean PATH; the spec refuses - and records for
   `python tools/alpha_runtime.py check <file>`, which build_alpha.ps1 runs before the package step - any collected
   .dll/.pyd/.exe whose source lies outside the build venv, its base Python and the Windows folder
   (`check_binary_sources`), a python3.dll or python3XX.dll that is not the build Python's own (`check_python_dlls`),
   and a VC++ runtime DLL whose source is not PySide6's package folder (`check_vc_runtime_sources`).

What the checks prove, and what not: the package check (`check_c_runtime`) refuses the UCRT and ICU anywhere and
same-named VC++ runtime copies whose bytes differ; it does not prove that the one version shipped is the right one.
That rests on the source check above (PySide6's folder, from the build record) and on the frozen self-test.

Not verifiable on macOS: that the frozen exe then imports QtCore on Windows (the next Windows build, #66).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

UCRT = re.compile(r"^(?:ucrtbase|api-ms-win-.+)\.dll$", re.IGNORECASE)
"""The Universal CRT: ucrtbase.dll and its api-ms-win-* forwarders (never bundled, #66)."""
ICU = re.compile(r"^icu[a-z]*\d*\.dll$", re.IGNORECASE)
"""ICU (icuuc, icuin, icudt78, icu.dll): Qt6Core on Windows uses the system's ICU in System32. alpha.3 carried
poppler's icuuc.dll/icudt78.dll (versioned exports) from a tool folder; loaded first by the frozen exe, they are the
prime suspect for "procedure not found" when importing QtCore (#66). Never bundled."""
VC_RUNTIME = re.compile(r"^(?:vcruntime140(?:_1|_threads)?|msvcp140(?:_[a-z0-9_]+)?|concrt140)\.dll$", re.IGNORECASE)
"""The Visual C++ 2015-2022 runtime DLLs by their plain names (not the debug "d" builds, not hashed vendored copies)."""

Entry = tuple[str, str, str]
"""A PyInstaller TOC entry: (name in the package, source path, type code)."""


def is_universal_crt(name: str) -> bool:
    return bool(UCRT.match(name))


def is_icu(name: str) -> bool:
    return bool(ICU.match(name))


def is_windows_provided(name: str) -> bool:
    """The Universal CRT and ICU: part of Windows 10 1809+, never shipped in the package (#66)."""
    return is_universal_crt(name) or is_icu(name)


def is_vc_runtime(name: str) -> bool:
    return bool(VC_RUNTIME.match(name))


def _file_name(package_name: str) -> str:
    return re.split(r"[\\/]", package_name)[-1]


def select_binaries(binaries: Iterable[Entry], pyside6_dir: Path) -> list[Entry]:
    """`binaries` without the Universal CRT, every VC++ runtime DLL taken from `pyside6_dir` (PySide6's package
    folder) where it has that name, and without PySide6's unused software OpenGL renderer."""
    shipped = {path.name.lower(): path for path in pyside6_dir.glob("*.dll") if is_vc_runtime(path.name)}
    selected: list[Entry] = []
    for name, source, kind in binaries:
        file_name = _file_name(name)
        if is_windows_provided(file_name):
            continue
        # PyInstaller's PySide6 hook collects this QtGui helper even when only QtCore is imported (#66).
        # Keep the final-package Qt guard unchanged; omit the unused renderer at collection time instead.
        if name.replace("\\", "/").lower() == "pyside6/opengl32sw.dll":
            continue
        if is_vc_runtime(file_name) and file_name.lower() in shipped:
            source = str(shipped[file_name.lower()])
        selected.append((name, source, kind))
    return selected


def check_c_runtime(app_root: Path) -> None:
    """tools/alpha_release.py validate(): raise ValueError if the package holds the Universal CRT anywhere, or a VC++
    runtime DLL name in more than one version (different bytes; names compared without case, as Windows does)."""
    copies: dict[str, list[Path]] = {}
    for source in sorted(app_root.rglob("*.[dD][lL][lL]")):
        relative = source.relative_to(app_root)
        if is_universal_crt(source.name):
            raise ValueError(f"the Universal CRT must not be shipped (Windows provides it, #66): {relative}")
        if is_icu(source.name):
            raise ValueError(f"ICU must not be shipped (Windows provides it, #66): {relative}")
        if is_vc_runtime(source.name):
            copies.setdefault(source.name.lower(), []).append(source)
    for name, paths in copies.items():
        if len({hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}) > 1:
            listed = ", ".join(str(path.relative_to(app_root)) for path in paths)
            raise ValueError(f"{name} is shipped in more than one version (one VC++ runtime only, #66): {listed}")


BINARY_SUFFIXES = (".dll", ".pyd", ".exe")


@dataclass(frozen=True)
class BuildRoots:
    """The only folders a bundled binary may come from: the build venv, its base Python install, Windows."""

    venv: str
    base_python: str
    windows: str
    python_version: tuple[int, int]

    @classmethod
    def of_this_python(cls) -> BuildRoots:
        windows = os.environ.get("SystemRoot") or "C:\\Windows"
        return cls(sys.prefix, sys.base_prefix, windows, (sys.version_info[0], sys.version_info[1]))


def _norm(path: str) -> str:
    """Windows rules on any host: case-insensitive, either separator, no trailing separator."""
    return path.replace("\\", "/").rstrip("/").lower()


def _inside(source: str, root: str) -> bool:
    folder = _norm(root)
    return _norm(source) == folder or _norm(source).startswith(folder + "/")


def check_binary_sources(entries: Iterable[Entry], roots: BuildRoots) -> None:
    """Raise ValueError naming every collected .dll/.pyd/.exe whose source is outside the build roots."""
    allowed = (roots.venv, roots.base_python, roots.windows)
    foreign = [
        f"{name} <- {source}"
        for name, source, _kind in entries
        if source.lower().endswith(BINARY_SUFFIXES) and not any(_inside(source, root) for root in allowed)
    ]
    if foreign:
        raise ValueError(
            "binaries from outside the build Python (venv, base install) and Windows; is a tool folder on PATH? "
            f"(#66): {'; '.join(foreign)}"
        )


def check_python_dlls(entries: Sequence[Entry], roots: BuildRoots) -> None:
    """python3.dll and python3XX.dll (the build's version) must be shipped, both from the base Python's folder; no
    other python3NN.dll may be shipped."""
    major, minor = roots.python_version
    own = f"python{major}{minor}.dll"
    found: dict[str, str] = {}
    for name, source, _kind in entries:
        file_name = _file_name(name).lower()
        if re.fullmatch(r"python\d+\.dll", file_name):
            found[file_name] = source
    for name in sorted(found):
        if name not in (f"python{major}.dll", own):
            raise ValueError(f"{name} is another Python's DLL; the build is Python {major}.{minor} (#66)")
    for name in (f"python{major}.dll", own):
        if name not in found:
            raise ValueError(f"{name} is not in the package (expected from {roots.base_python})")
        folder = re.split(r"[\\/](?=[^\\/]*$)", found[name])[0]
        if _norm(folder) != _norm(roots.base_python):
            raise ValueError(f"{name} comes from {found[name]}, not from the build's Python {roots.base_python} (#66)")


def check_vc_runtime_sources(entries: Iterable[Entry], pyside6_dir: str) -> None:
    """Every VC++ runtime DLL in the package must come from PySide6's package folder (rule 2): byte-identical copies
    alone could all be the wrong version (review rv-68c)."""
    foreign = [
        f"{name} <- {source}"
        for name, source, _kind in entries
        if is_vc_runtime(_file_name(name)) and _norm(re.split(r"[\\/](?=[^\\/]*$)", source)[0]) != _norm(pyside6_dir)
    ]
    if foreign:
        raise ValueError(f"VC++ runtime not taken from PySide6's folder {pyside6_dir} (#66): {'; '.join(foreign)}")


def write_sources(path: Path, entries: Iterable[Entry], roots: BuildRoots, pyside6_dir: Path | str) -> None:
    """The record build_alpha.ps1 checks: the build roots, PySide6's folder and every collected (name, source, kind)."""
    record = {"roots": asdict(roots), "pyside6_dir": str(pyside6_dir), "entries": [list(entry) for entry in entries]}
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """`python tools/alpha_runtime.py check <binary_sources.json>`: both checks on the spec's record."""
    command, record_path = argv if argv is not None else sys.argv[1:]
    if command != "check":
        raise SystemExit("usage: alpha_runtime.py check <binary_sources.json>")
    record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    roots_record = record["roots"]
    roots = BuildRoots(
        str(roots_record["venv"]),
        str(roots_record["base_python"]),
        str(roots_record["windows"]),
        (int(roots_record["python_version"][0]), int(roots_record["python_version"][1])),
    )
    entries = [(str(name), str(source), str(kind)) for name, source, kind in record["entries"]]
    check_binary_sources(entries, roots)
    check_python_dlls(entries, roots)
    check_vc_runtime_sources(entries, str(record["pyside6_dir"]))
    print(f"binary sources OK: {len(entries)} entries from the build Python and Windows only")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"binary sources refused: {error}", file=sys.stderr)
        raise SystemExit(1) from error
