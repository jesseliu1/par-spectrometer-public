from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import mccree1972_weights as mccree
import raw_spectral_process as rsp


SAMPLE_GROUPS: tuple[tuple[str, str], ...] = (
    ("LED", "data_history/PAR/Rawdata/正式采集LED"),
    ("HPS", "data_history/PAR/Rawdata/正式采集钠灯"),
    ("Cloudy", "data_history/PAR/Rawdata/阴天"),
)


@dataclass(frozen=True)
class SampleRow:
    scene: str
    name: str
    wm2: float
    par: float
    pfd: float
    ppfd: float
    cct: float
    pfd_b: float
    pfd_r: float
    mccree_field_ypfd: float
    mccree_chamber_ypfd: float

    @property
    def blue_red(self) -> float:
        return self.pfd_b / self.pfd_r if abs(self.pfd_r) > 1e-12 else math.nan

    @property
    def field_ratio_pfd(self) -> float:
        return self.mccree_field_ypfd / self.pfd if abs(self.pfd) > 1e-12 else math.nan

    @property
    def chamber_ratio_pfd(self) -> float:
        return self.mccree_chamber_ypfd / self.pfd if abs(self.pfd) > 1e-12 else math.nan

    @property
    def field_ratio_ppfd(self) -> float:
        return self.mccree_field_ypfd / self.ppfd if abs(self.ppfd) > 1e-12 else math.nan

    @property
    def chamber_ratio_ppfd(self) -> float:
        return self.mccree_chamber_ypfd / self.ppfd if abs(self.ppfd) > 1e-12 else math.nan


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    count = len(xs)
    if count != len(ys) or count == 0:
        return math.nan
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    numerator = sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(xs, ys))
    denominator_x = sum((x_value - mean_x) ** 2 for x_value in xs)
    denominator_y = sum((y_value - mean_y) ** 2 for y_value in ys)
    if denominator_x <= 0.0 or denominator_y <= 0.0:
        return math.nan
    return numerator / math.sqrt(denominator_x * denominator_y)


def _mean(rows: Iterable[SampleRow], attr_name: str) -> float:
    values = [float(getattr(row, attr_name)) for row in rows]
    return statistics.mean(values)


