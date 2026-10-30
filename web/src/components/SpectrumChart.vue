<script setup lang="ts">
/**
 * The selected record's spectrum, 350–1050 nm, with the PAR band 400–700 nm shaded (UI-037: follows the
 * selection). Values are the service's `values`; colours come from tokens.css. Once API-08 is loaded the curve is
 * filled by wavelength (UI-317) and the four reference curves sit on a right axis with their legend (UI-168), as in
 * V1.0.3; the plain line stays, invisible, for the tooltip.
 */
import { CustomChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkAreaComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ReferenceCurves, Spectrum } from "../api/types";
import {
  axisRange,
  fillSeries,
  PAR_BAND_NM,
  referenceLegend,
  referenceSeries,
  responseAxis,
  spectrumSeries,
} from "../lib/spectrum";
import { axisNumber } from "../lib/axis";
import { token, tokenNumber } from "../lib/theme";
import { REFERENCE_CURVES } from "../pages/referenceStore";

use([CustomChart, LineChart, GridComponent, LegendComponent, MarkAreaComponent, TooltipComponent, CanvasRenderer]);

const props = defineProps<{ spectrum: Spectrum | null; caption: string }>();
const host = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let observer: ResizeObserver | null = null;
const reference = inject(REFERENCE_CURVES, null);

function option(spectrum: Spectrum | null, curves: ReferenceCurves | null) {
  const axis = token("--chart-axis");
  const grid = token("--chart-grid");
  const [min, max] = axisRange(spectrum);
  const fontSize = tokenNumber("--font-size-xs");
  const points = spectrumSeries(spectrum);
  const plot = { left: 64, top: 36, bottom: 40 };
  const coloured = spectrum !== null ? curves : null;
  const left = {
    type: "value",
    name: "光谱辐照度（W·m⁻²·nm⁻¹）",
    nameTextStyle: { color: axis, align: "left" },
    axisLine: { show: true, lineStyle: { color: axis } },
    axisLabel: { color: axis, formatter: axisNumber },
    splitLine: { lineStyle: { color: grid } },
  };
  const spectrumLine = token("--chart-spectrum");
  return {
    animation: false,
    textStyle: { fontFamily: token("--font-family"), fontSize },
    grid: { ...plot, right: coloured ? tokenNumber("--chart-response-axis-width") : 24 },
    ...(coloured ? { legend: referenceLegend(coloured, plot, axis, fontSize) } : {}),
    tooltip: {
      trigger: "axis",
      backgroundColor: token("--color-surface"),
      borderColor: token("--color-outline-variant"),
      textStyle: { color: token("--color-on-surface"), fontSize },
      valueFormatter: (value: unknown) => String(value),
    },
    xAxis: {
      type: "value",
      min,
      max,
      name: "波长（nm）",
      nameLocation: "middle",
      nameGap: 26,
      axisLine: { lineStyle: { color: axis } },
      axisLabel: { color: axis },
      splitLine: { lineStyle: { color: grid } },
    },
    yAxis: coloured ? [left, responseAxis(coloured, axis, grid)] : left,
    series: [
      {
        type: "line",
        name: "光谱",
        data: points,
        showSymbol: false,
        lineStyle: { color: spectrumLine, width: tokenNumber("--chart-line-width"), ...(coloured ? { opacity: 0 } : {}) },
        itemStyle: { color: spectrumLine },
        ...(coloured ? {} : { areaStyle: { color: token("--chart-spectrum-fill") } }),
        markArea: {
          silent: true,
          itemStyle: { color: token("--chart-par-band") },
          // with the reference legend in the top left corner the band label moves to the band's top right
          label: { color: token("--chart-par-label"), fontSize, position: coloured ? "insideTopRight" : "insideTop" },
          data: [[{ name: `PAR ${PAR_BAND_NM[0]}–${PAR_BAND_NM[1]} nm`, xAxis: PAR_BAND_NM[0] }, { xAxis: PAR_BAND_NM[1] }]],
        },
      },
      ...(coloured ? [fillSeries(points, coloured), ...referenceSeries(coloured)] : []),
    ],
  };
}

function redraw(): void {
  chart?.setOption(option(props.spectrum, reference?.state.data ?? null), { notMerge: true });
}

onMounted(() => {
  if (!host.value) return;
  chart = init(host.value);
  redraw();
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(host.value);
});

watch(() => [props.spectrum, reference?.state.data] as const, redraw);

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <section class="panel chart-panel">
    <header class="head">
      <h2 class="panel-title">光谱</h2>
      <span class="muted caption">{{ props.caption }}</span>
    </header>
    <div ref="host" class="chart" data-testid="spectrum-chart"></div>
  </section>
</template>

<style scoped>
.chart-panel {
  display: flex;
  flex-direction: column;
  padding: var(--space-2) var(--space-3);
  min-height: 0;
}
.head {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}
.caption {
  font-size: var(--font-size-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chart {
  flex: 1;
  min-height: 240px;
}
</style>
