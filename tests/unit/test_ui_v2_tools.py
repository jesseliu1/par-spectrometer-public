"""Developer tools of the 2.0.0-alpha web UI (tools/ui_v2_*.py) and the shell entry point.

The service, the browser, npm and pywebview are replaced by fakes; the synthetic database tool writes real files
under tmp_path only (R-4-7).
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

import par_shell.__main__ as shell_entry
from par_shell import window
from par_shell.service import ServiceError, ServiceInfo
from tools import ui_v2_demo_db, ui_v2_dev, ui_v2_screenshot

from .test_shell import FreeLock

pytestmark = pytest.mark.unit
INFO = ServiceInfo(base_url="http://127.0.0.1:50123", port=50123, token="tok", pid=1, version="2.0.0-alpha.9")


def _rows(path: Path) -> list[tuple[Any, ...]]:
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as connection:
        return connection.execute("SELECT success, exposure_status, acquired_at FROM acquisitions").fetchall()


def test_demo_db_writes_one_synthetic_day_with_failures_and_exposure_warnings(tmp_path: Path) -> None:
    target = tmp_path / "demo" / "p1.sqlite3"
    assert ui_v2_demo_db.main([str(target), "--day", "2026-10-01", "--every-minutes", "30"]) == 0
    rows = _rows(target)
    assert len(rows) == 48
    assert rows[0][2] == "2026-10-01T00:00:00.000"
    assert any(success == 0 for success, _e, _t in rows)
    assert any(exposure == 2 for _s, exposure, _t in rows)
    with sqlite3.connect(f"{target.as_uri()}?mode=ro", uri=True) as connection:
        log = connection.execute("SELECT occurred_at, level, category FROM diagnostics ORDER BY id").fetchall()
    assert log == [  # the made-up device log of the settings page (issue #107)
        ("2026-10-01T08:00:00.000", "INFO", "connection"),
        ("2026-10-01T10:05:00.000", "WARNING", "communication"),
        ("2026-10-01T10:06:00.000", "INFO", "communication_recovery"),
    ]
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        ui_v2_demo_db.main([str(target)])


def test_demo_db_stops_at_now_on_the_current_day(tmp_path: Path) -> None:
    from par_app.domain.clock import BEIJING_TZ

    now = datetime(2026, 10, 18, 1, 5, tzinfo=BEIJING_TZ)
    count = ui_v2_demo_db.write(tmp_path / "p.sqlite3", date(2026, 10, 18), ui_v2_demo_db.timedelta(minutes=30), now)
    assert count == 3  # 00:00, 00:30, 01:00
    with sqlite3.connect(f"{(tmp_path / 'p.sqlite3').as_uri()}?mode=ro", uri=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM diagnostics").fetchone() == (0,)  # 08:00 not reached yet


def test_dev_imports_each_demo_source_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    posted: list[dict[str, object]] = []
    monkeypatch.setattr(ui_v2_dev, "_post", lambda info, path, body: posted.append(body) or {})
    ui_v2_dev.import_demo(INFO, tmp_path, today=date(2026, 10, 18))
    assert [body["position"] for body in posted] == [1, 2]
    assert all(Path(str(body["source_path"])).is_file() for body in posted)
    ui_v2_dev.import_demo(INFO, tmp_path, today=date(2026, 10, 18))
    assert len(posted) == 2


class FakeService:
    started: list[tuple[Path, Path | None]] = []

    def __init__(self, data_dir: Path, web_dir: Path | None = None) -> None:
        FakeService.started.append((data_dir, web_dir))

    def __enter__(self) -> FakeService:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def start(self) -> ServiceInfo:
        return INFO


def test_dev_runs_npm_with_the_data_dir_for_the_proxy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(ui_v2_dev, "ServiceProcess", FakeService)
    monkeypatch.setattr(ui_v2_dev.shutil, "which", lambda name: "/bin/npm" if name == "npm" else None)
    monkeypatch.setattr(ui_v2_dev.subprocess, "call", lambda command, cwd, env: calls.append((command, env)) or 0)
    assert ui_v2_dev.main(["--data-dir", str(tmp_path)]) == 0
    command, env = calls[0]
    assert command == ["/bin/npm", "run", "dev"]
    assert env["PAR_ALPHA_DATA_DIR"] == str(tmp_path.resolve())


def test_dev_without_npm_or_vite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui_v2_dev, "ServiceProcess", FakeService)
    monkeypatch.setattr(ui_v2_dev.shutil, "which", lambda name: None)
    assert ui_v2_dev.main(["--data-dir", str(tmp_path)]) == 1
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    imported: list[Path] = []
    monkeypatch.setattr(ui_v2_dev, "import_demo", lambda info, data_dir: imported.append(data_dir))
    assert ui_v2_dev.main(["--data-dir", str(tmp_path), "--no-vite", "--demo"]) == 0
    assert imported == [tmp_path.resolve()]


def test_screenshot_finds_a_browser_and_runs_it_once_per_scale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    browser = tmp_path / "chrome"
    browser.write_text("", encoding="utf-8")
    assert ui_v2_screenshot.find_browser(str(browser)) == str(browser)
    monkeypatch.setenv(ui_v2_screenshot.BROWSER_ENV, str(browser))
    assert ui_v2_screenshot.find_browser(None) == str(browser)

    runs: list[list[str]] = []
    monkeypatch.setattr(ui_v2_screenshot, "ServiceProcess", FakeService)
    monkeypatch.setattr(ui_v2_screenshot, "_post", lambda info, path, body: {})
    monkeypatch.setattr(ui_v2_screenshot.ui_v2_demo_db, "main", lambda argv: 0)
    monkeypatch.setattr(ui_v2_screenshot.subprocess, "run", lambda command, **options: runs.append(command))
    built = tmp_path / "root"
    (built / "web" / "dist").mkdir(parents=True)
    (built / "web" / "dist" / "index.html").write_text("<html>", encoding="utf-8")
    monkeypatch.setattr(ui_v2_screenshot, "ROOT", built)
    assert ui_v2_screenshot.main([str(tmp_path / "out"), "--scales", "1", "1.5"]) == 0
    assert len(runs) == 2
    assert runs[1][-1] == window.page_url(INFO)
    assert "--force-device-scale-factor=1.5" in runs[1]
    assert "--disable-background-networking" in runs[0]


def test_screenshot_needs_a_browser_and_a_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ui_v2_screenshot.BROWSER_ENV, raising=False)
    monkeypatch.setattr(ui_v2_screenshot, "CANDIDATES", ())
    assert ui_v2_screenshot.main([str(tmp_path)]) == 1
    browser = tmp_path / "chrome"
    browser.write_text("", encoding="utf-8")
    monkeypatch.setattr(ui_v2_screenshot, "ROOT", tmp_path)
    assert ui_v2_screenshot.main([str(tmp_path), "--browser", str(browser)]) == 1


class ShellService(FakeService):
    fail = False

    def start(self) -> ServiceInfo:
        if ShellService.fail:
            raise ServiceError("本机服务启动失败")
        return INFO


@pytest.fixture
def shell(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    seen: dict[str, list[Any]] = {"asked": [], "browser": [], "window": []}
    ShellService.fail = False
    monkeypatch.setattr(shell_entry, "ServiceProcess", ShellService)
    monkeypatch.setattr(shell_entry, "InstanceLock", FreeLock)  # not the session-wide Windows mutex (#66)
    monkeypatch.setattr(shell_entry, "ask", lambda text, yes_no: seen["asked"].append(text) or True)
    monkeypatch.setattr(shell_entry, "open_in_browser", lambda info: seen["browser"].append(info) or True)
    monkeypatch.setattr(shell_entry, "wait_for_browser_session", lambda: None)
    monkeypatch.setattr(
        shell_entry, "open_window", lambda info, smoke_seconds=None: seen["window"].append(smoke_seconds) or True
    )
    return seen


def test_shell_opens_the_window_and_passes_smoke(shell: dict[str, list[Any]], tmp_path: Path) -> None:
    assert shell_entry.main(["--data-dir", str(tmp_path), "--smoke", "5"]) == 0
    assert shell["window"] == [5.0]


def test_shell_browser_mode_and_missing_webview2(
    shell: dict[str, list[Any]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert shell_entry.main(["--data-dir", str(tmp_path), "--browser"]) == 0
    monkeypatch.setattr(shell_entry, "webview2_available", lambda: False)
    assert shell_entry.main(["--data-dir", str(tmp_path)]) == 0  # the user chose the browser
    assert len(shell["browser"]) == 2
    assert "WebView2" in shell["asked"][0]
    assert shell["window"] == []


def test_shell_reports_a_service_that_does_not_start(shell: dict[str, list[Any]], tmp_path: Path) -> None:
    ShellService.fail = True
    assert shell_entry.main(["--data-dir", str(tmp_path)]) == 1
    assert shell["asked"] == ["本机服务启动失败"]


def test_shell_message_and_browser_wait_off_windows(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX fallbacks; the Windows message box is not exercised in tests")
    assert shell_entry.ask("说明", True) is False
    assert "说明" in capsys.readouterr().err

    def interrupted(self: object, timeout: float | None = None) -> bool:
        raise KeyboardInterrupt

    monkeypatch.setattr(shell_entry.threading.Event, "wait", interrupted)
    shell_entry.wait_for_browser_session()
    assert "Ctrl+C" in capsys.readouterr().err


def test_window_without_smoke_blocks_until_closed() -> None:
    class Webview:
        started = False

        def create_window(self, title: str, url: str, **options: Any) -> object:  # noqa: ANN401
            return object()

        def start(self) -> None:
            Webview.started = True

    assert window.open_window(INFO, webview=Webview()) is True
    assert Webview.started
