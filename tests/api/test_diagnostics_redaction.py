"""Redaction of the diagnostics bundle (D-226 问题 3; PR #63 reviews: 评审 blocker 1, 评审 M-1 and m-2).

Windows-style samples run on every platform: the Redactor works on text, so a Windows path is checked on macOS and
Linux too. Covered: drive letters and user names in any case, 8.3 short names, URL-encoded and forward-slash paths,
JSON-escaped backslashes, absolute paths outside the data directory and the home folder (only the file name stays),
UNC paths, POSIX homes, and passwords, tokens and other credentials in structured data and in text.
"""

from __future__ import annotations

import io
import json

import pytest

from par_app.application import redaction
from par_app.application.diagnostics_content import log_tail_bytes
from par_app.application.redaction import (
    DATA_DIR_MARK,
    HEADER_LINE_MARK,
    HOME_MARK,
    PATH_MARK,
    PROGRAM_DIR_MARK,
    SECRET_MARK,
    TOKEN_MARK,
    Redactor,
    scrub,
)

pytestmark = pytest.mark.unit

DATA = r"C:\Users\Alice\AppData\Local\PAR_Spectrometer_2"
HOME = r"C:\Users\Alice"
PROGRAM = r"C:\Program Files\PAR_Spectrometer_2"
TOKEN = "s3rv1ce-t0ken-value-0123456789"


@pytest.fixture
def redact() -> Redactor:
    return Redactor(TOKEN, [(DATA, DATA_DIR_MARK), (HOME, HOME_MARK), (PROGRAM, PROGRAM_DIR_MARK)])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (rf"open {DATA}\logs\service.log", rf"open {DATA_DIR_MARK}\logs\service.log"),
        (r"open c:\users\alice\appdata\local\par_spectrometer_2\logs", rf"open {DATA_DIR_MARK}\logs"),
        (r"C:/Users/Alice/AppData/Local/PAR_Spectrometer_2/x", f"{DATA_DIR_MARK}/x"),
        (r'"C:\\Users\\Alice\\AppData\\Local\\PAR_Spectrometer_2\\x"', rf'"{DATA_DIR_MARK}\\x"'),
        ("C%3A%5CUsers%5CAlice%5CDesktop%5Cx.txt", f"{HOME_MARK}%5CDesktop%5Cx.txt"),
        (r"C:\Users\alice\Desktop\x", rf"{HOME_MARK}\Desktop\x"),
        (r'File "C:\Program Files\PAR_Spectrometer_2\_internal\a.py"', rf'File "{PROGRAM_DIR_MARK}\_internal\a.py"'),
    ],
)
def test_known_folders_in_any_spelling(redact: Redactor, text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        r"tmp C:\Users\ALICE~1\AppData\Local\Temp\_MEI123\base_library.zip",
        r"c:\users\BOB\Desktop\report.txt",
        r"D:\Users\carol smith\data\x.sqlite3",
        "file:///C:/Users/Dave/Documents/x.json",
        "/Users/erin/Library/x.log",
        "/home/frank/.local/share/x.log",
    ],
)
def test_any_user_folder_becomes_home(redact: Redactor, text: str) -> None:
    out = redact(text)
    assert HOME_MARK in out, out
    for name in ("ALICE", "BOB", "carol", "Dave", "erin", "frank"):
        assert name not in out, out


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (r"database D:\温室A\客户\North.sqlite3 locked", f"database {PATH_MARK}/North.sqlite3 locked"),
        (r'"path": "e:\\Field Site\\North.sqlite3"', f'"path": "{PATH_MARK}/North.sqlite3"'),
        (r"copy to \\fileserver\share\Customer X\North.sqlite3", f"copy to {PATH_MARK}/North.sqlite3"),
        ("D%3A%5CSite%5CNorth.sqlite3", f"{PATH_MARK}/North.sqlite3"),
        (r"F:/site/x.csv,", f"{PATH_MARK}/x.csv,"),
    ],
)
def test_other_absolute_paths_keep_only_the_file_name(redact: Redactor, text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "GET /api/v0/support/maintenance-log?device=p1 200",
        "2026-10-19 09:01:00.000 http://127.0.0.1:8765/index.html",
        "x_min=350, y1=-0.015 地址 7 · COM7 · 9600 bps",
    ],
)
def test_ordinary_text_is_untouched(redact: Redactor, text: str) -> None:
    assert redact(text) == text


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ('{"password": "hunter2!"}', "hunter2!"),
        ('{"db_passwd":"pa55"}', "pa55"),
        ('"X-PAR-Token": "abcdef123"', "abcdef123"),
        ("X-PAR-Token: abcdef123", "abcdef123"),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
        ('"{""api_key"": ""k-999""}"', "k-999"),
        (r'{\"secret\": \"s-777\"}', "s-777"),
        ("{'password': 'p-555'}", "p-555"),
        ("login password=p-444&user=x", "p-444"),
        ('{"pin": 1, "password": 123456}', "123456"),
        (f"GET /#token={TOKEN}", TOKEN),
        ("Authorization: Bearer some.jwt.value", "some.jwt.value"),
    ],
)
def test_credentials_in_text(redact: Redactor, text: str, secret: str) -> None:
    out = redact(text)
    assert secret not in out, out
    assert SECRET_MARK in out or TOKEN_MARK in out, out


