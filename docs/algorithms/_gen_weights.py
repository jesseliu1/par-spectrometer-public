#!/usr/bin/env python3
"""Generate C weight arrays for MCU spectral metrics library"""
import os, sys, math

# ----- chlorophyll_weights -----
sys.path.insert(0, os.path.dirname(__file__))
from chlorophyll_weights import (
    CHLOROPHYLL_WEIGHTED_IRRADIANCE_A,
    CHLOROPHYLL_WEIGHTED_IRRADIANCE_B,
    CHLOROPHYLL_WEIGHT_WAVELENGTH_START_NM,
    CHLOROPHYLL_WEIGHT_WAVELENGTH_END_NM,
)
from mccree1972_weights import (
    MCCREE_RAW_WAVELENGTHS_NM,
    MCCREE_FIELD_MEAN_RAW,
    MCCREE_CHAMBER_MEAN_RAW,
)

# Accumulation mode constants (must match C #defines)
ACCUM_MODE_SUM = 0
ACCUM_MODE_SUM_DIV10 = 1
ACCUM_MODE_PHOTON = 2

DECO = " * ================================================================="
DECO_OPEN  = "/* ================================================================="
DECO_CLOSE = DECO + " */"

def fmt_header(title, desc=""):
    lines = [
        "#ifndef SPECTRAL_METRICS_CALC_H",
        "#define SPECTRAL_METRICS_CALC_H",
        "",
        "/**",
        " * @file spectral_metrics_calc.h",
        f" * @brief {title}",
        " *",
        " * Target: ATSAML11E16A (Cortex-M23, 32MHz, no FPU)",
        " * Language: C99",
        " *",
        " * Usage:",
        " *   // 1. Include this header AFTER PARAPP.h (or whichever header defines",
        " *   //    spectral_data_t and the spectral_data global)",
        " *   // 2. Call individual calc functions or use spectral_calc_all()",
        " *",
        " *   // Single function:",
        " *   calc_status_t s = spectral_calc_PAR();",
        " *   if (s == CALC_COMPLETED) { /* use spectral_data.par */ }",
        " *",
        " *   // All functions:",
        " *   while (spectral_calc_all() != CALC_COMPLETED) { /* yield */ }",
        " *   spectral_calc_all_reset();",
        " */",
        "",
        "/* =================================================================",
        " *  IMPORTANT: spectral_data_t, exposure_status_t, and the global",
        " *  'spectral_data' are defined in PARAPP.h (the project header).",
        " *  This header ONLY adds calc_status_t, spectral constants, and",
        " *  the public API declarations.",
        " *",
        " *  Include order in your .c file:",
        " *    #include \"definitions.h\"   (or whatever provides stdint, etc.)",
        " *    #include \"PARAPP.h\"         (spectral_data_t + extern global)",
        " *    #include \"spectral_metrics_calc.h\"",
        " * ================================================================= */",
        "",
        "#include <stdint.h>",
        "#include <stdbool.h>",
        "",
        "/* PARAPP.h provides spectral_data_t, exposure_status_t, and extern spectral_data global */",
        "#include \"PARAPP.h\"",
        "",
        "/* ===== Spectral constants (must match PARAPP.h :: MAX_WAVELENGTH_POINTS = 701) ===== */",
        "#define SPECTRAL_WAVELENGTH_START_NM  350",
        "#define SPECTRAL_WAVELENGTH_END_NM    1050",
        "#define SPECTRAL_WAVELENGTH_COUNT     (SPECTRAL_WAVELENGTH_END_NM - SPECTRAL_WAVELENGTH_START_NM + 1)  /* 701 */",
        "",
        "/* ===== Calculation status ===== */",
        "typedef enum {",
        "    CALC_COMPLETED      = 0,   /* 计算完成 */",
        "    CALC_NOT_COMPLETED  = 1,   /* 计算仍在进行中 (分步计算, 需再次调用) */",
        "    CALC_ERROR          = 2,   /* 计算出错 */",
        "} calc_status_t;",
        "",
        "/* =================================================================",
        " *  Public API",
        " * =================================================================",
        "",
        "/* --- Peak --- */",
        "calc_status_t spectral_calc_peak(void);      /* peak_cwl + peak_spectrum (400-700nm) */",
        "calc_status_t spectral_calc_peak_ext(void);  /* E_peak_cwl + E_peak_spectrum (350-1050nm) */",
        "",
        "/* --- Energy integral (W/m2) --- */",
        "calc_status_t spectral_calc_WM2(void);       /* WM2: 350-1050nm */",
        "calc_status_t spectral_calc_PAR(void);       /* PAR: 400-700nm, /10 */",
        "calc_status_t spectral_calc_E_PAR(void);     /* E_PAR: 400-750nm, /10 */",
        "",
        "/* --- Photon integral (umol/m2/s) --- */",
        "calc_status_t spectral_calc_PPFD(void);      /* PPFD: 400-700nm */",
        "calc_status_t spectral_calc_PFD(void);       /* PFD: 350-780nm */",
        "calc_status_t spectral_calc_PFD_r(void);     /* PFD_R: 600-699nm */",
        "calc_status_t spectral_calc_PFD_b(void);     /* PFD_B: 400-499nm */",
        "calc_status_t spectral_calc_PFD_g(void);     /* PFD_G: 500-599nm */",
        "calc_status_t spectral_calc_PFD_uv(void);    /* PFD_UV: 350-400nm */",
        "calc_status_t spectral_calc_PFD_fr(void);    /* PFD_FR: 700-780nm */",
        "",
        "/* --- Photon integral (extended range) --- */",
        "calc_status_t spectral_calc_E_PPFD(void);    /* E_PPFD: 400-750nm */",
        "calc_status_t spectral_calc_E_PFD(void);     /* E_PFD: 350-1050nm */",
        "calc_status_t spectral_calc_E_PFD_fr(void);  /* E_PFD_FR: 700-1050nm */",
        "",
        "/* --- Weighted integrals --- */",
        "calc_status_t spectral_calc_lux(void);       /* Lux: V(lambda) weighted */",
        "calc_status_t spectral_calc_Chl_A(void);     /* Chl_A: 400-699nm weighted */",
        "calc_status_t spectral_calc_Chl_B(void);     /* Chl_B: 400-699nm weighted */",
        "calc_status_t spectral_calc_McCree_Y(void);  /* McCree Y_PFD: 350-740nm */",
        "calc_status_t spectral_calc_CCT(void);        /* CCT: CIE 1931 XYZ + McCamy, 350-1050nm */",
        "",
        "/* --- Bulk scheduler --- */",
        "calc_status_t spectral_calc_all(void);       /* 分步执行所有计算, 全完成返回CALC_COMPLETED */",
        "void spectral_calc_all_reset(void);           /* 重置调度器状态, 准备新数据 */",
        "",
        "#endif /* SPECTRAL_METRICS_CALC_H */",
    ]
    return "\n".join(lines)

