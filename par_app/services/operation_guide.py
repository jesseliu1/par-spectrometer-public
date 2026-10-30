"""Texts of the spectrum calculation guide (光谱计算应用说明) for the ui-v2 local service (stage two, route C).

A copy, not a move: par_app/ui.py is frozen on the ui-v2 line (internal notes 1.2). The V1.0.3
panel (OperationGuideCanvas.__init__, the summary) and dialog (OperationGuideCanvas.show_details, the full guide)
build their HTML inline; here the same words are kept as data (paragraphs with an optional bold heading, sections
with an optional anchor, reference links), so the web page renders them without injecting HTML.
tests/api/test_operations_parity.py rebuilds the V1.0.3 HTML from these constants and compares it character for
character with what the V1.0.3 widgets are given, so the copies cannot drift apart unnoticed.

Specs: UI-226 (four summary paragraphs with bold inline headings), UI-229 (one title), UI-230/UI-250 (reference
links), UI-231 (four chapter links), UI-235..UI-249 (the content rules of the cases and reminders).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuideParagraph:
    head: str | None
    """Bold inline heading (V1.0.3 <b>…</b>), None for a plain paragraph."""
    text: str


@dataclass(frozen=True)
class GuideLink:
    text: str
    url: str


@dataclass(frozen=True)
class GuideSection:
    anchor: str | None
    """Target of a chapter link (V1.0.3 <a name>), None when the navigation does not point here."""
    title: str
    paragraphs: tuple[GuideParagraph, ...]
    links: tuple[GuideLink, ...] = ()


TITLE = "光谱计算应用说明"
"""Title of the panel and of the dialog (UI-229)."""
DETAILS_BUTTON = "查看完整说明…"
CLOSE_BUTTON = "关闭"
NAVIGATION: tuple[tuple[str, str], ...] = (
    ("补光", "lighting"),
    ("温室", "greenhouse"),
    ("叶片", "leaf"),
    ("显示与导出", "display"),
)
"""(text, anchor) of the four chapter links at the top of the dialog (UI-231)."""
DIALOG_WIDTH_PX = 960
DIALOG_HEIGHT_PX = 760
DIALOG_SCREEN_FRACTION = 0.9
"""UI-232: the dialog opens at 960×760 logical pixels, at most 90 % of the available width and height."""

SUMMARY: tuple[GuideParagraph, ...] = (
    GuideParagraph(
        '加法 A+B · 补光组合：',
        '同点测量两盏灯，估算组合光谱；避免重复计入背景。',
    ),
    GuideParagraph(
        '减法 A−B · 补光增量：',
        'A 开灯后、B 开灯前；背景需稳定，负值表示 B 较强。',
    ),
    GuideParagraph(
        '比值 A/B · 温室综合透光评估：',
        'A 室内、B 室外，观察太阳位置及天气变化下的测点透光表现；最近时间不等于同步。',
    ),
    GuideParagraph(
        '比值 A/B · 叶片光谱透射比较：',
        ('A 叶片覆盖、B 夹具空白，固定光源与几何条件；不直接代表吸收率。2% 筛选可能隐藏低透射区，空缺不代表零透射。'),
    ),
)
INTRO = (
    '本页对已选光谱逐波长执行 A+B、A−B 或 A/B。以下为应用方向和测量提醒，不是标准测试方法或精度保证。放置方式、校准及'
    '参考条件决定结果能如何解释。'
)
SECTIONS: tuple[GuideSection, ...] = (
    GuideSection(
        'lighting',
        '1. 加法 A+B：补光组合',
        (
            GuideParagraph(
                '来源与用途：',
                (
                    'A、B 分别为同一测点、同一接收方向下两盏灯的光谱，用于估算贡献可线性叠加时的组合照明。例如660 nm'
                    '处0.003+0.005=0.008 mW/nm，仅为示意数值。不同测点不能直接当作同一点的合成照明。'
                ),
            ),
            GuideParagraph(
                '条件与限制：',
                (
                    '光源和背景需稳定；若两次均含背景，相加会重复计入，应先处理背景。本页不会自动扣除背景。灯具同时开'
                    '启后的实际光谱仍应复测；此估算不适用于相干干涉。'
                ),
            ),
        ),
    ),
    GuideSection(
        None,
        '2. 减法 A−B：补光增量',
        (
            GuideParagraph(
                '来源与用途：',
                (
                    'A 为开灯后，B 为开灯前。固定位置和方向、背景稳定时，差值可观察补光贡献。例如450 nm处0.006−0.004='
                    '0.002 mW/nm。负值表示该波长 B 较强，不代表负光能。'
                ),
            ),
            GuideParagraph(
                '条件与限制：',
                (
                    '尽量缩短时间差，记录调光和遮阳状态。云影、日照变化及设备偏差也会进入差值，不能把所有变化都归因于'
                    '灯具；不应为得到正值而强行截零。'
                ),
            ),
        ),
    ),
    GuideSection(
        'greenhouse',
        '3. 比值 A/B：温室综合透光评估',
        (
            GuideParagraph(
                '来源与用途：',
                (
                    'A 为温室内光谱，B 为室外参考光谱。设备响应和接收条件可比时，A/B 可用于评估该测点、该时刻的有效光'
                    '谱透过率。0.8对应80%，1.2表示该波长相对参考高出20%，不代表总光量增加20%。本页按比值显示，不自动'
                    '转换为百分数。'
                ),
            ),
            GuideParagraph(
                '太阳位置与天空条件：',
                (
                    '连续比较早、中、晚及不同天气的记录，可观察太阳高度角、方位角、直射与散射比例变化，以及覆盖材料、'
                    '骨架、遮阳设施的共同作用。建议称为温室综合透光评估，不将它命名为材料的球面或半球透过率。一天只覆'
                    '盖当天太阳轨迹，不能覆盖整个天空半球；相同太阳方向在不同天空条件下也可能得到不同结果。仅凭两条光'
                    '谱不能分离直射、散射的贡献。'
                ),
            ),
            GuideParagraph(
                '测量布置：',
                (
                    '先将两台设备并排、同方向测量，检查逐波长响应差异；必要时交换位置复测。室外参考需无遮挡，两探头保'
                    '持相同接收方向并注意水平和角响应。方向相同也不保证角响应误差抵消，因为室内外光的方向分布不同。记'
                    '录室内测点、高度、天气和设施状态；评价围护结构时避免混入作物遮挡，关闭或单独记录室内补光。云影快'
                    '速移动时，数秒时间差也可能造成明显偏差。'
                ),
            ),
            GuideParagraph(
                '结果边界：',
                (
                    '单点不代表全温室平均，也不等同于覆盖材料本身的透过率。整体评价需多个代表性测点，考虑移动的骨架阴'
                    '影。局部比值超过100%时，检查补光、反射集中、时间错配和设备差异，不直接截断，也不能解释为材料透过'
                    '率超过100%。若另行统计全天透光率，应取同一有效时段内室内外累计光量之比，不是瞬时比值的简单平均；'
                    '需注明波段以及能量或光子计量方式。太阳方向分布图、空间平均和全天统计不由本页自动生成。'
                ),
            ),
        ),
    ),
    GuideSection(
        'leaf',
        '4. 比值 A/B：叶片光谱透射比较',
        (
            GuideParagraph(
                '来源与用途：',
                (
                    'A 为叶片贴近并覆盖接收口时的光谱，B 为同一光源、同一夹具未放叶片时的空白参考。固定测量条件，可比'
                    '较不同叶片或处理条件下的光谱透射差异；这是固定接收几何下的透射比。'
                ),
            ),
            GuideParagraph(
                '夹具与重复测量：',
                (
                    '叶片完全覆盖有效接收口并防止边缘漏光，空白参考保留同一夹具和开孔。避免夹压损伤，固定受光正反面、'
                    '测量位置和接触间距；一致处理主叶脉、表面水滴等因素。优先使用稳定光源，测量前后复测空白参考，检查'
                    '暗信号，并在多个叶片部位重复测量。尽量缩短离体叶片测量时间；使用两台设备时，还需区分设备响应差异'
                    '与叶片差异。'
                ),
            ),
            GuideParagraph(
                '散射与接收范围：',
                (
                    '叶片会散射光，贴近探头不保证收集全部透射光。结果受开孔、间距和探头角响应影响，不直接等同于总半球'
                    '透过率。测量总透射或反射通常需要积分球等适合收集散射光的装置。'
                ),
            ),
            GuideParagraph(
                '透射不等于吸收：',
                (
                    '在适用的能量收支条件下，吸收率 α(λ)=1−R(λ)−T(λ)，其中 R、T 应为对应条件下的总反射率和总透过率。'
                    '没有反射测量，不能把1−A/B标为叶片吸收率。−log10(T)也会混入反射及未接收到的散射等衰减，不能直接解'
                    '释为纯吸收。本页不计算吸收率或吸光度，也不自动完成暗信号、背景或设备响应校正。'
                ),
            ),
        ),
    ),
    GuideSection(
        'display',
        '5. 低信号、无效值与显示范围',
        (
            GuideParagraph(
                '2%显示筛选：',
                (
                    '共同阈值为2%×max(A全波段峰值,B全波段峰值)，峰值取350–1050 nm。仅当两谱均为有限正值且均达到阈值时'
                    '绘制比值，等于阈值保留，否则断线，不跨缺口连接。交换来源不改变共同阈值，加减法不筛选。该规则不是'
                    '检测下限、信噪比判据或精度保证。'
                ),
            ),
            GuideParagraph(
                '透射测量特别提醒：',
                (
                    '2%筛选可能隐藏真实的低透射区。曲线空缺不代表零透射，也不代表完全吸收。应结合暗信号、参考强度、重'
                    '复测量及导出标记判断；导出保留数值不意味着该数值具备测量可信度。B 接近零时，比值对噪声敏感，有限'
                    '高比值不会被截断。'
                ),
            ),
            GuideParagraph(
                '无效值：',
                (
                    'B=0时（包括0/0）、非有限输入或计算溢出均为NaN；A=0且B为非零有限值时为有效0。数学有效不等于测量可'
                    '靠。图中1倍虚线仅在纵轴范围内显示，不参与缩放。'
                ),
            ),
        ),
    ),
    GuideSection(
        None,
        '操作与导出规则',
        (
            GuideParagraph(
                '最近时间匹配：',
                (
                    '默认开启“B 匹配 A 的最近时间”。首次进入、主动改变 A 或改变 B 设备时，搜索当前 B 全库中时间最近的'
                    '成功完整 701 点记录。等距先选较早时间，再按记录 ID。不设置隐含时间容差，不修改设备时钟；最近不代'
                    '表同时采集。'
                ),
            ),
            GuideParagraph(
                None,
                (
                    '手动选择 B 不改变 A，后台刷新保留选择；下次主动改变 A 才重新跟随。关闭后独立选择，重新开启立即匹'
                    '配。交换精确互换设备、数据库和记录，不重新匹配。'
                ),
            ),
            GuideParagraph(
                '计算与显示：',
                (
                    '选择、交换记录或改变算法后需重新执行。A/B 按完整波段使用共同纵轴，结果独立缩放。图表、计算和导出'
                    '固定为350–1050 nm，保留完整701点。'
                ),
            ),
            GuideParagraph(
                '导出：',
                (
                    '执行后选择 CSV、Excel，可同时选择。用户指定父目录，每次建立独立结果目录，每种格式一个文件，包含'
                    '波长、A、B、结果及来源设备、数据库、记录 ID、时间、时间差、算法和零值规则。比值导出包含低信号标'
                    '记（1=未通过显示筛选、0=通过）、结果有效标记（1=有效、0=无效）及共同阈值元数据。被隐藏的有限计算'
                    '值仍完整保留，无效结果写为NaN，不应当作0。Excel分为计算数据和计算说明两张表，默认打开数据表，冻'
                    '结表头及波长列并支持筛选；说明表保留完整北京时间与来源。CSV保持说明在前、701点数据在后的结构，不'
                    '保存列宽或显示格式；表格软件可能自动识别时间，必要时按文本导入以保留原始显示。结果仅驻留会话，不'
                    '写入采集数据库。'
                ),
            ),
        ),
    ),
    GuideSection(
        None,
        '参考资料',
        (
            GuideParagraph(
                None,
                '以下为光学定义与测量原理参考；温室与夹具案例为应用建议，不作为标准方法认证。',
            ),
        ),
        (
            GuideLink('RP Photonics：Transmittance', 'https://www.rp-photonics.com/transmittance.html'),
            GuideLink('RP Photonics：Integrating Spheres', 'https://www.rp-photonics.com/integrating_spheres.html'),
            GuideLink('RP Photonics：Absorptance', 'https://www.rp-photonics.com/absorptance.html'),
            GuideLink('RP Photonics：Absorbance', 'https://www.rp-photonics.com/absorbance.html'),
        ),
    ),
)
