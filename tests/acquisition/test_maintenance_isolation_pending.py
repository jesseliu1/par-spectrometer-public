"""D-218 question 1 (负责人 2026-10-19: "alpha 先与 V1.0.3 一致，另开 issue", the defect is #57): with a pending
communication write V1.0.3 disables the isolation box (`MaintenanceDialog.update_controls`), which keeps its tick
within one window. A manual verification is possible in the window that made the write; after the page is closed
and opened again the box is empty and disabled, and `MaintenanceDialog.submit` refuses ("请先只连接目标设备，并勾选
确认。") before anything is queued, whatever the request says."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from par_app.acquisition_host import v1_texts as texts
from tests.acquisition.conftest import Alpha
from tests.acquisition.maintenance_support import Running, enter, form, open_page, running_alpha, wait_idle

pytestmark = pytest.mark.qt


@pytest.fixture
def running(alpha: Alpha, monkeypatch: pytest.MonkeyPatch) -> Iterator[Running]:
    yield from running_alpha(alpha, monkeypatch)


def _pending(running: Running) -> dict[str, object]:
    alpha = running.alpha
    enter(alpha)
    running.devices[1].mute_after_move = True
    assert alpha.post("/api/v0/maintenance/comm/read", form()).status_code == 200
    wait_idle(alpha)
    assert alpha.confirmed("/api/v0/maintenance/comm/write", form(new=5)).status_code == 200
    state = wait_idle(alpha)  # the automatic verification fails: the write stays pending
    communication = state["communication"]
    assert communication["pending"] and communication["verify_enabled"]
    return dict(communication)


def test_the_window_that_wrote_keeps_its_tick_and_verifies_by_hand(running: Running) -> None:
    communication = _pending(running)
    assert not communication["isolation_enabled"]  # disabled while pending, as V1.0.3
    assert communication["isolated"] is True  # ... and still ticked: the write needed the tick
    running.calls.clear()
    assert running.alpha.post("/api/v0/maintenance/comm/verify", form(new=5)).status_code == 200
    assert running.calls == ["maintenance_verify"]


def test_a_reopened_page_cannot_verify_by_hand(running: Running) -> None:
    alpha = running.alpha
    _pending(running)
    assert alpha.delete("/api/v0/maintenance/page").status_code == 200
    communication = open_page(alpha, tab=2)["communication"]
    assert communication["pending"] and communication["verify_enabled"]
    assert not communication["isolation_enabled"] and communication["isolated"] is False
    running.calls.clear()
    running.refused(
        alpha.post("/api/v0/maintenance/comm/verify", form(new=5, isolated=True)),
        409,
        "precondition_failed",
        texts.ISOLATION_TEXT,
    )
