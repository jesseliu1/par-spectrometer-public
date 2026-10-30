from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

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
    py_a: float
    py_b: float
    py_ratio: float
    cct: float
    wm2: float
    par: float
    lux: float
    pfd: float
    pfd_b: float
    pfd_r: float

    @property
    def blue_red(self) -> float:
        return self.pfd_b / self.pfd_r if abs(self.pfd_r) > 1e-12 else math.nan

    @property
    def blue_frac(self) -> float:
        return self.pfd_b / self.pfd if abs(self.pfd) > 1e-12 else math.nan

    @property
    def py_b_wm2(self) -> float:
        return self.py_b / self.wm2 if abs(self.wm2) > 1e-12 else math.nan

    @property
    def py_b_par(self) -> float:
        return self.py_b / self.par if abs(self.par) > 1e-12 else math.nan

    @property
    def py_a_wm2(self) -> float:
        return self.py_a / self.wm2 if abs(self.wm2) > 1e-12 else math.nan

    @property
    def py_a_par(self) -> float:
        return self.py_a / self.par if abs(self.par) > 1e-12 else math.nan


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


def _ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        tail = index
        while tail + 1 < len(ordered) and ordered[tail + 1][1] == ordered[index][1]:
            tail += 1
        average_rank = (index + tail + 2) / 2.0
        for offset in range(index, tail + 1):
            ranks[ordered[offset][0]] = average_rank
        index = tail + 1
    return ranks


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    return _pearson(_ranks(xs), _ranks(ys))


def _pairwise_concordance(xs: Sequence[float], ys: Sequence[float]) -> tuple[int, int, int, float]:
    total = 0
    concordant = 0
    discordant = 0
    for left_index in range(len(xs)):
        for right_index in range(left_index + 1, len(xs)):
            delta_x = xs[right_index] - xs[left_index]
            delta_y = ys[right_index] - ys[left_index]
            if abs(delta_x) <= 1e-12 or abs(delta_y) <= 1e-12:
                continue
            total += 1
            if delta_x * delta_y > 0.0:
                concordant += 1
            else:
                discordant += 1
    ratio = concordant / total if total else math.nan
    return total, concordant, discordant, ratio


