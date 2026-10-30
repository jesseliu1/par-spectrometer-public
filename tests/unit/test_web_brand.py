"""The 2.0 page shows V1.0.3's company brand (UI-093): web/src/lib/brand.ts repeats V1.0.3's texts and imports the
repository's logo.png, the file V1.0.3 and the 2.0 window use. A change on one side fails here."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
NAMES = ("COMPANY_NAME", "SUPPORT_CONTACT", "SUPPORT_EMAIL", "COMPANY_WEBSITE", "COMPANY_ADDRESS")


def _v103_constants() -> dict[str, str]:
    tree = ast.parse((ROOT / "par_app" / "ui.py").read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in NAMES and isinstance(node.value, ast.Constant):
                found[node.targets[0].id] = str(node.value.value)
    return found


def _web_constants() -> dict[str, str]:
    text = (ROOT / "web" / "src" / "lib" / "brand.ts").read_text(encoding="utf-8")
    return dict(re.findall(r'export const ([A-Z_]+) =\s*"([^"]*)";', text))


def test_the_page_shows_v103_company_texts() -> None:
    v103, web = _v103_constants(), _web_constants()
    assert set(NAMES) <= set(v103), v103
    for name in NAMES:
        assert web[name] == v103[name], name


def test_the_product_name_and_purpose_follow_v103() -> None:
    """The about dialog's product name and model as V1.0.3 writes them; the purpose line keeps V1.0.3's wording
    except 光谱运算, which the pages call 光谱计算 (D-108)."""
    web = _web_constants()
    ui = (ROOT / "par_app" / "ui.py").read_text(encoding="utf-8")
    assert web["PRODUCT_NAME"] == "PAR 光谱仪专用软件" and web["PRODUCT_NAME"] in ui
    assert web["PRODUCT_MODEL"] == "ASMART-GROW-SPECTRA I" and f"{web['PRODUCT_NAME']} {web['PRODUCT_MODEL']}" in ui
    v103_purpose = (
        "面向温室、植物工厂与农业科研的光环境测量与分析工具。支持光谱采集、历史回放、光谱运算、日累计光积分及数据导出。"
    )
    assert "面向温室、植物工厂与农业科研的光环境测量与分析工具。" in ui and "日累计光积分及数据导出" in ui
    assert web["PRODUCT_PURPOSE"] == v103_purpose.replace("光谱运算", "光谱计算")


def test_the_page_uses_the_repository_logo() -> None:
    text = (ROOT / "web" / "src" / "lib" / "brand.ts").read_text(encoding="utf-8")
    assert 'import logoUrl from "../../../logo.png";' in text
    assert (ROOT / "logo.png").is_file()
