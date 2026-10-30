"""Write a SYNTHETIC V1.0.x-format history database for trying the 2.0.0-alpha history page (development only).

Usage: python tools/ui_v2_demo_db.py <new file.sqlite3> [--day YYYY-MM-DD] [--every-minutes 10]
                                    [--offset-seconds 0] [--filter none|greenhouse]

For the DLI page use --every-minutes 1: with the default poll cycle the allowed gap is 120 s, so records 10 minutes
apart never form an integrated segment. The file also gets a DLI enable time at 00:00 of the day and, when the day
has reached it, one DLI interruption at INTERRUPTION_AT (both made up, like the records), and the few device log rows
of DEMO_LOG that the day has reached (the settings page's 设备状态与最近日志, issue #107).

For the 光谱计算 page write a second file with --filter greenhouse --offset-seconds 20: the same light seen
through a made-up greenhouse cover (less blue and near infrared), each record 20 s after the first file's, so the
ratio A/B and the time difference show something.

The file is written by ParDatabase itself, i.e. exactly the format a V1.0.3 installation produces, with made-up
records: an LED-like spectrum scaled by a daylight curve, every few minutes of one Beijing day up to "now", a
failed record now and then and a few over/under-exposed ones. It refuses to touch an existing file, so it can
never write a real field database (R-4-7). Put it under an alpha data directory's data/devices and register it
(tools/ui_v2_e2e_devices.py) to see it on the pages: they show only the alpha's own device databases (issue #82).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from par_app.database import ParDatabase  # noqa: E402
from par_app.domain.clock import BEIJING_TZ, SystemClock  # noqa: E402
from par_app.math_ops import software_metrics  # noqa: E402

POINTS = 701
FIRST_NM = 350
COEFFICIENT = 3
SUNRISE_HOUR = 6
SUNSET_HOUR = 18
FAILURE_EVERY = 17
EXPOSURE_WARNING_EVERY = 23
PEAKS = ((450, 18.0, 1.0), (560, 60.0, 0.45), (660, 14.0, 0.9), (730, 20.0, 0.12))
"""(centre nm, width nm, relative height): a white+red horticultural LED, made up."""
PEAK_RAW = 1800.0
INTERRUPTION_AT = (10, 5)
"""(hour, minute) of the made-up DLI interruption."""
DEMO_LOG = (
    ((8, 0), "INFO", "connection", "总线已连接（演示数据）"),
    ((10, 5), "WARNING", "communication", "设备无应答（演示数据）"),
    ((10, 6), "INFO", "communication_recovery", "通信已恢复（演示数据）"),
)
"""((hour, minute), level, category, message) of the made-up device log rows, oldest first."""
COVER = ((0.45, 0.4, 480.0, 25.0), (0.25, 940.0, 40.0))
"""Made-up greenhouse cover transmission: base + step around 480 nm, minus a dip around 940 nm (--filter)."""


def cover_transmission(nm: int) -> float:
    (base, step, edge, width), (dip, centre, spread) = COVER
    return base + step / (1 + math.exp(-(nm - edge) / width)) - dip * math.exp(-(((nm - centre) / spread) ** 2))


def spectrum(scale: float, cover: bool = False) -> list[int]:
    raw = []
    for index in range(POINTS):
        nm = FIRST_NM + index
        level = sum(height * math.exp(-(((nm - centre) / width) ** 2)) for centre, width, height in PEAKS)
        if cover:
            level *= cover_transmission(nm)
        raw.append(max(0, round(PEAK_RAW * scale * level)))
    return raw


def daylight(moment: datetime) -> float:
    hours = moment.hour + moment.minute / 60
    if not SUNRISE_HOUR < hours < SUNSET_HOUR:
        return 0.05
    return 0.05 + math.sin(math.pi * (hours - SUNRISE_HOUR) / (SUNSET_HOUR - SUNRISE_HOUR))


def record(moment: datetime, index: int, cover: bool = False) -> dict[str, object]:
    acquired_at = moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    if index % FAILURE_EVERY == FAILURE_EVERY - 1:
        return {
            "acquired_at": acquired_at,
            "success": 0,
            "elapsed_ms": 10012.5,
            "error_stage": "read_spectrum",
            "error_detail": "读取超时（演示数据）",
            "dli_eligible": 0,
        }
    raw = spectrum(daylight(moment), cover)
    exposure = 2 if index % EXPOSURE_WARNING_EVERY == EXPOSURE_WARNING_EVERY - 1 else 0
    lux = round(sum(raw[200:350]) * 0.9, 1)
    return {
        "acquired_at": acquired_at,
        "mcu_time_ms": index * 600000,
        "success": 1,
        "initialized": 1,
        "need_power_cycle": 0,
        "raw_data_valid": 1,
        "calculate_data_valid": 1,
        "stop_status": 0,
        "spectral_coefficient": COEFFICIENT,
        "exposure_status": exposure,
        "exposure_time_us": 20000,
        "software_metrics_json": json.dumps(software_metrics(raw, COEFFICIENT)),
        "mcu_params_json": json.dumps({"lux": lux, "cct": 4870.4, "ra": 86.2, "duv": 0.0024, "x": 0.35, "y": 0.36}),
        "elapsed_ms": 5464.66,
        "raw_points": raw,
        "quality_json": json.dumps({"strategy": "single_capture", "acquisition_status": "completed"}),
        "dli_eligible": 1,
    }


def write(
    path: Path, day: date, every: timedelta, now: datetime, offset: timedelta = timedelta(), cover: bool = False
) -> int:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}: this tool only writes new synthetic files")
    path.parent.mkdir(parents=True, exist_ok=True)
    database = ParDatabase(path)
    moment = datetime(day.year, day.month, day.day, tzinfo=BEIJING_TZ) + offset
    count = 0
    while moment.date() == day and moment <= now:
        database.save_acquisition(record(moment.replace(tzinfo=None), count, cover))
        moment += every
        count += 1
    start = datetime(day.year, day.month, day.day)
    interruption = start.replace(hour=INTERRUPTION_AT[0], minute=INTERRUPTION_AT[1], second=30)
    with database.connect() as con:
        enabled_at = start.strftime("%Y-%m-%dT%H:%M:%S.000")
        con.execute(
            "INSERT INTO app_settings(key,value_json,updated_at) VALUES('dli_enabled_at',?,?)",
            (json.dumps(enabled_at), enabled_at),
        )
        if interruption <= now.replace(tzinfo=None):
            con.execute(
                "INSERT INTO dli_interruptions(occurred_at,reason) VALUES(?,?)",
                (interruption.strftime("%Y-%m-%dT%H:%M:%S.000"), "恢复命令未确认（演示数据）"),
            )
        for (hour, minute), level, category, message in DEMO_LOG:
            occurred = start.replace(hour=hour, minute=minute)
            if occurred <= now.replace(tzinfo=None):
                con.execute(
                    "INSERT INTO diagnostics(occurred_at,level,category,message,details_json) VALUES(?,?,?,?,?)",
                    (occurred.strftime("%Y-%m-%dT%H:%M:%S.000"), level, category, message, "{}"),
                )
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="new database file to create")
    parser.add_argument("--day", type=date.fromisoformat, default=None, help="Beijing day (default: today)")
    parser.add_argument("--every-minutes", type=int, default=10, help="minutes between records (default 10)")
    parser.add_argument("--offset-seconds", type=int, default=0, help="shift every record by this (default 0)")
    parser.add_argument("--filter", choices=("none", "greenhouse"), default="none", help="made-up cover (光谱计算)")
    args = parser.parse_args(argv)
    now = SystemClock().now()
    day = args.day or now.date()
    end_of_day = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=BEIJING_TZ)
    count = write(
        args.path,
        day,
        timedelta(minutes=args.every_minutes),
        min(now, end_of_day),
        timedelta(seconds=args.offset_seconds),
        args.filter == "greenhouse",
    )
    print(f"wrote {count} synthetic records to {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
