"""Microsoft Edge WebView2 runtime check on Windows (13_ appendix C). NOT VERIFIED ON WINDOWS YET.

The Evergreen runtime registers its version as the string value `pv` under the EdgeUpdate client key
{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}: per machine in HKLM (WOW6432Node on 64-bit Windows, plain on 32-bit) or
per user in HKCU. A missing key, an empty value or "0.0.0.0" means not installed (Microsoft's documented check).
When it is missing the shell does not install anything silently: it names the offline installer shipped next to
the program (S-5) and offers to open the page in the default browser instead.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from pathlib import Path

CLIENT_KEY = r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WOW_CLIENT_KEY = r"Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
VERSION_VALUE = "pv"
NOT_INSTALLED = {"", "0.0.0.0"}
OFFLINE_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
REDIST_DIR = "redist"
WEBVIEW2_MIN_BYTES = 50_000_000
"""Smallest plausible Evergreen Standalone Installer (about 150-200 MB); Microsoft's online bootstrapper
MicrosoftEdgeWebview2Setup.exe is about 2 MB and cannot install offline (review of PR #50, major 3)."""

HKLM = "HKEY_LOCAL_MACHINE"
HKCU = "HKEY_CURRENT_USER"
LOCATIONS: tuple[tuple[str, str], ...] = ((HKLM, WOW_CLIENT_KEY), (HKLM, CLIENT_KEY), (HKCU, CLIENT_KEY))

RegistryReader = Callable[[str, str, str], str | None]
"""(hive, key, value name) -> the string value, or None when the key or value does not exist."""


def windows_registry(hive: str, key: str, name: str) -> str | None:
    if sys.platform != "win32":
        return None
    import winreg  # noqa: PLC0415 (Windows only)

    root = {HKLM: winreg.HKEY_LOCAL_MACHINE, HKCU: winreg.HKEY_CURRENT_USER}[hive]
    try:
        with winreg.OpenKey(root, key) as handle:
            value, _kind = winreg.QueryValueEx(handle, name)
    except OSError:
        return None
    return str(value)


def runtime_version(read: RegistryReader, locations: Iterable[tuple[str, str]] = LOCATIONS) -> str | None:
    """The installed WebView2 runtime version, or None when none is installed."""
    for hive, key in locations:
        value = read(hive, key, VERSION_VALUE)
        if value is not None and value.strip() not in NOT_INSTALLED:
            return value.strip()
    return None


def webview2_available(platform: str = sys.platform, read: RegistryReader | None = None) -> bool:
    """True off Windows (pywebview uses the platform's own web view there) or when the runtime is installed."""
    if platform != "win32":
        return True
    return runtime_version(read or windows_registry) is not None


def offline_installer(program_dir: Path) -> Path | None:
    candidate = program_dir / REDIST_DIR / OFFLINE_INSTALLER
    return candidate if candidate.is_file() else None


def missing_runtime_message(program_dir: Path) -> str:
    installer = offline_installer(program_dir)
    where = f"随包安装程序：{installer}" if installer else f"未找到随包安装程序（应在 {program_dir / REDIST_DIR}）"
    return (
        "需要安装 Microsoft Edge WebView2 运行时才能打开窗口。\n"
        f"{where}\n安装需要您确认，本程序不会自动安装。\n\n"
        "也可以用本机浏览器（Edge / Chrome）打开界面：选择“是”用浏览器打开，选择“否”退出。"
    )
