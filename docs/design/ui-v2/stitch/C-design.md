<!-- 来源：Google Stitch 项目 projects/<id> 的设计系统 "Control Room Dark"（assets/15814385525623149752），2026-10-18 由 create_design_system 创建后原样导出。
     对应方向 C「控制室暗色」，屏幕 projects/<id>/screens/b9361c848c604a06953c567be94570d5。
     取值来自 docs/design/ui-v2-pages.md 第 3.4 节的 C 列。Stitch 保存时丢掉了 headlineFont / bodyFont / labelFont 字段（创建时填的是 NOTO_SANS / NOTO_SANS / JETBRAINS_MONO）。
     这是 Stitch 的设计说明，不是本项目已采纳的令牌，待负责人选定方向后再定稿。 -->

---
name: Control Room Dark
theme:
  colorMode: DARK
  colorVariant: FIDELITY
  customColor: '#22D3EE'
  overridePrimaryColor: '#22D3EE'
  overrideSecondaryColor: '#38BDF8'
  overrideTertiaryColor: '#A78BFA'
  overrideNeutralColor: '#0F172A'
  roundness: ROUND_FOUR
---

# Control Room Dark

Desktop software for a PAR spectrometer monitored around the clock in a dim control room by duty operators.

## Colors
- Background #0F172A, panels #1E293B, borders #334155, chart grid #1F2A44.
- Text #E2E8F0, muted #94A3B8. Accent cyan #22D3EE, accent fill #164E63.
- Status: warning #FBBF24, fault #F87171, disabled #64748B, maintenance #C4B5FD. Normal uses body text colour. All text and status colours must pass WCAG AA on #1E293B.
- No pure white large areas; avoid glare during long shifts.

## Typography
- Noto Sans SC; numbers tabular (JetBrains Mono for numeric readouts). Body 14px, table 13px, section 16px, page title 20px, KPI 32px.

## Shape & spacing
- 4px controls, 6px cards, 32px controls, 28px table rows, 4px spacing grid. Flat, no shadows, 1px borders. Status bar always visible.
