#!/usr/bin/env python3
"""
三方对比验证：硬件算法 vs spectral_metrics_calc.c vs raw_spectral_process.py

从硬件读取原始光谱数据(701 points)，分别用三种方式计算光参数：
1. 硬件寄存器值 (hardware: 设备已有算法)
2. spectral_metrics_calc.c 的 Python float32 复现 (c_algo)
3. raw_spectral_process.py 的 Python float64 参考实现 (python_ref)

然后对比 hardware vs c_algo vs python_ref 之间的差异。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from par_device import PARDevice
from raw_spectral_process import (
    WAVELENGTHS,
    WAVELENGTH_START_NM,
    WAVELENGTH_END_NM,
    WAVELENGTH_COUNT,
    PLANCK_CONSTANT,
    LIGHT_SPEED,
    AVOGADRO_CONSTANT,
    LUMINOUS_EFFICACY as PY_LUMINOUS_EFFICACY,
    build_processing_result as python_ref_build,
    photopic_weighting as py_photopic_weighting,
    cie1931_x_bar as py_cie1931_x_bar,
    cie1931_z_bar as py_cie1931_z_bar,
    correlated_color_temperature as py_cct,
    illuminance_lux as py_lux,
    chlorophyll_weighted_irradiance as py_chl_weighted,
)

try:
    from pymodbus.client.serial import ModbusSerialClient
except Exception as exc:
    raise RuntimeError(f"pymodbus 导入失败: {exc}") from exc

try:
    from serial.tools import list_ports
except Exception:
    list_ports = None

# ──────────────────────────────────────────────────────────────────────
#  常量 (与 spectral_metrics_calc.c 保持一致)
# ──────────────────────────────────────────────────────────────────────

# 物理常量 float32
F32_PLANCK = np.float32(6.62607015e-34)
F32_LIGHT_SPEED = np.float32(299792458.0)
F32_AVOGADRO = np.float32(6.02214076e23)
F32_LUMINOUS_EFFICACY = np.float32(683.0)
F32_PHOTON_TO_UMOL = np.float32(1e6 / (6.62607015e-34 * 299792458.0 * 6.02214076e23))

# CCT 波段 (C code: 360-830nm per CIE 15:2018)
CCT_BAND_START = 360
CCT_BAND_END = 830

# Lux 波段 (C code: 380-780nm)
LX_BAND_START = 380
LX_BAND_END = 780

# ──────────────────────────────────────────────────────────────────────
#  叶绿素权重 Q15 (直接从 spectral_metrics_calc.c 复制)
# ──────────────────────────────────────────────────────────────────────
# Q15 = round(float_weight * 32768.0), 从 C 代码原样复制
CHL_A_WEIGHTS_Q15 = [
    20318,  21010,  21659,  22353,  23002,  23550,  24060,  24509,  24791,  24982,
    25117,  25165,  25093,  24956,  24777,  24603,  24487,  24431,  24493,  24713,
    25102,  25710,  26424,  27306,  28277,  29326,  30308,  31243,  32043,  32590,
    32795,  32625,  31997,  30916,  29387,  27494,  25230,  22752,  20240,  17807,
    15329,  13044,  10988,   9127,   7538,   6112,   4880,   3862,   3227,   2726,
     2257,   1866,   1548,   1303,   1096,    903,    787,    707,    656,    600,
      545,    526,    467,    403,    408,    416,    385,    350,    359,    375,
      400,    388,    371,    382,    377,    353,    365,    383,    409,    430,
      411,    405,    408,    429,    479,    495,    511,    544,    567,    577,
      582,    573,    608,    632,    622,    614,    616,    638,    663,    678,
      667,    658,    655,    635,    653,    662,    651,    663,    674,    710,
      709,    700,    723,    737,    724,    765,    802,    856,    889,    909,
      931,    975,   1039,   1053,   1064,   1091,   1140,   1161,   1190,   1211,
     1236,   1258,   1264,   1254,   1262,   1261,   1269,   1265,   1277,   1257,
     1232,   1236,   1214,   1201,   1188,   1187,   1198,   1178,   1166,   1206,
     1177,   1170,   1199,   1244,   1289,   1334,   1381,   1421,   1516,   1609,
     1699,   1776,   1841,   1942,   2029,   2151,   2247,   2336,   2441,   2511,
     2617,   2700,   2754,   2834,   2906,   2955,   2983,   3040,   3081,   3094,
     3133,   3134,   3124,   3105,   3060,   3001,   2942,   2899,   2867,   2808,
     2774,   2752,   2760,   2784,   2818,   2922,   3033,   3153,   3260,   3431,
     3613,   3790,   3963,   4134,   4312,   4482,   4691,   4859,   4981,   5095,
     5198,   5312,   5394,   5452,   5490,   5530,   5550,   5539,   5505,   5451,
     5394,   5329,   5214,   5081,   4956,   4827,   4670,   4476,   4347,   4218,
     4069,   3977,   3917,   3838,   3773,   3774,   3805,   3867,   3983,   4168,
     4364,   4591,   4916,   5317,   5813,   6411,   7093,   7936,   8950,  10082,
    11445,  12901,  14518,  16277,  18096,  20004,  21796,  23517,  25114,  26441,
    27466,  28104,  28348,  28157,  27519,  26528,  25131,  23459,  21606,  19657,
    17318,  15112,  13436,  11859,  10198,   8648,   7297,   6086,   5082,   4159,
     3415,   2790,   2313,   1953,   1579,   1290,   1074,    900,    759,    632,
      528,    470,    419,    376,    329,    255,    182,    171,    196,    190,
]

CHL_B_WEIGHTS_Q15 = [
     3300,   3380,   3423,   3492,   3585,   3691,   3798,   3924,   4024,   4140,
     4317,   4510,   4688,   4924,   5281,   5679,   6025,   6351,   6788,   7279,
     7806,   8383,   8932,   9477,  10001,  10526,  10983,  11398,  11775,  12110,
    12363,  12578,  12765,  12895,  12989,  13088,  13181,  13352,  13574,  13867,
    14311,  14880,  15599,  16495,  17512,  18762,  20304,  21954,  23316,  24644,
    26206,  27727,  29113,  30382,  31412,  32165,  32636,  32775,  32596,  32113,
    31331,  30272,  29005,  27570,  26109,  24547,  22854,  21151,  19493,  17835,
    16267,  14708,  13234,  11882,  10608,   9441,   8382,   7419,   6438,   5617,
     5021,   4499,   3975,   3500,   3112,   2766,   2471,   2214,   1968,   1771,
     1613,   1464,   1348,   1250,   1161,   1080,   1014,    956,    917,    888,
      850,    826,    807,    770,    771,    761,    728,    722,    715,    721,
      714,    693,    690,    693,    686,    703,    697,    690,    716,    717,
      725,    758,    794,    819,    825,    834,    869,    917,    955,    991,
     1012,   1050,   1093,   1114,   1146,   1168,   1190,   1215,   1257,   1273,
     1288,   1316,   1329,   1346,   1382,   1372,   1365,   1362,   1370,   1397,
     1387,   1368,   1390,   1411,   1404,   1412,   1425,   1430,   1458,   1487,
     1511,   1531,   1554,   1580,   1601,   1616,   1614,   1627,   1664,   1682,
     1694,   1694,   1678,   1691,   1720,   1741,   1777,   1815,   1839,   1873,
     1917,   1956,   2009,   2083,   2162,   2210,   2266,   2356,   2430,   2471,
     2519,   2562,   2604,   2623,   2628,   2657,   2663,   2645,   2615,   2608,
     2579,   2511,   2438,   2388,   2327,   2282,   2240,   2185,   2159,   2142,
     2135,   2129,   2121,   2122,   2122,   2133,   2138,   2125,   2121,   2131,
     2156,   2201,   2246,   2323,   2435,   2570,   2735,   2920,   3158,   3433,
     3758,   4145,   4608,   5127,   5711,   6358,   7017,   7727,   8522,   9370,
     9981,  10443,  10917,  11314,  11545,  11632,  11546,  11285,  10883,  10340,
     9718,   9003,   8226,   7432,   6673,   5903,   5199,   4583,   3992,   3469,
     3015,   2600,   2236,   1915,   1638,   1405,   1181,   1007,    870,    743,
      625,    527,    441,    399,    348,    273,    250,    219,    196,    165,
      140,    121,    104,     84,     60,     49,     38,     25,     31,     31,
       34,     16,      6,     16,      0,      0,      0,      0,      0,      0,
]


# ──────────────────────────────────────────────────────────────────────
#  C 算法 float32 复现类
# ──────────────────────────────────────────────────────────────────────

class SpectralMetricsCAlgo:
    """
    Python float32 复现 spectral_metrics_calc.c.
    所有中间计算用 double (C 代码的实际行为), 最终结果转 float32.
    """

    # ---- scale LUT: 10^-N for N=0..15 ----
    SCALE_LUT = [np.float32(10.0 ** (-n)) for n in range(16)]

    @staticmethod
    def _q15_to_float(q15: int) -> np.float32:
        """Convert Q15 (uint16) to float. 1/32768 = 3.0517578125e-5"""
        return np.float32(q15) * np.float32(3.0517578125e-5)

    @staticmethod
    def _reconstruct(raw_points: Sequence[int], spectral_coefficient: int) -> list[np.float32]:
        """
        将原始 uint16 光谱点转为 float32 W/m²/nm.
        等价于 C 的 get_scaled_value() 对所有点调用.
        """
        coeff_idx = spectral_coefficient & 0x0F
        scale = SpectralMetricsCAlgo.SCALE_LUT[coeff_idx]
        return [np.float32(p) * scale for p in raw_points]

    @staticmethod
    def _energy_sum(spectrum_f32: list[np.float32], lo_nm: int, hi_nm: int) -> np.float32:
        """能量积分: sum(S) over range (float64 中间累加)"""
        accum = 0.0  # double
        start = max(lo_nm, WAVELENGTH_START_NM)
        end = min(hi_nm, WAVELENGTH_END_NM)
        for nm in range(start, end + 1):
            accum += float(spectrum_f32[nm - WAVELENGTH_START_NM])
        return np.float32(accum)

    @staticmethod
    def _photon_integral(spectrum_f32: list[np.float32], lo_nm: int, hi_nm: int) -> np.float32:
        """光子积分: sum(S * lambda_m) * PHOTON_TO_UMOL (与 C 一致)"""
        accum = 0.0  # double
        start = max(lo_nm, WAVELENGTH_START_NM)
        end = min(hi_nm, WAVELENGTH_END_NM)
        for nm in range(start, end + 1):
            s = float(spectrum_f32[nm - WAVELENGTH_START_NM])
            lambda_m = float(nm) * 1e-9
            accum += s * lambda_m
        accum *= float(F32_PHOTON_TO_UMOL)
        return np.float32(accum)

    @staticmethod
    def _weighted_q15_sum(spectrum_f32: list[np.float32], lo_nm: int, hi_nm: int,
                          weights_q15: list[int]) -> np.float32:
        """Q15 加权和 (用于 Chl_A/B)"""
        accum = 0.0  # double
        for nm in range(lo_nm, hi_nm + 1):
            s = float(spectrum_f32[nm - WAVELENGTH_START_NM])
            w = float(SpectralMetricsCAlgo._q15_to_float(weights_q15[nm - lo_nm]))
            accum += s * w
        return np.float32(accum)

    # ---- 光度函数 (与 C 代码完全相同) ----

    @staticmethod
    def _photopic_weight(lambda_nm: float) -> float:
        """V(lambda) 双高斯近似"""
        offset1 = lambda_nm - 568.8
        offset2 = lambda_nm - 530.9
        if lambda_nm < 568.8:
            t1 = offset1 * 0.0213
        else:
            t1 = offset1 * 0.0247
        if lambda_nm < 530.9:
            t2 = offset2 * 0.0613
        else:
            t2 = offset2 * 0.0322
        return 0.821 * math.exp(-0.5 * t1 * t1) + 0.286 * math.exp(-0.5 * t2 * t2)

    @staticmethod
    def _cie1931_x_bar(lambda_nm: float) -> float:
        """x_bar 三高斯近似"""
        offset1 = lambda_nm - 442.0
        offset2 = lambda_nm - 599.8
        offset3 = lambda_nm - 501.1
        if lambda_nm < 442.0:
            t1 = offset1 * 0.0624
        else:
            t1 = offset1 * 0.0374
        if lambda_nm < 599.8:
            t2 = offset2 * 0.0264
        else:
            t2 = offset2 * 0.0323
        if lambda_nm < 501.1:
            t3 = offset3 * 0.0490
        else:
            t3 = offset3 * 0.0382
        return (0.362 * math.exp(-0.5 * t1 * t1)
                + 1.056 * math.exp(-0.5 * t2 * t2)
                - 0.065 * math.exp(-0.5 * t3 * t3))

    @staticmethod
    def _cie1931_z_bar(lambda_nm: float) -> float:
        """z_bar 双高斯近似"""
        offset1 = lambda_nm - 437.0
        offset2 = lambda_nm - 459.0
        if lambda_nm < 437.0:
            t1 = offset1 * 0.0845
        else:
            t1 = offset1 * 0.0278
        if lambda_nm < 459.0:
            t2 = offset2 * 0.0385
        else:
            t2 = offset2 * 0.0725
        return (1.217 * math.exp(-0.5 * t1 * t1)
                + 0.681 * math.exp(-0.5 * t2 * t2))

    # ---- 公开计算接口 ----

    @staticmethod
    def compute_peak(spectrum_f32: list[np.float32]) -> tuple[int, np.float32]:
        """峰值 400-700nm"""
        max_val = np.float32(-1.0)
        max_nm = WAVELENGTH_START_NM
        for nm in range(400, 701):
            s = spectrum_f32[nm - WAVELENGTH_START_NM]
            if s > max_val:
                max_val = s
                max_nm = nm
        return max_nm, max_val

    @staticmethod
    def compute_peak_ext(spectrum_f32: list[np.float32]) -> tuple[int, np.float32]:
        """扩展峰值 350-1050nm"""
        max_val = np.float32(-1.0)
        max_nm = WAVELENGTH_START_NM
        for nm in range(WAVELENGTH_START_NM, WAVELENGTH_END_NM + 1):
            s = spectrum_f32[nm - WAVELENGTH_START_NM]
            if s > max_val:
                max_val = s
                max_nm = nm
        return max_nm, max_val

    @classmethod
    def compute_all(cls, raw_points: Sequence[int],
                    spectral_coefficient: int) -> dict[str, Any]:
        """执行所有 C 算法计算, 返回结果字典"""
        spec = cls._reconstruct(raw_points, spectral_coefficient)

        # 峰值
        peak_cwl, peak_spectrum = cls.compute_peak(spec)
        e_peak_cwl, e_peak_spectrum = cls.compute_peak_ext(spec)

        # 能量积分
        wm2 = cls._energy_sum(spec, 350, 1050)
        par = cls._energy_sum(spec, 400, 700)
        e_par = cls._energy_sum(spec, 400, 750)

        # 光子积分 (base)
        ppfd = cls._photon_integral(spec, 400, 700)
        pfd = cls._photon_integral(spec, 350, 780)
        pfd_r = cls._photon_integral(spec, 600, 699)
        pfd_b = cls._photon_integral(spec, 400, 499)
        pfd_g = cls._photon_integral(spec, 500, 599)
        pfd_uv = cls._photon_integral(spec, 350, 399)
        pfd_fr = cls._photon_integral(spec, 700, 780)

        # 光子积分 (extended)
        e_ppfd = cls._photon_integral(spec, 400, 750)
        e_pfd = cls._photon_integral(spec, 350, 1050)
        e_pfd_fr = cls._photon_integral(spec, 700, 1050)

        # E_PFD_r/b/g/uv 与 base 一致
        e_pfd_r = pfd_r
        e_pfd_b = pfd_b
        e_pfd_g = pfd_g
        e_pfd_uv = pfd_uv

        # Lux: V(lambda) weighted over 380-780nm
        lux_accum = 0.0
        for nm in range(LX_BAND_START, LX_BAND_END + 1):
            s = float(spec[nm - WAVELENGTH_START_NM])
            v = cls._photopic_weight(float(nm))
            lux_accum += s * v
        lux = np.float32(lux_accum * float(F32_LUMINOUS_EFFICACY))

        # Chl_A/B: Q15 weighted 400-699nm
        chl_a = cls._weighted_q15_sum(spec, 400, 699, CHL_A_WEIGHTS_Q15)
        chl_b = cls._weighted_q15_sum(spec, 400, 699, CHL_B_WEIGHTS_Q15)

        # CCT: CIE 1931 XYZ + McCamy 360-830nm
        x_accum = 0.0
        y_accum = 0.0
        z_accum = 0.0
        for nm in range(CCT_BAND_START, CCT_BAND_END + 1):
            s = float(spec[nm - WAVELENGTH_START_NM])
            nm_f = float(nm)
            x_accum += s * cls._cie1931_x_bar(nm_f)
            y_accum += s * cls._photopic_weight(nm_f)
            z_accum += s * cls._cie1931_z_bar(nm_f)

        sum_xyz = x_accum + y_accum + z_accum
        if sum_xyz > 0.0:
            x = x_accum / sum_xyz
            y = y_accum / sum_xyz
            denom = 0.1858 - y
            if abs(denom) > 1e-12:
                n_val = (x - 0.3320) / denom
                cct = np.float32(449.0 * n_val ** 3 + 3525.0 * n_val ** 2 + 6823.3 * n_val + 5520.33)
            else:
                cct = np.float32(0.0)
        else:
            cct = np.float32(0.0)

        return {
            "peak_cwl": int(peak_cwl),
            "peak_spectrum": float(peak_spectrum),
            "par": float(par),
            "pfd": float(pfd),
            "ppfd": float(ppfd),
            "pfd_r": float(pfd_r),
            "pfd_b": float(pfd_b),
            "pfd_g": float(pfd_g),
            "pfd_uv": float(pfd_uv),
            "pfd_fr": float(pfd_fr),
            "chl_a_value": float(chl_a),
            "chl_b_value": float(chl_b),
            "E_peak_cwl": int(e_peak_cwl),
            "E_peak_spectrum": float(e_peak_spectrum),
            "E_par": float(e_par),
            "E_pfd": float(e_pfd),
            "E_ppfd": float(e_ppfd),
            "E_pfd_r": float(e_pfd_r),
            "E_pfd_b": float(e_pfd_b),
            "E_pfd_g": float(e_pfd_g),
            "E_pfd_uv": float(e_pfd_uv),
            "E_pfd_fr": float(e_pfd_fr),
            "cct": float(cct),
            "lux": float(lux),
            "WM2": float(wm2),
            # ee = wm2 (相同)
            "ee": float(wm2),
            # 光度参数无 CRI (C 代码不计算)
        }


# ──────────────────────────────────────────────────────────────────────
#  Python 参考实现 (raw_spectral_process.py) 封装
# ──────────────────────────────────────────────────────────────────────

def compute_python_ref(raw_points: Sequence[int],
                       spectral_coefficient: int) -> dict[str, Any]:
    """
    调用 raw_spectral_process.py 的 build_processing_result 计算.
    注意: 该函数使用 float64 精度.
    """
    result = python_ref_build(raw_points, spectral_coefficient)
    # ee 由 build_processing_result 作为独立指标, 与 wm2 相同
    metrics = dict(result.metrics)
    return metrics


# ──────────────────────────────────────────────────────────────────────
#  硬件读取封装 (复用 光算法验证.py 的逻辑)
# ──────────────────────────────────────────────────────────────────────

TARGET_DEVICE_NAME = "Silicon Labs CP210x USB to UART Bridge"
PREFERRED_PORT = "COM4"
BAUDRATE = 115200
PARITY = "N"
STOPBITS = 1
BYTESIZE = 8
TIMEOUT = 3
SLAVE_ID = 1

REPORT_DIR = Path(__file__).resolve().parent / "data_history" / "PAR" / "Validation"


def _find_target_port(explicit_port: str, preferred_port: str,
                      target_device_name: str) -> str:
    if explicit_port:
        return explicit_port
    if not list_ports:
        raise RuntimeError("serial.tools.list_ports 不可用，且未显式提供 --port")
    if preferred_port:
        for port in list_ports.comports():
            if port.device.upper() == preferred_port.upper():
                return port.device
    for port in list_ports.comports():
        description = port.description or ""
        if target_device_name in description:
            return port.device
    raise RuntimeError(f"未找到目标设备串口: {target_device_name}")


def _await_stop_status(device: PARDevice, expected: int,
                       timeout_sec: float = 10.0) -> None:
    import time
    started = time.time()
    while time.time() - started < timeout_sec:
        status_obj = device.get_status_blocking(timeout=3)
        if int(status_obj.stop_status_to_user) == int(expected):
            return
        time.sleep(0.15)
    raise RuntimeError(f"等待 stop_status_to_user={expected} 超时")


def _set_stop(device: PARDevice, stop_value: int) -> None:
    future = device.set_stop(stop_value)
    if hasattr(future, "result"):
        future.result(timeout=2)


def capture_hardware_snapshot(device: PARDevice) -> dict[str, Any]:
    """从硬件读取一帧数据: 原始光谱 + 硬件计算值"""
    _set_stop(device, 1)
    _await_stop_status(device, 1)
    try:
        status_obj = device.get_status_blocking(timeout=5)
        spectral_obj = device.get_spectral_header_blocking(timeout=8)
        waves = device.get_wavelength_points_blocking(timeout=8)
        photometric = device.get_photometric_params_blocking(timeout=8)
        spectral_obj.wavelength_points_spectral_data = list(waves)
        spectral_obj.photometric_params = list(photometric)
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "spectral_data": {
                k: v for k, v in {
                    "spectral_coefficient": spectral_obj.spectral_coefficient,
                    "wavelength_points_spectral_data": list(waves),
                    "photometric_params": list(photometric),
                    "peak_cwl": spectral_obj.peak_cwl,
                    "peak_spectrum": spectral_obj.peak_spectrum,
                    "par": spectral_obj.par,
                    "pfd": spectral_obj.pfd,
                    "ppfd": spectral_obj.ppfd,
                    "pfd_r": spectral_obj.pfd_r,
                    "pfd_b": spectral_obj.pfd_b,
                    "pfd_g": spectral_obj.pfd_g,
                    "pfd_uv": spectral_obj.pfd_uv,
                    "pfd_fr": spectral_obj.pfd_fr,
                    "chl_a_value": spectral_obj.chl_a_value,
                    "chl_b_value": spectral_obj.chl_b_value,
                    "E_peak_cwl": spectral_obj.E_peak_cwl,
                    "E_peak_spectrum": spectral_obj.E_peak_spectrum,
                    "E_par": spectral_obj.E_par,
                    "E_pfd": spectral_obj.E_pfd,
                    "E_ppfd": spectral_obj.E_ppfd,
                    "E_pfd_r": spectral_obj.E_pfd_r,
                    "E_pfd_b": spectral_obj.E_pfd_b,
                    "E_pfd_g": spectral_obj.E_pfd_g,
                    "E_pfd_uv": spectral_obj.E_pfd_uv,
                    "E_pfd_fr": spectral_obj.E_pfd_fr,
                    "cct": spectral_obj.cct,
                    "lux": spectral_obj.lux,
                    "WM2": spectral_obj.WM2,
                    "Measurement_Certainty": spectral_obj.Measurement_Certainty,
                }.items()
            },
        }
        return snapshot
    finally:
        try:
            _set_stop(device, 0)
            _await_stop_status(device, 0, timeout_sec=5.0)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────
#  三方比较数据结构
# ──────────────────────────────────────────────────────────────────────

# 要比较的指标
COMPARISON_METRICS = [
    "peak_cwl", "peak_spectrum",
    "E_peak_cwl", "E_peak_spectrum",
    "par", "E_par",
    "WM2", "ee",
    "ppfd", "pfd",
    "pfd_r", "pfd_b", "pfd_g", "pfd_uv", "pfd_fr",
    "E_ppfd", "E_pfd",
    "E_pfd_r", "E_pfd_b", "E_pfd_g", "E_pfd_uv", "E_pfd_fr",
    "cct", "lux",
    "chl_a_value", "chl_b_value",
]


@dataclass
class ThreeWayComparison:
    name: str
    hardware: float | None
    c_algo: float | None
    python_ref: float | None
    hw_vs_c_diff: float | None       # hardware - c_algo
    hw_vs_c_rel: float | None        # |hw - c_algo| / max(|hw|, 1)
    c_vs_py_diff: float | None       # c_algo - python_ref
    c_vs_py_rel: float | None        # |c_algo - python_ref| / max(|c_algo|, 1)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _rel_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    denom = max(abs(a), 1.0)
    return abs(b - a) / denom * 100.0


def compare_three_way(hw_metrics: dict[str, Any],
                      c_algo_metrics: dict[str, Any],
                      py_ref_metrics: dict[str, Any]) -> list[ThreeWayComparison]:
    comparisons: list[ThreeWayComparison] = []
    for name in COMPARISON_METRICS:
        hw = _safe_float(hw_metrics.get(name))
        ca = _safe_float(c_algo_metrics.get(name))
        pr = _safe_float(py_ref_metrics.get(name))

        hw_vs_c = None if hw is None or ca is None else (ca - hw)
        c_vs_py = None if ca is None or pr is None else (pr - ca)

        comparisons.append(ThreeWayComparison(
            name=name,
            hardware=hw,
            c_algo=ca,
            python_ref=pr,
            hw_vs_c_diff=hw_vs_c,
            hw_vs_c_rel=_rel_diff(hw, ca),
            c_vs_py_diff=c_vs_py,
            c_vs_py_rel=_rel_diff(ca, pr),
        ))
    return comparisons


# ──────────────────────────────────────────────────────────────────────
#  格式化与输出
# ──────────────────────────────────────────────────────────────────────

def _fmt(v: float | None, digits: int = 6) -> str:
    if v is None:
        return "-"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{digits}f}".rstrip("0").rstrip(".")


def print_comparison(captures: list[tuple[dict[str, Any],
                                           dict[str, Any],
                                           dict[str, Any],
                                           list[ThreeWayComparison]]]) -> None:
    for idx, (hw, ca, pr, comps) in enumerate(captures, 1):
        coef = hw.get("spectral_data", {}).get("spectral_coefficient", "?")
        ts = hw.get("timestamp", "?")

        print(f"\n{'='*100}")
        print(f"=== Capture #{idx}  timestamp={ts}  coeff={coef}")
        print(f"{'='*100}")
        print(f"{'metric':<24} {'hardware':>14} {'c_algo':>14} {'py_ref':>14} "
              f"{'hw-c_diff':>12} {'hw-c_rel%':>9} {'c-py_diff':>12} {'c-py_rel%':>9}")

        for comp in comps:
            print(f"{comp.name:<24} "
                  f"{_fmt(comp.hardware):>14} "
                  f"{_fmt(comp.c_algo):>14} "
                  f"{_fmt(comp.python_ref):>14} "
                  f"{_fmt(comp.hw_vs_c_diff):>12} "
                  f"{_fmt(comp.hw_vs_c_rel, 3):>9} "
                  f"{_fmt(comp.c_vs_py_diff):>12} "
                  f"{_fmt(comp.c_vs_py_rel, 3):>9}")


def save_report(captures: list[tuple[dict[str, Any],
                                      dict[str, Any],
                                      dict[str, Any],
                                      list[ThreeWayComparison]]],
                output_dir: Path, port: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"three_way_validation_{port}_{ts}.json"

    payload = {
        "timestamp": datetime.now().isoformat(),
        "port": port,
        "capture_count": len(captures),
        "captures": [],
    }
    for idx, (hw, ca, pr, comps) in enumerate(captures):
        payload["captures"].append({
            "index": idx + 1,
            "snapshot_timestamp": hw.get("timestamp"),
            "snapshot": hw,  # 包含原始 snapshot (含 spectral_data + wavelength_points)
            "spectral_coefficient": hw.get("spectral_data", {}).get("spectral_coefficient"),
            "hardware_metrics": {m.name: m.hardware for m in comps},
            "c_algo_metrics": {m.name: m.c_algo for m in comps},
            "python_ref_metrics": {m.name: m.python_ref for m in comps},
            "comparisons": [
                {
                    "name": m.name,
                    "hw_vs_c_diff": m.hw_vs_c_diff,
                    "hw_vs_c_rel_pct": m.hw_vs_c_rel,
                    "c_vs_py_diff": m.c_vs_py_diff,
                    "c_vs_py_rel_pct": m.c_vs_py_rel,
                }
                for m in comps
            ],
        })

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ──────────────────────────────────────────────────────────────────────
#  主流程
# ──────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="三方验证: 硬件 vs spectral_metrics_calc.c vs raw_spectral_process.py"
    )
    parser.add_argument("--port", default="",
                        help="串口名，留空自动匹配")
    parser.add_argument("--device-name", default=TARGET_DEVICE_NAME)
    parser.add_argument("--preferred-port", default=PREFERRED_PORT)
    parser.add_argument("--baudrate", type=int, default=BAUDRATE)
    parser.add_argument("--parity", default=PARITY)
    parser.add_argument("--stopbits", type=float, default=STOPBITS)
    parser.add_argument("--bytesize", type=int, default=BYTESIZE)
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument("--slave-id", type=int, default=SLAVE_ID)
    parser.add_argument("--count", type=int, default=3,
                        help="采集次数 (不同光照强度)")
    parser.add_argument("--interval", type=float, default=30.0,
                        help="每次采集之间的等待秒数 (让光照变化)")
    parser.add_argument("--output-dir", default=str(REPORT_DIR),
                        help="报告输出目录")
    parser.add_argument("--no-save", action="store_true",
                        help="只打印结果，不写 JSON 报告")
    parser.add_argument("--validate-from-file", default="",
                        help="从已保存的 JSON 文件验证, 不连接硬件")
    return parser.parse_args()


def validate_from_file(filepath: str) -> None:
    """从已有 JSON 文件加载数据, 仅比较 C algo vs Python ref"""
    payload = json.loads(Path(filepath).read_text(encoding="utf-8"))
    snapshots = []
    if "captures" in payload:
        for cap in payload["captures"]:
            snapshots.append(cap["snapshot"])
    elif "spectral_data" in payload:
        snapshots.append(payload)

    for snap in snapshots:
        sd = snap.get("spectral_data", snap)
        raw = sd.get("wavelength_points_spectral_data")
        coef = sd.get("spectral_coefficient")
        if not raw or coef is None:
            print(f"[SKIP] missing spectral data")
            continue

        hw_metrics = {m: _safe_float(sd.get(m)) for m in COMPARISON_METRICS}
        ca_metrics = SpectralMetricsCAlgo.compute_all(raw, int(coef))
        py_metrics = compute_python_ref(raw, int(coef))
        comps = compare_three_way(hw_metrics, ca_metrics, py_metrics)
        print_comparison([(
            {"timestamp": snap.get("timestamp", "?"),
             "spectral_data": sd},
            ca_metrics, py_metrics, comps
        )])


def run_validation(args: argparse.Namespace) -> None:
    port = _find_target_port(args.port, args.preferred_port, args.device_name)
    client = ModbusSerialClient(
        port=port,
        baudrate=args.baudrate,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
        timeout=args.timeout,
    )
    if not client.connect():
        raise RuntimeError(f"串口打开失败: {port}")
    device = PARDevice(client, unit=args.slave_id, prefer_direct=True)

    captures: list[tuple[dict[str, Any],
                          dict[str, Any],
                          dict[str, Any],
                          list[ThreeWayComparison]]] = []

    try:
        for idx in range(1, args.count + 1):
            print(f"\n[{idx}/{args.count}] 采集硬件数据...")
            snapshot = capture_hardware_snapshot(device)
            sd = snapshot["spectral_data"]
            raw = sd.get("wavelength_points_spectral_data")
            coef = sd.get("spectral_coefficient")
            if not raw or coef is None:
                print(f"[WARN] 采集 {idx} 缺少光谱数据，跳过")
                continue

            # 提取硬件指标
            hw_metrics = {m: _safe_float(sd.get(m)) for m in COMPARISON_METRICS}

            # C 算法 float32 计算
            ca_metrics = SpectralMetricsCAlgo.compute_all(raw, int(coef))

            # Python 参考 float64 计算
            py_metrics = compute_python_ref(raw, int(coef))

            # 三方对比
            comps = compare_three_way(hw_metrics, ca_metrics, py_metrics)
            captures.append((snapshot, ca_metrics, py_metrics, comps))

            if idx < args.count:
                print(f"等待 {args.interval} 秒让光照变化...")
                time.sleep(args.interval)

    finally:
        try:
            client.close()
        except Exception:
            pass

    if not captures:
        print("没有有效采集数据")
        return

    # 打印报告
    print_comparison(captures)

    # 汇总
    print(f"\n{'='*100}")
    print("=== 汇总统计 ===")
    print(f"{'metric':<24} {'samples':>8} {'hw-vs-c_max_abs':>16} {'hw-vs-c_max_rel%':>16} "
          f"{'c-vs-py_max_abs':>16} {'c-vs-py_max_rel%':>16}")

    metric_groups: dict[str, list[ThreeWayComparison]] = {}
    for _, _, _, comps in captures:
        for comp in comps:
            metric_groups.setdefault(comp.name, []).append(comp)

    for name in COMPARISON_METRICS:
        rows = metric_groups.get(name, [])
        if not rows:
            continue
        hwc_diffs = [r.hw_vs_c_diff for r in rows if r.hw_vs_c_diff is not None]
        hwc_rels = [r.hw_vs_c_rel for r in rows if r.hw_vs_c_rel is not None]
        cpy_diffs = [r.c_vs_py_diff for r in rows if r.c_vs_py_diff is not None]
        cpy_rels = [r.c_vs_py_rel for r in rows if r.c_vs_py_rel is not None]
        print(f"{name:<24} {len(rows):>8} "
              f"{_fmt(max(hwc_diffs) if hwc_diffs else None):>16} "
              f"{_fmt(max(hwc_rels) if hwc_rels else None, 3):>16} "
              f"{_fmt(max(cpy_diffs) if cpy_diffs else None):>16} "
              f"{_fmt(max(cpy_rels) if cpy_rels else None, 3):>16}")

    # 保存报告
    if not args.no_save:
        report_path = save_report(captures, Path(args.output_dir),
                                  port.replace(":", "_"))
        print(f"\n报告已保存: {report_path}")


def main() -> int:
    args = _parse_args()
    if args.validate_from_file:
        validate_from_file(args.validate_from_file)
        return 0
    try:
        run_validation(args)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
