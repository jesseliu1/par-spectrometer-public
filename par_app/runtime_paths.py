"""开发环境与 PyInstaller 发布包共用的路径解析。"""

from __future__ import annotations

import sys
import os
from pathlib import Path


def application_root() -> Path:
    """返回可写的程序目录：开发时为项目目录，发布时为 EXE 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_path(name: str) -> Path:
    """返回随程序打包的只读资源路径。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", application_root())) / name
    local_path = application_root() / name
    return local_path if local_path.exists() else application_root().parent / name


def chinese_font_path() -> Path:
    bundled = resource_path('resources/fonts/NotoSansSC.ttf')
    system = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'simhei.ttf'
    if not getattr(sys, 'frozen', False) and system.is_file():
        return system
    return bundled