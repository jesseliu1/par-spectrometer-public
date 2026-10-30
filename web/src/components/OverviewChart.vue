<script setup lang="ts">
/**
 * The overview spectrum (UI-057: fixed 350–1050 nm, no band choice) with the in-chart metrics card (UI-010, UI-060:
 * two left-aligned columns, 8 band values and 12 others; while the record has no entries, the four core readings).
 * The y axis runs from 0 to the service's y_max (peak at about 0.618 of the height, UI-175) and the x axis shows the
 * service's ticks. Without a spectrum the chart shows the service's empty title and the V1.0.3 empty texts (UI-054).
 * Colours come from tokens.css. Once API-08 is loaded the curve is filled by wavelength (UI-317) and the four
 * reference curves sit on a right axis with their legend (UI-168, UI-278), as on the history page; the plain line
 * stays, invisible, for the tooltip.
 */
import { CustomChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { OverviewChart, OverviewTexts } from "../api/types";
import {
  AXIS_END_NM,
  AXIS_START_NM,
  fillSeries,
  referenceLegend,
  referenceSeries,
  responseAxis,
  spectrumSeries,
} from "../lib/spectrum";
import { axisNumber } from "../lib/axis";
import { token, tokenNumber } from "../lib/theme";
import { REFERENCE_CURVES } from "../pages/referenceStore";

use([CustomChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const props = defineProps<{ chart: OverviewChart | null; texts: OverviewTexts | null; metricsVisible: boolean }>();
const host = ref<HTMLDivElement | null>(null);
let echart: ECharts | null = null;
let observer: ResizeObserver | null = null;

const spectrum = computed(() => props.chart?.spectrum ?? null);
const overlay = computed(() => (props.metricsVisible ? (props.chart?.overlay ?? []) : []));
const reference = inject(REFERENCE_CURVES, null);
/** The right response axis is drawn: the metrics card moves left of it. */
const withCurves = computed(() => spectrum.value !== null && (reference?.state.data ?? null) !== null);

function option() {
  const axis = token("--chart-axis");
  const grid = token("--chart-grid");
  const fontSize = tokenNumber("--font-size-xs");
  const ticks = props.chart?.x_ticks ?? [];
  const points = spectrumSeries(spectrum.value);
  const plot = { left: 72, top: 24, bottom: 44 };
  const coloured = spectrum.value ? (reference?.state.data ?? null) : null;
  const left = {
    type: "value",
    min: 0,
    max: props.chart?.y_max ?? undefined,
    name: props.texts?.y_label ?? "",
    nameTextStyle: { color: axis, align: "left" },
    axisLine: { show: true, lineStyle: { color: axis } },
    // the top is the service's y_max (peak / 0.618), rarely a round number: label the even steps below it
    axisLabel: { color: axis, showMaxLabel: false, formatter: axisNumber },
    splitLine: { lineStyle: { color: grid } },
  };
  const line = token("--chart-spectrum");
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
      min: AXIS_START_NM,
      max: AXIS_END_NM,
      name: props.texts?.x_label ?? "",
      nameLocation: "middle",
      nameGap: 28,
      nameTextStyle: { color: axis },
      axisLine: { lineStyle: { color: axis } },
      axisTick: { customValues: ticks },
      axisLabel: { customValues: ticks, color: axis, formatter: (value: number) => String(value) },
      splitLine: { lineStyle: { color: grid } },
    },
    yAxis: coloured ? [left, responseAxis(coloured, axis, grid)] : left,
    series: spectrum.value
      ? [
          {
            type: "line",
            name: "实测光谱",
            data: points,
            showSymbol: false,
            lineStyle: { color: line, width: tokenNumber("--chart-line-width"), ...(coloured ? { opacity: 0 } : {}) },
            itemStyle: { color: line },
            ...(coloured ? {} : { areaStyle: { color: token("--chart-spectrum-fill") } }),
          },
          ...(coloured ? [fillSeries(points, coloured), ...referenceSeries(coloured)] : []),
        ]
      : [],
  };
}

onMounted(() => {
  if (!host.value) return;
  echart = init(host.value);
  echart.setOption(option());
  observer = new ResizeObserver(() => echart?.resize());
  observer.observe(host.value);
});

watch(
  () => [props.chart, props.texts, reference?.state.data] as const,
  () => echart?.setOption(option(), { notMerge: true }),
);

onBeforeUnmount(() => {
  observer?.disconnect();
  echart?.dispose();
  echart = null;
});
</script>

<template>
  <div class="chart-wrap">
    <div ref="host" class="chart" data-testid="overview-chart"></div>
    <div v-if="!spectrum && props.chart" class="empty" data-role="chart-empty">
      <strong class="empty-title">{{ props.chart.title }}</strong>
      <span class="muted">{{ props.texts?.empty_heading }}</span>
      <span class="muted small">{{
        props.chart.spectrum_state === "invalid" ? props.texts?.invalid_spectrum : props.texts?.empty_detail
      }}</span>
    </div>
    <div
      v-if="overlay.length"
      class="overlay numeric"
      :class="{ 'beside-axis': withCurves }"
      data-role="overlay"
    >
      <dl v-for="(column, index) in overlay" :key="index" class="column">
        <div v-for="row in column" :key="row.label" class="row">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.text }}</dd>
        </div>
      </dl>
    </div>
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
}
.chart {
  flex: 1;
  min-height: 300px;
}
.empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  pointer-events: none;
}
.empty-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-medium);
}
.small {
  font-size: var(--font-size-sm);
}
.overlay {
  position: absolute;
  top: var(--space-5);
  right: var(--space-5);
  display: flex;
  gap: var(--space-4);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border: var(--border-width) solid var(--color-outline);
  border-radius: var(--radius-control);
  font-size: var(--font-size-xs);
  line-height: 1.5;
  pointer-events: none;
}
.overlay.beside-axis {
  right: var(--chart-response-axis-width);
}
/* each column left-aligned, values lined up after the column's widest label (SpectrumCanvas._draw_core_metrics_card) */
.column {
  margin: 0;
  display: grid;
  grid-template-columns: max-content max-content;
  column-gap: var(--space-2);
  align-content: start;
}
.row {
  display: contents;
}
.row dt {
  font-family: var(--font-family);
  color: var(--color-on-surface-variant);
}
.row dd {
  margin: 0;
}
</style>
