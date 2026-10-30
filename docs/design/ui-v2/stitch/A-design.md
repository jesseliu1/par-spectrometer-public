<!-- 来源：Google Stitch 项目 projects/<id> 的设计系统 "Precision Radiometry"（assets/1d3a9b07b002461e8a9d9568bbd64690，Stitch 自动生成），2026-10-18 原样导出。
     对应方向 A「实验室仪表」，屏幕 projects/<id>/screens/c6c108ca705e44f6b5bb6767631f28ff。
     这是 Stitch 的设计说明，不是本项目已采纳的令牌；正式令牌以 docs/design/ui-v2-pages.md 第 3.4 节为准，待负责人选定方向后再定稿。
     其中的示例按钮（单次采集、连续采集、校准暗电流、停止采集）和 350–850 nm 范围是 Stitch 自拟内容，与 alpha 只读、350–1050 nm 的要求不符，见 ../方向对比.md。 -->

---
name: Precision Radiometry
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#3f4850'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#707881'
  outline-variant: '#bfc7d2'
  surface-tint: '#006398'
  primary: '#006194'
  on-primary: '#ffffff'
  primary-container: '#007bb9'
  on-primary-container: '#fdfcff'
  inverse-primary: '#93ccff'
  secondary: '#006a63'
  on-secondary: '#ffffff'
  secondary-container: '#99efe5'
  on-secondary-container: '#006f67'
  tertiary: '#4f5d71'
  on-tertiary: '#ffffff'
  tertiary-container: '#67758b'
  on-tertiary-container: '#fdfcff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cce5ff'
  primary-fixed-dim: '#93ccff'
  on-primary-fixed: '#001d31'
  on-primary-fixed-variant: '#004b73'
  secondary-fixed: '#9cf2e8'
  secondary-fixed-dim: '#80d5cb'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#00504a'
  tertiary-fixed: '#d5e3fc'
  tertiary-fixed-dim: '#b9c7df'
  on-tertiary-fixed: '#0d1c2e'
  on-tertiary-fixed-variant: '#3a485b'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  headline-sm:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  body-lg:
    fontFamily: Noto Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: Noto Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Noto Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-telemetry-lg:
    fontFamily: JetBrains Mono
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
  label-telemetry-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-telemetry-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
  label-caps:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  margin: 1rem
  space-xs: 0.25rem
  space-sm: 0.375rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system targets optical engineers, plant physiologists, and laboratory researchers operating high-precision PAR (Photosynthetically Active Radiation) spectrometers. The design language is strictly utilitarian, functional, and rigorous. It embodies a Modern Technical Instrument aesthetic: high data density, crystal-clear visual hierarchy, zero ornamental fluff, and uncompromised legibility under typical laboratory lighting environments.

Visual cues draw inspiration from precision benchtop measurement devices and scientific workstations. Chrome and decorative gradients are discarded in favor of calibrated neutral surfaces, razor-sharp 1px structural framing, and deliberate chromatic cues reserved strictly for telemetry state validation, spectral waveforms, and band classification.

## Colors

The color palette is engineered for prolonged operational focus and optical data discrimination. 

- **Canvas & Surface Tiering:** The root canvas rests on `#f8fafc` (Slate 50), with operational sub-panels on `#f1f5f9` (Slate 100) and critical telemetry readout cards set against stark white `#ffffff`. Structural borders employ `#e2e8f0` (Slate 200) for standard segmenting and `#cbd5e1` (Slate 300) for focused boundaries.
- **Typographic Neutral Hierarchy:** Primary scientific values and critical headings use `#0f172a` (Slate 900). Secondary metadata, field labels, and axis markers use `#334155` (Slate 700) and `#64748b` (Slate 500).
- **Technical Blue (Primary `#0284c7`):** Reserved exclusively for active device states, selected wave peaks, focused cursor scrubbers, primary acquisition triggers, and the primary live spectrum curve.
- **PAR Spectral Bands (400–700 nm):** Rendered as subtle, scientific translucent fills over the chart canvas:
  - Blue/Cyan band (400–500 nm): `rgba(2, 132, 199, 0.08)`
  - Green/Amber band (500–600 nm): `rgba(16, 185, 129, 0.06)`
  - Red/Far-Red band (600–750 nm): `rgba(244, 63, 94, 0.07)`
- **Telemetry State Indicators:**
  - 采集成功 (Acquisition Success / Calibrated): Emerald `#059669` with background `#ecfdf5` and border `#a7f3d0`.
  - 复核未完成 (Pending Verification / Warmup): Amber `#d97706` with background `#fffbeb` and border `#fde68a`.
  - 采集失败 / 溢出 (Error / Sensor Saturation): Rose `#e11d48` with background `#fff1f2` and border `#fecdd3`.

## Typography

Typography prioritizes high data density and instant optical scannability. 

