"""Device name -> default database file name stays a usable Windows file name (CONF-030; D-140 defect part).

`safe_database_filename` builds the default library `data/devices/<设备名>.sqlite3` and the export folder
`<父目录>/<设备名>/...`. V1.0.2 only replaced `\\ / : * ? " < > |` and CR/LF/TAB, so Windows reserved device
names (COM1, CON, ...), other control characters and over-long names passed through unchanged (old repo
old repository issue 11, audit robustness-ui Bug 4). Ordinary names must keep the
exact same result so already generated default paths do not move. Names changed by the new rules end in
"_" plus a digest of their V1.0.2 result, so the new rules never merge two names V1.0.2 kept apart (review
of #23: merged export folders overwrite each other) and names V1.0.2 merged stay merged (D-140). Nothing is
mocked: the long-name case creates the real SQLite library in a temp dir.
"""

from __future__ import annotations

import random
import re
import warnings
from pathlib import Path, PureWindowsPath

import pytest

from par_app.database import ParDatabase
from par_app.models import DEFAULT_DEVICE_DATABASE_DIR, default_device_database_path, safe_database_filename

pytestmark = [pytest.mark.unit, pytest.mark.spec("CONF-030")]

LIMIT = 100  # audit suggestion for one file-name segment; far below the 255 per-name limit
TAG = "_[0-9a-f]{8}"  # names changed by the new rules carry a digest of their V1.0.2 result (review of #23)


def _v102(name: str, fallback: str = "spectrometer") -> str:
    """V1.0.2 safe_database_filename, verbatim, as the reference for which names stay apart."""
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(name or "")).strip(" .")
    return cleaned or fallback


def _reserved_on_windows(name: str) -> bool:
    with warnings.catch_warnings():  # PurePath.is_reserved is deprecated from Python 3.13
        warnings.simplefilter("ignore", DeprecationWarning)
        return PureWindowsPath(name).is_reserved()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("COM1", "COM1"),
        ("con", "con"),
        ("NUL", "NUL"),
        ("aux", "aux"),
        ("Prn", "Prn"),
        ("lpt9", "lpt9"),
        ("COM1.backup", "COM1_.backup"),
        ("CON .old", "CON _.old"),
    ],
)
def test_windows_reserved_names_are_rewritten(name: str, expected: str, tmp_path: Path) -> None:
    result = safe_database_filename(name)
    assert re.fullmatch(re.escape(expected) + TAG, result)
    assert not _reserved_on_windows(result)
    assert not _reserved_on_windows(result + ".sqlite3")
    assert PureWindowsPath(default_device_database_path(name, 0, tmp_path)).name == f"{result}.sqlite3"


def test_names_that_only_look_reserved_are_unchanged() -> None:
    for name in ("COM10", "COM", "CONSOLE", "LPT0x", "温室COM1", "nul-1"):
        assert safe_database_filename(name) == name


def test_control_characters_are_replaced() -> None:
    for name in ("a\x01b", "a\x00\x1fb", "a\x7fb"):
        assert re.fullmatch("a_b" + TAG, safe_database_filename(name))
    result = safe_database_filename("温室\x02A\x1b-01\x7f")
    assert not any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in result)


def test_over_long_name_is_truncated_and_the_default_library_can_be_created(tmp_path: Path) -> None:
    result = safe_database_filename("x" * 300)
    assert 0 < len(result) <= LIMIT
    path = default_device_database_path("x" * 300, 0, tmp_path)
    ParDatabase(path)  # V1.0.2: sqlite3.OperationalError "unable to open database file"
    assert Path(path).is_file()
    folder = tmp_path / "export" / safe_database_filename("y" * 300) / "CSV"
    folder.mkdir(parents=True)  # V1.0.2: OSError "File name too long"