# ---- CIE 1931 tristimulus LUT generators (Python reference, double precision) ----
def _cie1931_x_bar_py(nm):
    t1 = (nm - 442.0) * (0.0624 if nm < 442.0 else 0.0374)
    t2 = (nm - 599.8) * (0.0264 if nm < 599.8 else 0.0323)
    t3 = (nm - 501.1) * (0.0490 if nm < 501.1 else 0.0382)
    return 0.362 * math.exp(-0.5 * t1 * t1) + 1.056 * math.exp(-0.5 * t2 * t2) - 0.065 * math.exp(-0.5 * t3 * t3)

def _cie1931_y_bar_py(nm):
    t1 = (nm - 568.8) * (0.0213 if nm < 568.8 else 0.0247)
    t2 = (nm - 530.9) * (0.0613 if nm < 530.9 else 0.0322)
    return 0.821 * math.exp(-0.5 * t1 * t1) + 0.286 * math.exp(-0.5 * t2 * t2)

def _cie1931_z_bar_py(nm):
    t1 = (nm - 437.0) * (0.0845 if nm < 437.0 else 0.0278)
    t2 = (nm - 459.0) * (0.0385 if nm < 459.0 else 0.0725)
    return 1.217 * math.exp(-0.5 * t1 * t1) + 0.681 * math.exp(-0.5 * t2 * t2)

def _fmt_float_array(name, values, per_line=8):
    lines = [f"static const float {name}[{len(values)}] = {{"]
    for i in range(0, len(values), per_line):
        chunk = values[i:i+per_line]
        s = "    " + ", ".join(f"{v:.8e}f" for v in chunk)
        if i + per_line < len(values):
            s += ","
        lines.append(s)
    lines.append("};")
    lines.append("")
    return lines

# Precompute CIE 1931 LUTs (701 values, 350-1050nm)
_LUT_START = 350
_LUT_END = 1050
_LUT_COUNT = _LUT_END - _LUT_START + 1
_CIE_X_BAR_LUT = [_cie1931_x_bar_py(nm) for nm in range(_LUT_START, _LUT_END + 1)]
_CIE_Y_BAR_LUT = [_cie1931_y_bar_py(nm) for nm in range(_LUT_START, _LUT_END + 1)]
_CIE_Z_BAR_LUT = [_cie1931_z_bar_py(nm) for nm in range(_LUT_START, _LUT_END + 1)]