- **Primary Interface Text:** `Noto Sans` (Simplified Chinese) paired with `Geist` provides neutral, highly legible glyph rendering across UI controls, parameter inputs, and scientific descriptions without distraction.
- **Telemetry & Numerical Data:** All numeric readouts (PPFD, YPFD, W/m², Lux, CCT, CRI, R:FR, integration times, and wavelength values) must use `JetBrains Mono` with tabular lining figures (`font-variant-numeric: tabular-nums`). This guarantees rigid horizontal alignment across dynamic streaming data columns.
- **Hierarchy Rules:** Large marketing-scale displays are prohibited. Primary telemetry indicators utilize `label-telemetry-lg` (22px bold monospace), preserving critical vertical canvas space for spectrum visualizers and tabular measurement matrices.

## Layout & Spacing

Designed specifically for standard laboratory desktop form factors (target baseline 1440x900 non-scrolling instrument viewports):

- **Grid Architecture:** A rigid 3-pane instrument dashboard configuration:
  - **Left Parameter Rail (280px fixed):** Optical calibration, integration time settings, dark current subtraction, and serial communication triggers.
  - **Central Main Canvas (Fluid):** Live spectral curve graph (350–850 nm) with interactive crosshairs, overlay references, and PAR region shading.
  - **Right Telemetry Matrix (340px fixed):** Instant scalar measurements (PPFD, PFD-B, PFD-G, PFD-R, PFD-FR, Lux, CCT, Peak λ).
  - **Bottom Inspection Drawer (180px collapsible):** Historical scan logs and tabular multi-channel integration data.
- **Rhythm:** An ultra-compact 4px/8px base spacing grid optimizes screen real estate, keeping all high-frequency instrumentation controls visible above the fold without mouse-wheel travel.

## Elevation & Depth

This system avoids drop shadows and ambient blur effects to simulate the clean, uncompromised precision of analytical instrument glass and hardware monitors.

- **Zero-Shadow Philosophy:** Elements rely strictly on 1px borders (`#e2e8f0`) and subtle surface tonal shifts (`#ffffff` panels atop `#f8fafc` workspace canvas) to convey stratification.
- **Active & Selected Focus:** Active inputs, selected chart inspection windows, and focused tabular rows receive a 1px border recolor to `#0284c7` and an optional `0 0 0 1px #0284c7` focus ring.
- **Modal Dialogs & Overlays:** When calibration or firmware prompts appear, depth is established via a flat 1px solid border (`#cbd5e1`) and a 20% darkened neutral backdrop (`rgba(15, 23, 42, 0.35)`), avoiding soft visual artifacts.

## Shapes

Shapes reflect precision laboratory hardware: compact, squared, and controlled.

- **Corner Radii:** Set strictly to `roundedness: 1` (4px / 0.25rem for buttons, cards, tags, and inputs). 
- **Inner Micro-Elements:** Dropdown items, inner badge counters, and segmented switch indicators use 2px radius.
- **Circular Elements:** Reserved exclusively for status LED pips and radio selections. Pill shapes are forbidden to maintain an industrial instrument aesthetic.

## Components

### Buttons
- **Primary Action (e.g., 单次采集, 连续采集):** Background `#0284c7`, text `#ffffff`, border 1px solid `#0369a1`. Hover: `#0369a1`. Height 28px or 32px, font-size 13px, padding 0 12px.
- **Secondary Action (e.g., 校准暗电流, 导出CSV):** Background `#ffffff`, text `#334155`, border 1px solid `#cbd5e1`. Hover: `#f8fafc`.
- **Destructive/Halt (e.g., 停止采集):** Background `#ffffff`, text `#e11d48`, border 1px solid `#fecdd3`. Hover: `#fff1f2`.

### Telemetry Value Display Cards
- Background `#ffffff`, border 1px solid `#e2e8f0`. Padding 8px 12px.
- Layout: Top row contains micro-label in `Geist` (e.g., "PPFD (400-700nm)") in `#64748b`; main row contains numeric telemetry in `JetBrains Mono` bold 20px `#0f172a`, followed by inline unit designation (e.g., "µmol·m⁻²·s⁻¹") in `#64748b` 11px.

### Status Tags
- Height 20px, horizontal padding 6px, border-radius 2px, font-size 11px, font-weight 500.
- **采集成功:** Text `#065f46`, background `#ecfdf5`, border 1px solid `#a7f3d0`. Preceded by a 5px solid emerald dot.
- **复核未完成:** Text `#92400e`, background `#fffbeb`, border 1px solid `#fde68a`. Preceded by a 5px solid amber dot.
- **采集失败 / 饱和:** Text `#9f1239`, background `#fff1f2`, border 1px solid `#fecdd3`. Preceded by a 5px solid rose dot.

### Inputs & Number Steppers
- Height 28px, background `#ffffff`, border 1px solid `#cbd5e1`, text `#0f172a`, font-family `JetBrains Mono` 12px. 
- Stepper buttons are embedded 14px squares with crisp arrow glyphs. Focus state uses border color `#0284c7`.

### Spectrum Graph Container
- Canvas background `#ffffff`, bounded by a 1px solid `#cbd5e1` container.
- Gridlines: 1px dashed `#f1f5f9` with major intervals in `#e2e8f0`.
- Spectrum Line: 1.5px solid `#0284c7`. Optional overlay reference curve in `#94a3b8` 1px dotted.
- Scrub bar: Vertical 1px hairline in `#0f172a` with an attached dynamic tooltip displaying `λ: xxx.x nm | I: xxxx.xx µW/cm²/nm`.
