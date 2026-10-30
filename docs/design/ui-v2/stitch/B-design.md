<!-- 来源：Google Stitch 项目 projects/<id> 的设计系统 "Greenhouse Field"（assets/6529060157490922311），2026-10-18 由 create_design_system 创建后原样导出。
     对应方向 B「温室田间」，屏幕 projects/<id>/screens/3449e84ff1fe40c595b05083a5bb4714。
     取值来自 docs/design/ui-v2-pages.md 第 3.4 节的 B 列。Stitch 保存时丢掉了 headlineFont / bodyFont 两个字段（创建时填的是 NOTO_SANS），
     所以 B.png 的中文标题和数字回退成了衬线字体，这是生成问题，不代表方向 B 的字体。
     这是 Stitch 的设计说明，不是本项目已采纳的令牌，待负责人选定方向后再定稿。 -->

---
name: Greenhouse Field
theme:
  colorMode: LIGHT
  colorVariant: FIDELITY
  customColor: '#2F7D32'
  overridePrimaryColor: '#2F7D32'
  overrideSecondaryColor: '#8D6E4A'
  overrideTertiaryColor: '#0E7490'
  overrideNeutralColor: '#5B6656'
  labelFont: IBM Plex Sans
  roundness: ROUND_EIGHT
---

# Greenhouse Field

Desktop / touch all-in-one software for a PAR spectrometer used on greenhouse floors and in the field. Users are growers, not engineers.

## Colors
- Page background warm off-white #FAF8F3; panels #FFFFFF; borders #E7E2D6 (earthy sand).
- Text #1F2A1F, muted #5B6656. Primary leaf green #2F7D32, weak green fill #E3F1DF. Secondary earth brown #8D6E4A.
- Status: warning amber #B45309, fault #C62828, disabled #A8A29E. Normal state uses body text colour.
- High contrast for strong daylight: body text must reach WCAG AA on every surface, avoid pale grey text on white.

## Typography
- Noto Sans SC throughout; numbers tabular. Body 16px, table 15px, section title 20px, page title 26px, KPI value 40px bold.

## Shape & spacing
- 8px controls, 12px cards. Controls 44px tall (touch). Table rows 40px. Spacing 8/12/16/24/32/48.
- Large KPI cards for PPFD and DLI; generous padding; no decorative imagery.