# ============================================================
def fmt_impl():
    lines = [
        '#include "spectral_metrics_calc.h"',
        "",
        "/* Note: No math.h needed -- all expf() eliminated via precomputed LUTs */",
        "",
        DECO_OPEN,
        " *  Physical constants",
        DECO_CLOSE,
        "/* All in SI units, float constants for M23 soft-float */",
        "static const float PLANCK_CONSTANT  = 6.62607015e-34f;    /* J*s */",
        "static const float LIGHT_SPEED      = 299792458.0f;       /* m/s */",
        "static const float AVOGADRO_CONSTANT= 6.02214076e23f;     /* mol^-1 */",
        "static const float LUMINOUS_EFFICACY= 683.0f;            /* lm/W */",
        "",
        "/* Precomputed: 1.0 / (h * c * Na) * 1e6 -> photon_to_umol_factor */",
        "static const float PHOTON_TO_UMOL   = 1000000.0f / (PLANCK_CONSTANT * LIGHT_SPEED * AVOGADRO_CONSTANT);",
        "",
        DECO_OPEN,
        " *  Spectral coefficient scale LUT: 10^-N for N = 0..15",
        " *  Precomputed as float to avoid pow() on MCU",
        DECO_CLOSE,
        "static const float SCALE_LUT[16] = {",
        "    1.0e0f,   1.0e-1f,  1.0e-2f,  1.0e-3f,",
        "    1.0e-4f,  1.0e-5f,  1.0e-6f,  1.0e-7f,",
        "    1.0e-8f,  1.0e-9f,  1.0e-10f, 1.0e-11f,",
        "    1.0e-12f, 1.0e-13f, 1.0e-14f, 1.0e-15f,",
        "};",
        "",
        DECO_OPEN,
        " *  Chlorophyll A/B weight curves (Q15 fixed-point format)",
        " *  300 values each, covering 400nm to 699nm",
        " *  Converted from Python: Q15 = round(float_weight * 32768.0)",
        DECO_CLOSE,
    ]

    # Chlorophyll A Q15 weights
    vals_a = [round(w * 32768.0) for w in CHLOROPHYLL_WEIGHTED_IRRADIANCE_A]
    lines.append("static const uint16_t CHL_A_WEIGHTS_Q15[300] = {")
    for i in range(0, len(vals_a), 15):
        chunk = vals_a[i:i+15]
        s = "    " + ", ".join(f"{v:6d}" for v in chunk)
        if i + 15 < len(vals_a):
            s += ","
        lines.append(s)
    lines.append("};")
    lines.append("")

    # Chlorophyll B Q15 weights
    vals_b = [round(w * 32768.0) for w in CHLOROPHYLL_WEIGHTED_IRRADIANCE_B]
    lines.append("static const uint16_t CHL_B_WEIGHTS_Q15[300] = {")
    for i in range(0, len(vals_b), 15):
        chunk = vals_b[i:i+15]
        s = "    " + ", ".join(f"{v:6d}" for v in chunk)
        if i + 15 < len(vals_b):
            s += ","
        lines.append(s)
    lines.append("};")
    lines.append("")

    # Q15 -> float inline helper
    lines.extend([
        "/* Inline: convert Q15 (uint16) to float */",
        "static inline float q15_to_float(uint16_t q15) {",
        "    return (float)q15 * 3.0517578125e-5f;  /* 1/32768 */",
        "}",
        "",
    ])

    # McCree weights (float, only 17 points, not worth Q15)
    lines.append(DECO_OPEN)
    lines.append(" *  McCree 1972 field-mean photon-action weights")
    lines.append(" *  16 tabulated points (350-725nm, 25nm step) + extrapolated 740nm")
    lines.append(" *  Stored as float (only 17 points, 68 bytes)")
    lines.append(DECO_CLOSE)
    wls = list(MCCREE_RAW_WAVELENGTHS_NM) + [740]
    lines.append("static const uint16_t MCCREE_WAVELENGTHS_NM[17] = {")
    s = "    " + ", ".join(f"{w:4d}" for w in wls)
    lines.append(s)
    lines.append("};")

    # Extrapolate 740nm value
    left_val = float(MCCREE_FIELD_MEAN_RAW[-2])
    right_val = float(MCCREE_FIELD_MEAN_RAW[-1])
    slope = (right_val - left_val) / float(MCCREE_RAW_WAVELENGTHS_NM[-1] - MCCREE_RAW_WAVELENGTHS_NM[-2])
    tail_val = right_val + slope * (740.0 - float(MCCREE_RAW_WAVELENGTHS_NM[-1]))
    if tail_val < 0.0:
        tail_val = 0.0
    raw_vals = list(MCCREE_FIELD_MEAN_RAW) + [round(tail_val, 6)]

    lines.append("static const float MCCREE_WEIGHTS[17] = {")
    s = "    " + ", ".join(f"{v:.6f}f" for v in raw_vals)
    lines.append(s)
    lines.append("};")
    lines.append("")

    # ---- CIE 1931 tristimulus LUTs (precomputed, 701 values each, 350-1050nm) ----
    lines.append(DECO_OPEN)
    lines.append(" *  CIE 1931 x_bar(lambda) LUT -- precomputed from 3-Gaussian analytic")
    lines.append(" *  701 values, 350-1050nm, 1nm step")
    lines.append(DECO_CLOSE)
    lines.extend(_fmt_float_array("CIE_X_BAR_LUT", [round(v, 12) for v in _CIE_X_BAR_LUT]))

    lines.append(DECO_OPEN)
    lines.append(" *  CIE 1931 y_bar(lambda) LUT (= photopic V(lambda))")
    lines.append(" *  701 values, 350-1050nm, 1nm step")
    lines.append(DECO_CLOSE)
    lines.extend(_fmt_float_array("CIE_Y_BAR_LUT", [round(v, 12) for v in _CIE_Y_BAR_LUT]))

    lines.append(DECO_OPEN)
    lines.append(" *  CIE 1931 z_bar(lambda) LUT -- precomputed from 2-Gaussian analytic")
    lines.append(" *  701 values, 350-1050nm, 1nm step")
    lines.append(DECO_CLOSE)
    lines.extend(_fmt_float_array("CIE_Z_BAR_LUT", [round(v, 12) for v in _CIE_Z_BAR_LUT]))

    # ---- Helper: photopic weighting (V(lambda)) -- LUT lookup ----
    lines.extend([
        DECO_OPEN,
        " *  V(lambda) photopic luminosity function (CIE 1924 photopic)",
        " *  LUT lookup into CIE_Y_BAR_LUT (precomputed, no expf() on MCU)",
        DECO_CLOSE,
        "static inline float photopic_weight(float lambda_nm) {",
        "    int idx = (int)(lambda_nm + 0.5f) - SPECTRAL_WAVELENGTH_START_NM;",
        "    if (idx < 0 || idx >= SPECTRAL_WAVELENGTH_COUNT) return 0.0f;",
        "    return CIE_Y_BAR_LUT[idx];",
        "}",
        "",
    ])


    # ---- Helper: McCree weight interpolation ----
    lines.extend([
        DECO_OPEN,
        " *  McCree weight at a given wavelength (linear interpolation)",
        DECO_CLOSE,
        "static float mccree_weight(float lambda_nm) {",
        "    int left_idx = 0;",
        "    int right_idx = 16;  /* index of last element */",
        "",
        "    /* Outside range -> zero */",
        "    if (lambda_nm < MCCREE_WAVELENGTHS_NM[0] || lambda_nm > MCCREE_WAVELENGTHS_NM[16]) {",
        "        return 0.0f;",
        "    }",
        "",
        "    /* Binary search for interval */",
        "    while (right_idx - left_idx > 1) {",
        "        int mid = (left_idx + right_idx) >> 1;",
        "        if (lambda_nm < (float)MCCREE_WAVELENGTHS_NM[mid]) {",
        "            right_idx = mid;",
        "        } else {",
        "            left_idx = mid;",
        "        }",
        "    }",
        "",
        "    /* Linear interpolation */",
        "    float x0 = (float)MCCREE_WAVELENGTHS_NM[left_idx];",
        "    float x1 = (float)MCCREE_WAVELENGTHS_NM[right_idx];",
        "    float y0 = MCCREE_WEIGHTS[left_idx];",
        "    float y1 = MCCREE_WEIGHTS[right_idx];",
        "    float ratio = (lambda_nm - x0) / (x1 - x0);",
        "",
        "    return y0 + (y1 - y0) * ratio;",
        "}",
        "",
    ])

    # ---- Helper: get scaled spectral value ----
    lines.extend([
        DECO_OPEN,
        " *  Get scaled spectral value at a given wavelength index",
        " *  result = wavelength_points_spectral_data[index] * scale_factor",
        DECO_CLOSE,
        "static inline float get_scaled_value(int nm) {",
        "    int idx = nm - SPECTRAL_WAVELENGTH_START_NM;",
        "    if (idx < 0 || idx >= SPECTRAL_WAVELENGTH_COUNT) {",
        "        return 0.0f;",
        "    }",
        "    uint16_t coeff = spectral_data.spectral_coefficient;",
        "    float scale = SCALE_LUT[coeff & 0x0F];",
        "    return (float)spectral_data.wavelength_points_spectral_data[idx] * scale;",
        "}",
        "",
    ])

    # ---- Universal non-chunked range-accumulate function (for single-shot <3ms functions) ----
    lines.extend([
        DECO_OPEN,
        " *  Internal: accumulate spectral energy over [start_nm, end_nm]",
        " *  mode: 0 = sum(S), 1 = sum(S)/10, 2 = sum(S*lambda/hcNa*1e6)",
        " *  Assign result to *result_ptr",
        " *  Returns CALC_COMPLETED or CALC_ERROR",
        " *  NOTE: Used only by single-shot functions (<3ms).",
        " *        For chunked functions, see accum_chunk() below.",
        DECO_CLOSE,
        "#define ACCUM_MODE_SUM        0  /* direct sum of W/m2/nm */",
        "#define ACCUM_MODE_SUM_DIV10  1  /* PAR mode: sum/10 */",
        "#define ACCUM_MODE_PHOTON     2  /* photon integral (umol/m2/s) */",
        "",
        "static calc_status_t range_accumulate(",
        "    int start_nm,",
        "    int end_nm,",
        "    float *result_ptr,",
        "    int mode)",
        "{",
        "    double accum = 0.0;  /* double for intermediate precision */",
        "    int nm;",
        "",
        "    if (result_ptr == NULL) {",
        "        return CALC_ERROR;",
        "    }",
        "",
        "    /* Clamp to valid range */",
        "    if (start_nm < SPECTRAL_WAVELENGTH_START_NM) start_nm = SPECTRAL_WAVELENGTH_START_NM;",
        "    if (end_nm   > SPECTRAL_WAVELENGTH_END_NM)   end_nm   = SPECTRAL_WAVELENGTH_END_NM;",
        "    if (start_nm > end_nm) {",
        "        *result_ptr = 0.0f;",
        "        return CALC_COMPLETED;",
        "    }",
        "",
        "    if (mode == ACCUM_MODE_PHOTON) {",
        "        /* Photon integral: S * lambda / (h*c*Na) * 1e6 */",
        "        for (nm = start_nm; nm <= end_nm; nm++) {",
        "            float s = get_scaled_value(nm);",
        "            float lambda_m = (float)nm * 1.0e-9f;",
        "            accum += (double)s * (double)lambda_m;",
        "        }",
        "        accum *= (double)PHOTON_TO_UMOL;",
        "    } else {",
        "        /* Energy integral: sum of S or sum/10 */",
        "        for (nm = start_nm; nm <= end_nm; nm++) {",
        "            accum += (double)get_scaled_value(nm);",
        "        }",
        "        if (mode == ACCUM_MODE_SUM_DIV10) {",
        "            accum /= 10.0;",
        "        }",
        "    }",
        "",
        "    *result_ptr = (float)accum;",
        "    return CALC_COMPLETED;",
        "}",
        "",
    ])

    # ---- Weighted accumulate helper (non-chunked, for single-shot) ----
    lines.extend([
        DECO_OPEN,
        " *  Internal: weighted integral over [start_nm, end_nm]",
        " *  result = sum(S[nm] * weight[nm - start_nm])",
        " *  Weights are in Q15 format (uint16_t array)",
        DECO_CLOSE,
        "static calc_status_t range_weighted_q15(",
        "    int start_nm,",
        "    int end_nm,",
        "    const uint16_t *weights_q15,",
        "    float *result_ptr)",
        "{",
        "    double accum = 0.0;",
        "    int nm;",
        "",
        "    if (weights_q15 == NULL || result_ptr == NULL) {",
        "        return CALC_ERROR;",
        "    }",
        "",
        "    for (nm = start_nm; nm <= end_nm; nm++) {",
        "        float s = get_scaled_value(nm);",
        "        float w = q15_to_float(weights_q15[nm - start_nm]);",
        "        accum += (double)s * (double)w;",
        "    }",
        "",
        "    *result_ptr = (float)accum;",
        "    return CALC_COMPLETED;",
        "}",
        "",
    ])

    # ================================================================
    # Chunked accumulation helpers (for time-sliced functions >3ms)
    # ================================================================
    lines.extend([
        DECO_OPEN,
        " *  Chunked accumulation (time-sliced)",
        " *",
        " *  Control block + processing helper for functions that need",
        " *  to be split across multiple calls to keep each call <~2ms.",
        " *",
        " *  accum_cb_t  : for range_accumulate-type functions (SUM/PHOTON)",
        " *  wq15_cb_t   : for Q15-weighted functions (Chl_A/B)",
        " *  peakext_cb_t: for peak_ext (max search)",
        " *  mccree_cb_t : for McCree Y_PFD",
        DECO_CLOSE,
        "",
        "/* Chunk sizes */",
        "#define CHUNK_SIZE        20  /* default: ~1.5-3ms per call */",
        "#define LUX_CHUNK_SIZE    20  /* lux: LUT lookup, same as default CHUNK_SIZE */",
        "#define MCCREE_CHUNK_SIZE  30  /* McCree: binary search + interp, ~2.5ms */",
        "",

        "/* --- Chunked accumulator for range_accumulate-type functions --- */",
        "typedef struct {",
        "    int nm;              /* current nm position, -1 = idle */",
        "    double accum;        /* partial sum */",
        "    int start_nm;        /* range start (inclusive) */",
        "    int end_nm;          /* range end (inclusive) */",
        "    int mode;            /* ACCUM_MODE_SUM or ACCUM_MODE_PHOTON */",
        "    int chunk_size;      /* points per call */",
        "    float *result_ptr;   /* where to write final result */",
        "} accum_cb_t;",
        "",
        "static calc_status_t accum_chunk(accum_cb_t *cb) {",
        "    int end;",
        "    if (cb->nm < 0) {",
        "        cb->nm = cb->start_nm;",
        "        cb->accum = 0.0;",
        "    }",
        "    end = cb->nm + cb->chunk_size - 1;",
        "    if (end > cb->end_nm) end = cb->end_nm;",
        "",
        "    if (cb->mode == ACCUM_MODE_PHOTON) {",
        "        for (; cb->nm <= end; cb->nm++) {",
        "            float s = get_scaled_value(cb->nm);",
        "            float lm = (float)cb->nm * 1.0e-9f;",
        "            cb->accum += (double)s * (double)lm;",
        "        }",
        "    } else {",
        "        for (; cb->nm <= end; cb->nm++) {",
        "            cb->accum += (double)get_scaled_value(cb->nm);",
        "        }",
        "    }",
        "",
        "    if (cb->nm > cb->end_nm) {",
        "        if (cb->mode == ACCUM_MODE_PHOTON) {",
        "            cb->accum *= (double)PHOTON_TO_UMOL;",
        "        }",
        "        *cb->result_ptr = (float)cb->accum;",
        "        cb->nm = -1;",
        "        return CALC_COMPLETED;",
        "    }",
        "    return CALC_NOT_COMPLETED;",
        "}",
        "",
        "/* --- Chunked weighted accumulator for Chl_A/B --- */",
        "typedef struct {",
        "    int nm;",
        "    double accum;",
        "    int start_nm;",
        "    int end_nm;",
        "    int chunk_size;",
        "    const uint16_t *weights;",
        "    float *result_ptr;",
        "} wq15_cb_t;",
        "",
        "static calc_status_t wq15_chunk(wq15_cb_t *cb) {",
        "    int end;",
        "    if (cb->nm < 0) {",
        "        cb->nm = cb->start_nm;",
        "        cb->accum = 0.0;",
        "    }",
        "    end = cb->nm + cb->chunk_size - 1;",
        "    if (end > cb->end_nm) end = cb->end_nm;",
        "",
        "    for (; cb->nm <= end; cb->nm++) {",
        "        float s = get_scaled_value(cb->nm);",
        "        float w = q15_to_float(cb->weights[cb->nm - cb->start_nm]);",
        "        cb->accum += (double)s * (double)w;",
        "    }",
        "",
        "    if (cb->nm > cb->end_nm) {",
        "        *cb->result_ptr = (float)cb->accum;",
        "        cb->nm = -1;",
        "        return CALC_COMPLETED;",
        "    }",
        "    return CALC_NOT_COMPLETED;",
        "}",
        "",
    ])

    # ---- Now generate all public functions ----
    funcs_tpl = []

    # 1. peak (single-shot, <3ms)
    funcs_tpl.extend([
        DECO_OPEN,
        " *  Public API implementations",
        " *",
        " *  Single-shot functions (<3ms):  peak, PAR, E_PAR, PFD_r/b/g/uv/fr",
        " *  Chunked functions (>3ms):      peak_ext, WM2, PPFD, PFD, E_PPFD,",
        " *                                  E_PFD, E_PFD_fr, lux, Chl_A, Chl_B, McCree_Y",
        DECO_CLOSE,
        "",
        "/* --- peak: scan 400-700nm for max value and its wavelength --- */",
        "calc_status_t spectral_calc_peak(void) {",
        "    float max_val = -1.0f;",
        "    int max_nm = SPECTRAL_WAVELENGTH_START_NM;",
        "    int nm;",
        "",
        "    for (nm = 400; nm <= 700; nm++) {",
        "        float s = get_scaled_value(nm);",
        "        if (s > max_val) {",
        "            max_val = s;",
        "            max_nm = nm;",
        "        }",
        "    }",
        "",
        "    spectral_data.peak_cwl = max_nm;",
        "    spectral_data.peak_spectrum = max_val;",
        "    return CALC_COMPLETED;",
        "}",
        "",
    ])

    # 2. peak_ext (chunked, CHUNK_SIZE=100)
    funcs_tpl.extend([
        "/* --- peak_ext (chunked): scan 350-1050nm --- */",
        "static int _peak_ext_nm = -1;",
        "static float _peak_ext_max_val = -1.0f;",
        "static int _peak_ext_max_nm = SPECTRAL_WAVELENGTH_START_NM;",
        "",
        "calc_status_t spectral_calc_peak_ext(void) {",
        "    int end;",
        "    if (_peak_ext_nm < 0) {",
        "        _peak_ext_nm = SPECTRAL_WAVELENGTH_START_NM;",
        "        _peak_ext_max_val = -1.0f;",
        "        _peak_ext_max_nm = SPECTRAL_WAVELENGTH_START_NM;",
        "    }",
        "    end = _peak_ext_nm + CHUNK_SIZE - 1;",
        "    if (end > SPECTRAL_WAVELENGTH_END_NM) end = SPECTRAL_WAVELENGTH_END_NM;",
        "",
        "    for (; _peak_ext_nm <= end; _peak_ext_nm++) {",
        "        float s = get_scaled_value(_peak_ext_nm);",
        "        if (s > _peak_ext_max_val) {",
        "            _peak_ext_max_val = s;",
        "            _peak_ext_max_nm = _peak_ext_nm;",
        "        }",
        "    }",
        "",
        "    if (_peak_ext_nm > SPECTRAL_WAVELENGTH_END_NM) {",
        "        spectral_data.E_peak_cwl = _peak_ext_max_nm;",
        "        spectral_data.E_peak_spectrum = _peak_ext_max_val;",
        "        _peak_ext_nm = -1;",
        "        return CALC_COMPLETED;",
        "    }",
        "    return CALC_NOT_COMPLETED;",
        "}",
        "",
    ])

    # 3. WM2 (chunked via accum_cb, SUM mode)
    funcs_tpl.extend([
        "/* --- WM2 (chunked): 350-1050nm energy sum --- */",
        "static accum_cb_t _wm2_cb = { -1, 0.0, 350, 1050, ACCUM_MODE_SUM, CHUNK_SIZE, &spectral_data.WM2 };",
        "calc_status_t spectral_calc_WM2(void) { return accum_chunk(&_wm2_cb); }",
        "",
    ])

    # 4. PAR and E_PAR (single-shot, <3ms)
    funcs_tpl.extend([
        "/* --- PAR, E_PAR (single-shot, <3ms) --- */",
        "calc_status_t spectral_calc_PAR(void) {",
        "    return range_accumulate(400, 700, &spectral_data.par, ACCUM_MODE_SUM_DIV10);",
        "}",
        "",
        "calc_status_t spectral_calc_E_PAR(void) {",
        "    return range_accumulate(400, 750, &spectral_data.E_par, ACCUM_MODE_SUM_DIV10);",
        "}",
        "",
    ])

    # 5. Photon integrals: PPFD, PFD (chunked), PFD_r/b/g/uv/fr (single-shot)
    funcs_tpl.extend([
        "/* --- PPFD (chunked): 400-700nm photon integral --- */",
        "static accum_cb_t _ppfd_cb = { -1, 0.0, 400, 700, ACCUM_MODE_PHOTON, CHUNK_SIZE, &spectral_data.ppfd };",
        "calc_status_t spectral_calc_PPFD(void) { return accum_chunk(&_ppfd_cb); }",
        "",
        "/* --- PFD (chunked): 350-780nm photon integral --- */",
        "static accum_cb_t _pfd_cb = { -1, 0.0, 350, 780, ACCUM_MODE_PHOTON, CHUNK_SIZE, &spectral_data.pfd };",
        "calc_status_t spectral_calc_PFD(void) { return accum_chunk(&_pfd_cb); }",
        "",
        "/* --- PFD sub-bands (single-shot, all <3ms) --- */",
        "calc_status_t spectral_calc_PFD_r(void)  { return range_accumulate(600, 699, &spectral_data.pfd_r, ACCUM_MODE_PHOTON); }",
        "calc_status_t spectral_calc_PFD_b(void)  { return range_accumulate(400, 499, &spectral_data.pfd_b, ACCUM_MODE_PHOTON); }",
        "calc_status_t spectral_calc_PFD_g(void)  { return range_accumulate(500, 599, &spectral_data.pfd_g, ACCUM_MODE_PHOTON); }",
        "calc_status_t spectral_calc_PFD_uv(void) { return range_accumulate(350, 400, &spectral_data.pfd_uv, ACCUM_MODE_PHOTON); }",
        "calc_status_t spectral_calc_PFD_fr(void) { return range_accumulate(700, 780, &spectral_data.pfd_fr, ACCUM_MODE_PHOTON); }",
        "",
    ])

    # 6. Extended photon integrals (chunked)
    funcs_tpl.extend([
        "/* --- E_PPFD (chunked): 400-750nm --- */",
        "static accum_cb_t _e_ppfd_cb = { -1, 0.0, 400, 750, ACCUM_MODE_PHOTON, CHUNK_SIZE, &spectral_data.E_ppfd };",
        "calc_status_t spectral_calc_E_PPFD(void) { return accum_chunk(&_e_ppfd_cb); }",
        "",
        "/* --- E_PFD (chunked): 350-1050nm --- */",
        "static accum_cb_t _e_pfd_cb = { -1, 0.0, 350, 1050, ACCUM_MODE_PHOTON, CHUNK_SIZE, &spectral_data.E_pfd };",
        "calc_status_t spectral_calc_E_PFD(void) { return accum_chunk(&_e_pfd_cb); }",
        "",
        "/* --- E_PFD_fr (chunked): 700-1050nm --- */",
        "static accum_cb_t _e_pfd_fr_cb = { -1, 0.0, 700, 1050, ACCUM_MODE_PHOTON, CHUNK_SIZE, &spectral_data.E_pfd_fr };",
        "calc_status_t spectral_calc_E_PFD_fr(void) { return accum_chunk(&_e_pfd_fr_cb); }",
        "",
        "/* Note: E_PFD_r == PFD_r, E_PFD_b == PFD_b, etc. (same range) */",
        "/* The spectral_calc_all() scheduler handles assignment. */",
        "",
    ])

    # 7. Lux (chunked via LUT lookup, same as default CHUNK_SIZE)
    funcs_tpl.extend([
        "/* --- lux (chunked): V(lambda) weighted, LUT lookup --- */",
        "static int _lux_nm = -1;",
        "static double _lux_accum = 0.0;",
        "",
        "calc_status_t spectral_calc_lux(void) {",

        "    int end;",
        "    if (_lux_nm < 0) {",
        "        _lux_nm = SPECTRAL_WAVELENGTH_START_NM;",
        "        _lux_accum = 0.0;",
        "    }",
        "    end = _lux_nm + LUX_CHUNK_SIZE - 1;",
        "    if (end > SPECTRAL_WAVELENGTH_END_NM) end = SPECTRAL_WAVELENGTH_END_NM;",
        "",
        "    for (; _lux_nm <= end; _lux_nm++) {",
        "        float s = get_scaled_value(_lux_nm);",
        "        float v = photopic_weight((float)_lux_nm);",
        "        _lux_accum += (double)s * (double)v;",
        "    }",
        "",
        "    if (_lux_nm > SPECTRAL_WAVELENGTH_END_NM) {",
        "        spectral_data.lux = (float)(_lux_accum * (double)LUMINOUS_EFFICACY);",
        "        _lux_nm = -1;",
        "        return CALC_COMPLETED;",
        "    }",
        "    return CALC_NOT_COMPLETED;",
        "}",
        "",
    ])

    # 8. Chl_A and Chl_B (chunked via wq15_cb)
    funcs_tpl.extend([
        "/* --- Chl_A (chunked): 400-699nm Q15 weighted --- */",
        "static wq15_cb_t _chl_a_cb = { -1, 0.0, 400, 699, CHUNK_SIZE, CHL_A_WEIGHTS_Q15, &spectral_data.chl_a_value };",
        "calc_status_t spectral_calc_Chl_A(void) { return wq15_chunk(&_chl_a_cb); }",
        "",
        "/* --- Chl_B (chunked): 400-699nm Q15 weighted --- */",
        "static wq15_cb_t _chl_b_cb = { -1, 0.0, 400, 699, CHUNK_SIZE, CHL_B_WEIGHTS_Q15, &spectral_data.chl_b_value };",
        "calc_status_t spectral_calc_Chl_B(void) { return wq15_chunk(&_chl_b_cb); }",
        "",
    ])

    # 9. McCree Y_PFD (chunked, MCCREE_CHUNK_SIZE=50)
    funcs_tpl.extend([
        "/* --- McCree Y_PFD (chunked, 50pt/call): 350-740nm weighted photon integral --- */",
        "static int _mccree_nm = -1;",
        "static double _mccree_accum = 0.0;",
        "",
        "calc_status_t spectral_calc_McCree_Y(void) {",
        "    int end;",
        "    if (_mccree_nm < 0) {",
        "        _mccree_nm = 350;",
        "        _mccree_accum = 0.0;",
        "    }",
        "    end = _mccree_nm + MCCREE_CHUNK_SIZE - 1;",
        "    if (end > 740) end = 740;",
        "",
        "    for (; _mccree_nm <= end; _mccree_nm++) {",
        "        float s = get_scaled_value(_mccree_nm);",
        "        float w = mccree_weight((float)_mccree_nm);",
        "        if (w <= 0.0f) continue;",
        "        float lambda_m = (float)_mccree_nm * 1.0e-9f;",
        "        _mccree_accum += (double)s * (double)lambda_m * (double)w;",
        "    }",
        "",
        "    if (_mccree_nm > 740) {",
        "        spectral_data.mccree_ypfd = (float)(_mccree_accum * (double)PHOTON_TO_UMOL);",
        "        _mccree_nm = -1;",
        "        return CALC_COMPLETED;",
        "    }",
        "    return CALC_NOT_COMPLETED;",
        "}",
        "",
    ])

    # ---- 10. CCT (correlated color temperature, chunked) ----
    funcs_tpl.extend([
        "/* --- CCT (chunked): CIE 1931 XYZ tristimulus + McCamy formula --- */",
        "/*",
        " *  X = sum(S * x_bar(lambda)), Y = sum(S * y_bar(lambda)), Z = sum(S * z_bar(lambda))",
        " *  All CIE 1931 tristimulus weights are precomputed LUTs:",
        " *    x_bar -> CIE_X_BAR_LUT[idx]",
        " *    y_bar -> CIE_Y_BAR_LUT[idx] (= photopic V(lambda), same as photopic_weight())",
        " *    z_bar -> CIE_Z_BAR_LUT[idx]",
        " *  After accumulation: x = X/(X+Y+Z), y = Y/(X+Y+Z)",
        " *  CCT = 449*n^3 + 3525*n^2 + 6823.3*n + 5520.33, where n = (x-0.3320)/(0.1858-y)",
        " */",
        "static int _cct_nm = -1;",
        "static double _cct_x_accum = 0.0;",
        "static double _cct_y_accum = 0.0;",
        "static double _cct_z_accum = 0.0;",
        "",
        "calc_status_t spectral_calc_CCT(void) {",
        "    int end;",
        "    if (_cct_nm < 0) {",
        "        _cct_nm = SPECTRAL_WAVELENGTH_START_NM;",
        "        _cct_x_accum = 0.0;",
        "        _cct_y_accum = 0.0;",
        "        _cct_z_accum = 0.0;",
        "    }",
        "    end = _cct_nm + CHUNK_SIZE - 1;",
        "    if (end > SPECTRAL_WAVELENGTH_END_NM) end = SPECTRAL_WAVELENGTH_END_NM;",
        "",
        "    for (; _cct_nm <= end; _cct_nm++) {",
        "        float s = get_scaled_value(_cct_nm);",
        "        int idx = _cct_nm - SPECTRAL_WAVELENGTH_START_NM;",
        "        _cct_x_accum += (double)s * (double)CIE_X_BAR_LUT[idx];",
        "        _cct_y_accum += (double)s * (double)CIE_Y_BAR_LUT[idx];",
        "        _cct_z_accum += (double)s * (double)CIE_Z_BAR_LUT[idx];",
        "    }",
        "",
        "    if (_cct_nm > SPECTRAL_WAVELENGTH_END_NM) {",

        "        double sum_xyz = _cct_x_accum + _cct_y_accum + _cct_z_accum;",
        "        if (sum_xyz > 0.0) {",
        "            double x = _cct_x_accum / sum_xyz;",
        "            double y = _cct_y_accum / sum_xyz;",
        "            double denom = 0.1858 - y;",
        "            if (denom > 1e-12 || denom < -1e-12) {",
        "                double n = (x - 0.3320) / denom;",
        "                spectral_data.cct = (float)(449.0 * n * n * n",
        "                                          + 3525.0 * n * n",
        "                                          + 6823.3 * n",
        "                                          + 5520.33);",
        "            } else {",
        "                spectral_data.cct = 0.0f;  /* near Planckian locus degenerate */",
        "            }",
        "        } else {",
        "            spectral_data.cct = 0.0f;",
        "        }",
        "        _cct_nm = -1;",
        "        return CALC_COMPLETED;",
        "    }",
        "    return CALC_NOT_COMPLETED;",
        "}",
        "",
    ])

    # ---- 11. Scheduler ----
    funcs_tpl.extend([
        DECO_OPEN,
        " *  Bulk scheduler",
        " * 每次调用执行1个计算步骤, 步骤内分块未完成则返回CALC_NOT_COMPLETED",
        " * 全部完成返回CALC_COMPLETED",
        DECO_CLOSE,
        "static int _calc_step = 0;  /* current step index */",
        "",
        "calc_status_t spectral_calc_all(void) {",
        "    calc_status_t s = CALC_COMPLETED;",
        "",
        "    switch (_calc_step) {",
        "        case 0:  s = spectral_calc_peak();    break;",
        "        case 1:  s = spectral_calc_peak_ext(); break;",
        "        case 2:  s = spectral_calc_WM2();      break;",
        "        case 3:  s = spectral_calc_PAR();      break;",
        "        case 4:  s = spectral_calc_E_PAR();    break;",
        "        case 5:  s = spectral_calc_PPFD();     break;",
        "        case 6:  s = spectral_calc_PFD();      break;",
        "        case 7:  s = spectral_calc_PFD_r();    break;",
        "        case 8:  s = spectral_calc_PFD_b();    break;",
        "        case 9:  s = spectral_calc_PFD_g();    break;",
        "        case 10: s = spectral_calc_PFD_uv();   break;",
        "        case 11: s = spectral_calc_PFD_fr();   break;",
        "        case 12: s = spectral_calc_E_PPFD();   break;",
        "        case 13: s = spectral_calc_E_PFD();    break;",
        "        case 14: s = spectral_calc_E_PFD_fr(); break;",
        "        case 15: s = spectral_calc_lux();      break;",
        "        case 16: s = spectral_calc_Chl_A();    break;",
        "        case 17: s = spectral_calc_Chl_B();    break;",
        "        case 18: s = spectral_calc_McCree_Y(); break;",
        "        case 19:",
        "            /* Step 19: no calc needed, assign E_PFD_r/b/g/uv */",
        "            spectral_data.E_pfd_r  = spectral_data.pfd_r;",
        "            spectral_data.E_pfd_b  = spectral_data.pfd_b;",
        "            spectral_data.E_pfd_g  = spectral_data.pfd_g;",
        "            spectral_data.E_pfd_uv = spectral_data.pfd_uv;",
        "            break;",
        "        case 20: s = spectral_calc_CCT();     break;",
        "        default:",
        "            break;",
        "    }",
        "",
        "    if (s == CALC_ERROR) {",
        "        return CALC_ERROR;",
        "    }",
        "",
        "    if (s == CALC_NOT_COMPLETED) {",
        "        return CALC_NOT_COMPLETED;",
        "    }",
        "",
        "    /* Step completed, advance */",
        "    _calc_step++;",
        "",
        "    if (_calc_step >= 21) {",
        "        return CALC_COMPLETED;",
        "    }",
        "",
        "    return CALC_NOT_COMPLETED;  /* more steps remain */",
        "}",
        "",
        "void spectral_calc_all_reset(void) {",
        "    _calc_step = 0;",
        "    /* Reset all chunk state variables */",
        "    _peak_ext_nm = -1;",
        "    _wm2_cb.nm = -1;",
        "    _ppfd_cb.nm = -1;",
        "    _pfd_cb.nm = -1;",
        "    _e_ppfd_cb.nm = -1;",
        "    _e_pfd_cb.nm = -1;",
        "    _e_pfd_fr_cb.nm = -1;",
        "    _lux_nm = -1;",
        "    _chl_a_cb.nm = -1;",
        "    _chl_b_cb.nm = -1;",
        "    _mccree_nm = -1;",
        "    _cct_nm = -1;",
        "}",
        "",
    ])

    return "\n".join(lines + funcs_tpl)

# ============================================================
def generate():
    header = fmt_header("温室光谱指标计算库 (Spectral Metrics Calculation Library)")
    impl = fmt_impl()

    out_dir = "d:\\VSCO_PAR"
    with open(os.path.join(out_dir, "spectral_metrics_calc.h"), "w", encoding="utf-8") as f:
        f.write(header)
    with open(os.path.join(out_dir, "spectral_metrics_calc.c"), "w", encoding="utf-8") as f:
        f.write(impl)

    print("Generated:")
    print("  spectral_metrics_calc.h")
    print("  spectral_metrics_calc.c")

if __name__ == "__main__":
    generate()