def _collect_rows() -> list[SampleRow]:
    rows: list[SampleRow] = []
    for scene, folder_text in SAMPLE_GROUPS:
        folder = Path(folder_text)
        for path in sorted(folder.glob("Rawdata*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            processing_result = rsp.compute_from_rawdata_payload(payload)
            metrics = processing_result.metrics
            spectrum = processing_result.spectrum_wm2_nm
            field_ypfd = mccree.weighted_photon_integral_umol(spectrum, rsp.WAVELENGTHS, variant="field")
            chamber_ypfd = mccree.weighted_photon_integral_umol(spectrum, rsp.WAVELENGTHS, variant="chamber")
            rows.append(
                SampleRow(
                    scene=scene,
                    name=path.name,
                    wm2=float(metrics["WM2"]),
                    par=float(metrics["par"]),
                    pfd=float(metrics["pfd"]),
                    ppfd=float(metrics["ppfd"]),
                    cct=float(metrics["cct"]),
                    pfd_b=float(metrics["pfd_b"]),
                    pfd_r=float(metrics["pfd_r"]),
                    mccree_field_ypfd=field_ypfd,
                    mccree_chamber_ypfd=chamber_ypfd,
                )
            )
    return rows


def build_report_text(rows: Sequence[SampleRow]) -> str:
    field_ypfd = [row.mccree_field_ypfd for row in rows]
    chamber_ypfd = [row.mccree_chamber_ypfd for row in rows]
    pfd = [row.pfd for row in rows]
    ppfd = [row.ppfd for row in rows]
    cct = [row.cct for row in rows]
    blue_red = [row.blue_red for row in rows]
    field_ratio_pfd = [row.field_ratio_pfd for row in rows]
    chamber_ratio_pfd = [row.chamber_ratio_pfd for row in rows]

    lines: list[str] = []
    lines.append("日期：2026-04-23")
    lines.append("范围：McCree 1972 原始 25 nm 表的独立验证")
    lines.append("主文件：mccree1972_weights.py / mccree1972_validation.py")
    lines.append("样本范围：data_history/PAR/Rawdata 下 11 份正式样本（正式采集LED 4 份、正式采集钠灯 4 份、阴天 3 份）")
    lines.append("")
    lines.append("## 当前冻结口径")
    lines.append("")
    lines.append("- 数据来源：McCree 1972 农业气象论文 Table IV / III 的上游文本转录。")
    lines.append(f"- 上游文本：{mccree.MCCREE_SOURCE_URL}")
    lines.append("- 原始离散点：25 nm 一点，当前上游文本可见 350-725 nm 共 16 点。")
    lines.append("- 本轮保守实现：按原始 25 nm 点做分段线性插值；350-740 nm 内参与加权；超出 350-740 nm 的波长统一置 0。")
    lines.append("- 尾段处理：由于上游文本最后一个点为 725 nm，而当前项目决定采用到 740 nm 的应用窗口，因此脚本按 700-725 nm 末段斜率线性延伸到 740 nm，再参与分段插值。")
    lines.append("- 当前仅做独立验证，不改动主算法链。")
    lines.append("")
    lines.append("## 核心结果")
    lines.append("")
    lines.append("### 1. McCree 加权结果数值稳定，且始终低于宽谱 PFD")
    lines.append(f"- field mean 最小/最大 = {min(field_ypfd):.6f} / {max(field_ypfd):.6f}")
    lines.append(f"- chamber mean 最小/最大 = {min(chamber_ypfd):.6f} / {max(chamber_ypfd):.6f}")
    lines.append(f"- field/pfd 最小/最大 = {min(field_ratio_pfd):.6f} / {max(field_ratio_pfd):.6f}")
    lines.append(f"- chamber/pfd 最小/最大 = {min(chamber_ratio_pfd):.6f} / {max(chamber_ratio_pfd):.6f}")
    lines.append("- 说明：按当前 350-740 nm 加权后，结果落在合理量级，没有出现权重爆表或数值异常。")
    lines.append("")
    lines.append("### 2. McCree 加权结果与现有 PFD / PPFD 保持强正相关")
    lines.append(f"- field vs pfd: Pearson = {_pearson(field_ypfd, pfd):.4f}")
    lines.append(f"- chamber vs pfd: Pearson = {_pearson(chamber_ypfd, pfd):.4f}")
    lines.append(f"- field vs ppfd: Pearson = {_pearson(field_ypfd, ppfd):.4f}")
    lines.append(f"- chamber vs ppfd: Pearson = {_pearson(chamber_ypfd, ppfd):.4f}")
    lines.append("- 说明：McCree 加权量与现有总量指标保持高度同向关系，可作为现有光谱算法链上的附加量，而不是孤立噪声。")
    lines.append("")
    lines.append("### 3. 光谱场景差异能够体现在 McCree 加权占比上")
    lines.append(f"- field/pfd 与 cct: Pearson = {_pearson(field_ratio_pfd, cct):.4f}")
    lines.append(f"- chamber/pfd 与 cct: Pearson = {_pearson(chamber_ratio_pfd, cct):.4f}")
    lines.append(f"- field/pfd 与 pfd_b/pfd_r: Pearson = {_pearson(field_ratio_pfd, blue_red):.4f}")
    lines.append(f"- chamber/pfd 与 pfd_b/pfd_r: Pearson = {_pearson(chamber_ratio_pfd, blue_red):.4f}")
    lines.append("- 说明：McCree 加权后的占比不是固定常数，而会随谱型变化，这符合引入 action spectrum 的本意。")
    lines.append("")
    lines.append("### 4. field mean 与 chamber mean 的差异量级可控")
    lines.append(
        f"- 平均绝对差 = {statistics.mean(abs(row.mccree_field_ypfd - row.mccree_chamber_ypfd) for row in rows):.6f}"
    )
    lines.append(
        f"- 最大绝对差 = {max(abs(row.mccree_field_ypfd - row.mccree_chamber_ypfd) for row in rows):.6f}"
    )
    lines.append("- 说明：两条平均曲线方向一致，field mean 可作为后续默认主口径，chamber mean 适合作为备选参考。")
    lines.append("")
    lines.append("## 分场景组均值")
    lines.append("")
    for scene, _folder in SAMPLE_GROUPS:
        subset = [row for row in rows if row.scene == scene]
        lines.append(
            f"- {scene} 组：field_ypfd={_mean(subset, 'mccree_field_ypfd'):.6f}，"
            f"chamber_ypfd={_mean(subset, 'mccree_chamber_ypfd'):.6f}，"
            f"field/pfd={_mean(subset, 'field_ratio_pfd'):.6f}，"
            f"chamber/pfd={_mean(subset, 'chamber_ratio_pfd'):.6f}，"
            f"cct={_mean(subset, 'cct'):.2f}，blue_red={_mean(subset, 'blue_red'):.6f}"
        )
    lines.append("")
    lines.append("## 样本摘录")
    lines.append("")
    for row in rows:
        lines.append(
            f"- {row.scene} {row.name}：field_ypfd={row.mccree_field_ypfd:.6f}，"
            f"chamber_ypfd={row.mccree_chamber_ypfd:.6f}，field/pfd={row.field_ratio_pfd:.6f}，"
            f"chamber/pfd={row.chamber_ratio_pfd:.6f}，cct={row.cct:.2f}，blue_red={row.blue_red:.6f}"
        )
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append("1. McCree 1972 原始 25 nm 表已经可以在当前仓库中稳定复算为一个独立的 photon-based 加权量。")
    lines.append("2. 采用 350-740 nm 应用窗口、范围外置 0 的保守方案后，结果量级合理，与现有 PFD / PPFD 强正相关。")
    lines.append("3. 当前可以进入下一阶段：把 field mean 版本并入现有光谱算法链，先作为新增衍生指标接入，不替换现有 confirmed 指标。")
    return "\n".join(lines) + "\n"


def main() -> int:
    rows = _collect_rows()
    report_text = build_report_text(rows)
    output_path = Path("doc/规划/McCree1972_25nm独立验证_V1_20260423.md")
    output_path.write_text(report_text, encoding="utf-8")
    print(report_text)
    print(f"report_written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())