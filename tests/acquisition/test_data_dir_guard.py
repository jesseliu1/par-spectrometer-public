"""The alpha refuses a data directory that is a V1.0.3 program folder (PR #54 review Q2; 15_ 5; D-215).

V1.0.3 keeps config/app_config.json and data/devices/ relative to its program folder, the same layout the alpha uses
under its data directory. Pointed there with --data-dir or PAR_ALPHA_DATA_DIR, the alpha would read and write
V1.0.3's configuration and databases ("never write V1.0.3 data"). The service therefore refuses to start when the
directory holds V1.0.3's program files (the packaged _internal folder or PAR_Spectrometer.exe, or main.py with
par_app/ when run from source), before it creates anything there.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from par_app import service_main
from par_app.application.paths import v103_program_marker

pytestmark = pytest.mark.qt


@pytest.mark.parametrize(
    "files",
    [["_internal/"], ["PAR_Spectrometer.exe"], ["main.py", "par_app/"]],
    ids=["packaged", "exe", "source"],
)
def test_a_v103_program_folder_is_refused_before_anything_is_written(
    qt_app: object, tmp_path: Path, files: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "PAR_Spectrometer_V1.0.3"
    for name in files:
        target = folder / name.rstrip("/")
        if name.endswith("/"):
            target.mkdir(parents=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")
    (folder / "config").mkdir()
    (folder / "config" / "app_config.json").write_text("{}", encoding="utf-8")
    before = sorted(folder.rglob("*"))
    assert v103_program_marker(folder) is not None
    assert service_main.main(["--port", "0", "--data-dir", str(folder)]) == service_main.EXIT_REFUSED_DATA_DIR
    assert sorted(folder.rglob("*")) == before
    assert "V1.0.3 的程序目录" in capsys.readouterr().err


def test_an_ordinary_alpha_folder_is_accepted(tmp_path: Path) -> None:
    folder = tmp_path / "alpha data"
    (folder / "config").mkdir(parents=True)
    (folder / "config" / "app_config.json").write_text("{}", encoding="utf-8")  # the alpha's own tier-1 file
    (folder / "main.py").write_text("", encoding="utf-8")  # one marker alone is not a program folder
    assert v103_program_marker(folder) is None
    assert v103_program_marker(tmp_path / "missing") is None