def test_structured_scrub_before_serialisation() -> None:
    value = {
        "bus": {"serial_port": "COM7", "password": "p1", "X-PAR-Token": "t1"},
        "devices": [{"name": "North", "api_key": "k1", "credentials": {"user": "u"}}],
        "token_count": 42,
        "slave_id": 7,
    }
    cleaned = scrub(value)
    text = json.dumps(cleaned)
    assert "p1" not in text and "t1" not in text and "k1" not in text and '"u"' not in text
    assert cleaned["bus"]["serial_port"] == "COM7" and cleaned["devices"][0]["name"] == "North"
    assert cleaned["bus"]["password"] == SECRET_MARK and cleaned["bus"]["X-PAR-Token"] == TOKEN_MARK
    assert cleaned["token_count"] == 42 and cleaned["slave_id"] == 7
    assert value["bus"]["password"] == "p1"  # the input is not changed


def test_cell_with_json_is_scrubbed_structurally(redact: Redactor) -> None:
    cell = json.dumps({"action": "maintenance_write", "password": "pw-1", "connection": {"serial_port": "COM7"}})
    out = redact.cell(cell)
    assert "pw-1" not in out and json.loads(out)["connection"]["serial_port"] == "COM7"
    assert redact.cell(7) == 7 and redact.cell(None) is None


def test_redaction_is_idempotent(redact: Redactor) -> None:
    text = rf'{DATA}\x D:\a\b.txt password=p token={TOKEN} \\srv\s\c.txt'
    once = redact(text)
    assert redact(once) == once