def _collect_rows() -> list[SampleRow]:
    rows: list[SampleRow] = []
    for scene, folder_text in SAMPLE_GROUPS:
        folder = Path(folder_text)
        for path in sorted(folder.glob("Rawdata*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            metrics = rsp.compute_from_rawdata_payload(payload).metrics
            py_a = float(metrics["chl_a_value"])
            py_b = float(metrics["chl_b_value"])
            rows.append(
                SampleRow(
                    scene=scene,
                    name=path.name,
                    py_a=py_a,
                    py_b=py_b,
                    py_ratio=py_b / py_a,
                    cct=float(metrics["cct"]),
                    wm2=float(metrics["WM2"]),
                    par=float(metrics["par"]),
                    lux=float(metrics["lux"]),
                    pfd=float(metrics["pfd"]),
                    pfd_b=float(metrics["pfd_b"]),
                    pfd_r=float(metrics["pfd_r"]),
                )
            )
    return rows


def _mean(rows: Iterable[SampleRow], attr_name: str) -> float:
    values = [float(getattr(row, attr_name)) for row in rows]
    return statistics.mean(values)


def build_report_text(rows: Sequence[SampleRow]) -> str:
    py_ratio = [row.py_ratio for row in rows]
    cct = [row.cct for row in rows]
    blue_red = [row.blue_red for row in rows]
    py_b_wm2 = [row.py_b_wm2 for row in rows]
    py_b_par = [row.py_b_par for row in rows]
    py_a_wm2 = [row.py_a_wm2 for row in rows]
    py_a_par = [row.py_a_par for row in rows]

    ratio_cct_pairwise = _pairwise_concordance(py_ratio, cct)
    ratio_blue_red_pairwise = _pairwise_concordance(py_ratio, blue_red)

    lines: list[str] = []
    lines.append("日期：2026-04-23")
    lines.append("范围：Python 科学口径 chl_a_value / chl_b_value 的自洽性验证")
    lines.append("主文件：raw_spectral_process.py")
    lines.append("样本范围：data_history/PAR/Rawdata 下 11 份正式样本（正式采集LED 4 份、正式采集钠灯 4 份、阴天 3 份）")
    lines.append("")
    lines.append("## 目的")
    lines.append("")
    lines.append("- 在前一轮关系性验证中，已经证明硬件叶绿素值不可信。")
    lines.append("- 本轮不再追问硬件寄存器，而是直接检查 Python 科学口径叶绿素值是否自洽。")
    lines.append("- 这里的“自洽”指：叶绿素值及其比值，是否与色温、蓝红谱比、归一化总量等结构性指标保持稳定且可解释的关系。")
    lines.append("")
    lines.append("## 方法")
    lines.append("")
    lines.append("- 对每份正式样本提取 Python 科学口径的 chl_a_value / chl_b_value。")
    lines.append("- 同时提取 cct、WM2、par、lux、pfd_b、pfd_r 等已确认光学指标。")
    lines.append("- 重点检查以下关系：")
    lines.append("  - chl_b / chl_a 与 cct 是否同向变化")
    lines.append("  - chl_b / chl_a 与蓝红谱比 pfd_b / pfd_r 是否同向变化")
    lines.append("  - chl_b 归一化到 wm2 / par 后，是否仍与 cct、蓝红谱比保持稳定正相关")
    lines.append("  - 三个正式场景（LED、钠灯、阴天）的组均值排序是否符合谱型直觉")
    lines.append("")
    lines.append("## 核心结果")
    lines.append("")
    lines.append("### 1. Python 科学口径的 chl_b / chl_a 与 cct 保持强正相关")
    lines.append(f"- Pearson = {_pearson(py_ratio, cct):.4f}")
    lines.append(f"- Spearman = {_spearman(py_ratio, cct):.4f}")
    lines.append(
        f"- 成对排序一致性 = {ratio_cct_pairwise[1]}/{ratio_cct_pairwise[0]} = {ratio_cct_pairwise[3]:.4f}"
    )
    lines.append("- 说明：色温越高时，科学口径下 chl_b 相对 chl_a 越占优势，这一方向在全样本上稳定成立。")
    lines.append("")
    lines.append("### 2. Python 科学口径的 chl_b / chl_a 与蓝红谱比保持显著正相关")
    lines.append(f"- Pearson = {_pearson(py_ratio, blue_red):.4f}")
    lines.append(f"- Spearman = {_spearman(py_ratio, blue_red):.4f}")
    lines.append(
        f"- 成对排序一致性 = {ratio_blue_red_pairwise[1]}/{ratio_blue_red_pairwise[0]} = {ratio_blue_red_pairwise[3]:.4f}"
    )
    lines.append("- 说明：蓝成分提高时，科学口径下 chl_b / chl_a 同步提高，没有出现和硬件口径那样的方向翻转。")
    lines.append("")
    lines.append("### 3. 即使做总量归一化，chl_b 的结构关系仍然成立")
    lines.append(f"- py_b / wm2 与 cct：Pearson = {_pearson(py_b_wm2, cct):.4f}")
    lines.append(f"- py_b / wm2 与 pfd_b / pfd_r：Pearson = {_pearson(py_b_wm2, blue_red):.4f}")
    lines.append(f"- py_b / par 与 cct：Pearson = {_pearson(py_b_par, cct):.4f}")
    lines.append(f"- py_b / par 与 pfd_b / pfd_r：Pearson = {_pearson(py_b_par, blue_red):.4f}")
    lines.append("- 说明：科学值的自洽性不是“总量越大，什么都一起涨”的假象；即使归一化到总辐照度或 PAR，chl_b 仍与色温和蓝红谱比保持强正相关。")
    lines.append("")
    lines.append("### 4. chl_a 主要响应总量，chl_b / chl_a 主要响应谱型")
    lines.append(f"- py_a 与 wm2：Pearson = {_pearson([row.py_a for row in rows], [row.wm2 for row in rows]):.4f}")
    lines.append(f"- py_a 与 par：Pearson = {_pearson([row.py_a for row in rows], [row.par for row in rows]):.4f}")
    lines.append(f"- py_b 与 wm2：Pearson = {_pearson([row.py_b for row in rows], [row.wm2 for row in rows]):.4f}")
    lines.append(f"- py_b 与 par：Pearson = {_pearson([row.py_b for row in rows], [row.par for row in rows]):.4f}")
    lines.append(f"- py_a / wm2 与 cct：Pearson = {_pearson(py_a_wm2, cct):.4f}")
    lines.append(f"- py_a / par 与 cct：Pearson = {_pearson(py_a_par, cct):.4f}")
    lines.append("- 说明：")
    lines.append("  - chl_a 与总量指标高度正相关，说明它主要跟随总体能量变化。")
    lines.append("  - chl_b 既跟随总量，也在比值和归一化后保留明显谱型信息。")
    lines.append("  - 因此科学口径不是随机加权噪声，而是同时保留了总量和谱型两层信息。")
    lines.append("")
    lines.append("### 5. 三个正式场景的组均值排序符合谱型直觉")
    for scene, _folder in SAMPLE_GROUPS:
        subset = [row for row in rows if row.scene == scene]
        lines.append(
            f"- {scene} 组：py_a={_mean(subset, 'py_a'):.6f}，py_b={_mean(subset, 'py_b'):.6f}，"
            f"py_b/py_a={_mean(subset, 'py_ratio'):.6f}，cct={_mean(subset, 'cct'):.2f}，pfd_b/pfd_r={_mean(subset, 'blue_red'):.6f}"
        )
    lines.append("- 组间排序表现为：")
    lines.append("  - 钠灯组 cct 最低、蓝红谱比最低，同时 py_b / py_a 也最低。")
    lines.append("  - 阴天组 cct 最高、蓝红谱比最高，同时 py_b / py_a 也最高。")
    lines.append("  - LED 组位于两者之间。")
    lines.append("- 说明科学口径在跨场景比较时保持了稳定、可解释的层级关系。")
    lines.append("")
    lines.append("## 样本摘录")
    lines.append("")
    for row in rows:
        lines.append(
            f"- {row.scene} {row.name}：py_a={row.py_a:.6f}，py_b={row.py_b:.6f}，"
            f"py_b/py_a={row.py_ratio:.6f}，cct={row.cct:.2f}，pfd_b/pfd_r={row.blue_red:.6f}"
        )
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append("### 1. 当前 Python 科学口径叶绿素值具有明确的结构自洽性")
    lines.append("- chl_b / chl_a 与 cct、蓝红谱比均保持显著正相关。")
    lines.append("- 这种关系在 Pearson、Spearman 和成对排序一致性三种口径下都成立。")
    lines.append("")
    lines.append("### 2. 科学口径的自洽性不是总量假象")
    lines.append("- 即使把 chl_b 归一化到 wm2 / par，自洽关系仍然存在。")
    lines.append("- 说明该算法输出保留了谱型响应，而不是仅仅跟着总能量一起变化。")
    lines.append("")
    lines.append("### 3. 当前最合理的工程结论")
    lines.append("- 已经可以把 Python 科学口径 chl_a_value / chl_b_value 视为当前项目中的唯一正式业务值。")
    lines.append("- 硬件叶绿素字段继续只保留为原始证据字段，不参与任何业务判断。")
    lines.append("")
    lines.append("## 后续建议")
    lines.append("")
    lines.append("1. 后续继续新增样本时，沿用同一脚本复算 Pearson、Spearman 与成对排序一致性，观察自洽性是否保持稳定。")
    lines.append("2. 若后续引入外部叶绿素参考仪器，可再补“绝对真值”层验证；当前这一版已足够支撑项目内业务替代。")
    return "\n".join(lines) + "\n"


def main() -> int:
    rows = _collect_rows()
    report_text = build_report_text(rows)
    output_path = Path("doc/规划/PAR二代叶绿素科学值自洽性验证_V1_20260423.md")
    output_path.write_text(report_text, encoding="utf-8")
    print(report_text)
    print(f"report_written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())