def test_truncation_never_leaves_trailing_space_dot_or_reserved_name() -> None:
    cut = safe_database_filename("a" * 99 + " ." + "b" * 10)
    assert len(cut) <= LIMIT
    assert not cut.endswith((" ", "."))
    cut = safe_database_filename("CON" + " " * 200 + "x")
    assert not _reserved_on_windows(cut)
    assert not cut.endswith((" ", "."))
    cut = safe_database_filename("CON." + "x" * 300)
    assert len(cut) <= LIMIT
    assert not _reserved_on_windows(cut)


def test_empty_results_use_the_fallback(tmp_path: Path) -> None:
    for name in ("", "   ", "...", " . "):
        assert safe_database_filename(name) == "spectrometer"
        assert safe_database_filename(name, "device3") == "device3"
    assert Path(default_device_database_path("", 1, tmp_path)).name == "device2.sqlite3"


def test_ordinary_names_keep_the_v102_result(tmp_path: Path) -> None:
    """Names V1.0.2 already handled keep the identical file name, so existing default paths do not move."""
    cases = {
        "光谱仪1": "光谱仪1",
        "温室A-01": "温室A-01",
        "a/b": "a_b",
        'x:*?"<>|y': "x_y",
        " 温室 B. ": "温室 B",
        "line\r\nbreak\tok": "line_break_ok",
        "z" * LIMIT: "z" * LIMIT,
    }
    for name, expected in cases.items():
        assert safe_database_filename(name) == expected
    path = Path(default_device_database_path("光谱仪1", 0, tmp_path))
    assert path == tmp_path / DEFAULT_DEVICE_DATABASE_DIR / "光谱仪1.sqlite3"


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("A" * 100 + "1", "A" * 100 + "2"),  # review of #23: identical after truncation to 100
        ("温室" * 60 + "甲", "温室" * 60 + "乙"),
        ("CON", "CON_"),  # reserved-name rewrite must not land on a name V1.0.2 already produced
        ("COM1.backup", "COM1_.backup"),
        ("a\x01b", "a_b"),  # new control-character replacement
        ("a\x01b", "a\x02b"),
    ],
)
def test_new_rules_never_merge_names_that_v102_kept_apart(first: str, second: str, tmp_path: Path) -> None:
    assert _v102(first) != _v102(second)
    assert safe_database_filename(first) != safe_database_filename(second)
    assert default_device_database_path(first, 0, tmp_path) != default_device_database_path(second, 1, tmp_path)


def test_names_that_v102_merged_stay_merged(tmp_path: Path) -> None:
    """D-140: duplicates after replacement are still rejected as today (DeviceHub.apply sees one path)."""
    for first, second in (("A/B" * 50, "A_B" * 50), ("CON/1", "CON_1"), ("x" * 150 + ":", "x" * 150 + "|")):
        assert _v102(first) == _v102(second)
        assert safe_database_filename(first) == safe_database_filename(second)
        assert default_device_database_path(first, 0, tmp_path) == default_device_database_path(second, 1, tmp_path)


def test_new_rules_keep_exactly_the_v102_groups_of_equal_names() -> None:
    """Random names mixing reserved stems, control characters, separators, dots, spaces and long runs."""
    rng = random.Random(23)
    parts = [
        "CON",
        "com1",
        "LPT9",
        "NUL",
        "aux",
        "COM¹",
        "CONIN$",
        ".",
        " ",
        "/",
        "_",
        ":",
        "\x01",
        "\x1f",
        "\x7f",
        "\t",
        "\n",
        "a",
        "温室",
        "1",
        "x" * 40,
        "y" * 97,
    ]
    names = {"".join(rng.choice(parts) for _ in range(rng.randint(1, 8))) for _ in range(4000)}
    groups: dict[str, set[str]] = {}
    for name in names:
        result = safe_database_filename(name)
        assert 0 < len(result) <= LIMIT
        assert not result.endswith((" ", "."))
        assert not any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in result)
        assert not _reserved_on_windows(result) and not _reserved_on_windows(result + ".sqlite3")
        groups.setdefault(result, set()).add(_v102(name))
    merged = {result: old for result, old in groups.items() if len(old) > 1}
    assert merged == {}
