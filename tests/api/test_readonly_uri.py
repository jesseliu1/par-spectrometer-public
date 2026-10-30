"""file: URIs of read-only connections (review Q-3: Windows network shares and mapped drives).

SQLite accepts only an empty or "localhost" authority in a file: URI, so a UNC path must not become
file://server/share/...; it is written with an empty authority, file:////server/share/... (SQLite passes the path
//server/share/... to Windows, which opens it as the UNC path). A mapped drive letter resolves to its UNC path on
Windows, so it takes the same route.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from par_app.application.readonly import file_uri

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("path", "uri"),
    [
        (
            PureWindowsPath(r"C:\PAR\data\东区 1号.sqlite3"),
            "file:///C:/PAR/data/%E4%B8%9C%E5%8C%BA%201%E5%8F%B7.sqlite3",
        ),
        (PureWindowsPath(r"\\nas01\par\data\par.sqlite3"), "file:////nas01/par/data/par.sqlite3"),
        (
            PureWindowsPath(r"C:\PAR\东区 #1 %25 &;=,.sqlite3"),  # #66: Windows-legal names a URI must escape
            "file:///C:/PAR/%E4%B8%9C%E5%8C%BA%20%231%20%2525%20%26%3B%3D%2C.sqlite3",
        ),
        (PureWindowsPath(r"\\nas01\par\温室 #2%.sqlite3"), "file:////nas01/par/%E6%B8%A9%E5%AE%A4%20%232%25.sqlite3"),
        (PureWindowsPath(r"\\?\UNC\nas01\par\par.sqlite3"), "file:////nas01/par/par.sqlite3"),
        (PureWindowsPath(r"\\?\C:\PAR\par.sqlite3"), "file:///C:/PAR/par.sqlite3"),
        (PurePosixPath("/srv/par data/par.sqlite3"), "file:///srv/par%20data/par.sqlite3"),
    ],
)
def test_file_uri_has_an_empty_authority(path: PureWindowsPath | PurePosixPath, uri: str) -> None:
    assert file_uri(path) == uri


def test_sqlite_opens_the_uri_of_a_local_file(tmp_path: Path) -> None:
    database = tmp_path / "a b" / "东区.sqlite3"
    database.parent.mkdir()
    sqlite3.connect(database).close()
    con = sqlite3.connect(f"{file_uri(database.resolve())}?mode=ro", uri=True)
    try:
        assert con.execute("PRAGMA schema_version").fetchone() is not None
    finally:
        con.close()