def test_for_paths_uses_the_data_dir_home_and_program_folder(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    from par_app.application.paths import AlphaPaths

    data_dir = tmp_path / "home" / "alpha"
    data_dir.mkdir(parents=True)
    (data_dir / "service.json").write_text(json.dumps({"token": TOKEN}), encoding="utf-8")
    monkeypatch.setattr(redaction, "program_folder", lambda: tmp_path / "prog")
    redact = Redactor.for_paths(AlphaPaths(data_dir), home=tmp_path / "home")
    assert redact(f"{data_dir}/logs {tmp_path / 'home'}/x {tmp_path / 'prog'}/a {TOKEN}") == (
        f"{DATA_DIR_MARK}/logs {HOME_MARK}/x {PROGRAM_DIR_MARK}/a {TOKEN_MARK}"
    )


class _Growing(io.BytesIO):
    """A log that grows by 100 bytes right after its size was taken (the service keeps writing)."""

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        position = super().seek(offset, whence)
        if whence == io.SEEK_END:
            super().write(b"x" * 99 + b"\n")
            super().seek(position)
        return position


def test_log_tail_reads_at_most_the_limit_while_the_log_grows() -> None:
    handle = _Growing(b"".join(f"line {index}\n".encode() for index in range(100)))
    data, cut = log_tail_bytes(handle, 64)
    assert cut and len(data) <= 64
    assert data.startswith(b"line ")  # from the first whole line


# PR #63 re-review (rv-63b) item 1: no fragment of a secret may survive, whatever its quoting.
FRAGMENT_CASES = [
    (r'{"password":"first\u0041SENSITIVE_TAIL"}', ["first", "SENSITIVE_TAIL", "u0041"]),
    (r'{"password": "with \"quoted\" PART2 inside"}', ["quoted", "PART2", "inside"]),
    ('password="TWO WORDS_SECRET"', ["TWO", "WORDS_SECRET"]),
    ("password='SINGLE QUOTED_SECRET'", ["SINGLE", "QUOTED_SECRET"]),
    ("Cookie: a=SENSITIVE1; b=SENSITIVE2; c=SENSITIVE3", ["SENSITIVE1", "SENSITIVE2", "SENSITIVE3"]),
    ("Set-Cookie: sid=SENSITIVE4; Path=/; HttpOnly", ["SENSITIVE4"]),
    ('"{""password"": ""CSV PART1 \\"" PART2""}"', ["CSV", "PART1", "PART2"]),
    (r'{\"api_key\": \"ESCAPED_ONE \\\" ESCAPED_TWO\"}', ["ESCAPED_ONE", "ESCAPED_TWO"]),
    ("{'secret': 'REPR_A \\' REPR_B'}", ["REPR_A", "REPR_B"]),
]


@pytest.mark.parametrize(("text", "fragments"), FRAGMENT_CASES)
def test_no_fragment_of_a_secret_survives(redact: Redactor, text: str, fragments: list[str]) -> None:
    out = redact(text)
    for fragment in fragments:
        assert fragment not in out, (fragment, out)


@pytest.mark.parametrize(
    ("text", "fragments"),
    [
        (r"open \\?\UNC\customer-server\customer-share\dir\x.sqlite3", ["customer-server", "customer-share", "dir"]),
        ("open %5C%5Ccustomer-server%5Ccustomer-share%5Cx.sqlite3", ["customer-server", "customer-share"]),
        (r"open \\?\D:\Customer Site\x.sqlite3", ["Customer Site"]),
        ('File "/srv/customer-site/app/a.py", line 3', ["srv", "customer-site"]),
    ],
)
def test_extended_encoded_unc_and_traceback_paths(redact: Redactor, text: str, fragments: list[str]) -> None:
    out = redact(text)
    assert PATH_MARK in out, out
    for fragment in fragments:
        assert fragment not in out, (fragment, out)


def test_setting_rows_named_after_a_credential(redact: Redactor) -> None:
    """app_settings rows are exported as {"key": ..., "value": ...}: the setting's name decides."""
    rows = [
        {"key": "password", "value": "SETTING_PW_1", "updated_at": "t"},
        {"key": "x-par-token", "value": {"nested": "SETTING_TOKEN_2"}, "updated_at": "t"},
        {"key": "dli_location", "value": {"lat": 1.5}, "updated_at": "t"},
    ]
    text = json.dumps(redact.structure(rows))
    assert "SETTING_PW_1" not in text and "SETTING_TOKEN_2" not in text and '"lat": 1.5' in text


def test_non_credential_keys_are_kept(redact: Redactor) -> None:
    """Counts, retries and error texts named after a credential are diagnostics, not credentials (rv-63b nit)."""
    value = {"token_count": 42, "password_retries": 3, "last_token_error": "connection failed", "max_tokens": 9}
    assert scrub(value) == value
    text = 'token_count=42 password_retries=3 "last_token_error": "connection failed"'
    assert redact(text) == text
    assert scrub({"dbPassword": "x", "auth_token": "y", "session-id": "z"}) == {
        "dbPassword": SECRET_MARK,
        "auth_token": TOKEN_MARK,
        "session-id": SECRET_MARK,
    }


# PR #63 third review (rv-63c) items 1 and 3: a credential key drops the rest of its line; cookie and
# authorization header lines go entirely; encoded extended UNC and //server/share paths.
THIRD_REVIEW_CASES = [
    ("""{'password': "FIRST'S SECOND"}""", ["FIRST", "SECOND"]),
    ('{"password":["FIRST","SECOND"]}', ["FIRST", "SECOND"]),
    ('{"password": {"nested": "FIRST"}, "x": "SECOND"}', ["FIRST", "SECOND"]),
    ("Cookie=a=FIRST; b=SECOND", ["FIRST", "SECOND"]),
    ("headers: {'Cookie': 'a=FIRST; b=SECOND'}", ["FIRST", "SECOND"]),
    ("Authorization: Digest username=FIRST, response=SECOND", ["FIRST", "SECOND"]),
    ("secret = FIRST SECOND", ["FIRST", "SECOND"]),
]


@pytest.mark.parametrize(("text", "fragments"), THIRD_REVIEW_CASES)
def test_credential_line_rest_is_dropped(redact: Redactor, text: str, fragments: list[str]) -> None:
    out = redact(f"before line\n{text}\nafter line")
    for fragment in fragments:
        assert fragment not in out, (fragment, out)
    assert out.startswith("before line\n") and out.endswith("\nafter line")


@pytest.mark.parametrize(
    "text",
    [
        "open %5C%5C%3F%5CUNC%5Ccustomer-server%5Ccustomer-share%5Cx.db",
        "open //customer-server/customer-share/x.db",
        "open %2F%2Fcustomer-server%2Fcustomer-share%2Fx.db",
    ],
)
def test_encoded_extended_and_forward_slash_unc(redact: Redactor, text: str) -> None:
    out = redact(text)
    assert out == f"open {PATH_MARK}/x.db", out


def test_urls_are_not_unc_paths(redact: Redactor) -> None:
    text = "GET http://127.0.0.1:8765/api/v0/support/maintenance-log https://example.com/a/b"
    assert redact(text) == text


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
def test_credential_header_lines_go_entirely_with_any_line_ending(redact: Redactor, newline: str) -> None:
    """#66: logs written on Windows end their lines with CRLF; the header rule must not need a bare LF."""
    lines = ["before", "Authorization: Bearer abc.def", "Set-Cookie: a=1", "Proxy-Authorization: Basic eA==", "after"]
    out = redact(newline.join(lines) + newline)
    assert out == newline.join(["before", HEADER_LINE_MARK, HEADER_LINE_MARK, HEADER_LINE_MARK, "after"]) + newline


@pytest.mark.parametrize(
    "value",
    [
        r"C:\Users\Alice\AppData\Local\Temp\pytest-of-alice\Customer Site\North.sqlite3",
        r"c:\users\ALICE~1\Customer Site\North.sqlite3",
        r"C:\Users\Bob\Customer Site\North.sqlite3",
        "C:/Users/Alice/Customer Site/North.sqlite3",
        r"D:\Customer Site\North.sqlite3",
        r"\\nas01\Customer Site\North.sqlite3",
        r"\\?\C:\Customer Site\North.sqlite3",
        r"\\?\UNC\nas01\Customer Site\North.sqlite3",
        "/Users/alice/Customer Site/North.sqlite3",
        "/srv/Customer Site/North.sqlite3",
    ],
)
def test_a_whole_absolute_path_in_structured_data_keeps_only_its_file_name(redact: Redactor, value: str) -> None:
    """#66: a database path outside the alpha folder (app_config.json, an allowlisted field) is cut to its file name
    whatever the host system: a Windows path under a home folder used to keep the folder names after <HOME>."""
    assert redact.structure({"database_path": value}) == {"database_path": f"{PATH_MARK}/North.sqlite3"}


def test_paths_inside_the_alpha_and_program_folders_and_plain_values_are_kept(redact: Redactor) -> None:
    value = {
        "inside": rf"{DATA}\data\devices\North.sqlite3",
        "program": rf"{PROGRAM}\_internal\x.dll",
        "port": "COM7",
        "host": "127.0.0.1",
        "name": "North",
        "relative": r"data\devices\North.sqlite3",
    }
    assert redact.structure(value) == value | {
        "inside": rf"{DATA_DIR_MARK}\data\devices\North.sqlite3",
        "program": rf"{PROGRAM_DIR_MARK}\_internal\x.dll",
    }


@pytest.mark.parametrize("value", [HOME, "/Users/alice"])
def test_a_home_folder_alone_stays_home_in_structured_data(redact: Redactor, value: str) -> None:
    """Never the user name: the home folder itself is not cut to its last name."""
    out = redact.structure({"folder": value})["folder"]
    assert out == HOME_MARK and "lice" not in out


@pytest.mark.parametrize(
    "value",
    [
        "/srv/Customer Site/",
        r"C:\Users\Alice\Customer Site" + "\\",
        r"D:\Customer Site" + "\\",
        "C:/Users/Bob/Customer Site/",
        r"\\nas01\Customer Site" + "\\",
        "/Customer Site/",  # one-level folders: rv-68b
        r"E:\Customer Site" + "\\",
    ],
)
def test_a_whole_absolute_folder_in_structured_data_keeps_no_folder_name(redact: Redactor, value: str) -> None:
    """review of PR #68: a folder value (ending in a separator) has no file name; none of its names stay."""
    out = redact.structure({"folder": value})["folder"]
    assert out == f"{PATH_MARK}/" and "Customer" not in out


def test_a_one_level_whole_folder_keeps_no_name(redact: Redactor) -> None:
    """rv-68b: `/srv/` alone was kept because a one-name path was taken for the home folder."""
    assert redact.structure({"folder": "/srv/"})["folder"] == f"{PATH_MARK}/"


@pytest.mark.parametrize("value", [HOME + "\\", "/Users/alice/"])
def test_the_home_folder_with_a_trailing_separator_stays_home(redact: Redactor, value: str) -> None:
    out = redact.structure({"folder": value})["folder"]
    assert out.startswith(HOME_MARK) and "lice" not in out
