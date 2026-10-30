<script setup lang="ts">
/**
 * One chart of the spectrum calculation page: A, B or the result (UI-189). The title sits above the plot,
 * centred on the whole panel (UI-215); every chart spans 350–1050 nm with the service's tick set for its width
 * (UI-192..UI-194). The y range is the service's: A and B share one (UI-209), the result has its own (UI-214) and
 * shows no y labels while waiting (UI-212). A ratio is a plain line without fill (UI-223) that breaks at null
 * points (UI-218), with the dashed 1× line only when the service says it lies in range (UI-220). Empty states and
 * notes are the service's texts. Colours come from tokens.css. Once API-08 is loaded, A, B and a sum or difference
 * are filled by wavelength like V1.0.3 (UI-317), with no reference curves (V1.0.3 draws none on this page); the plain
 * line stays, invisible, for the tooltip and the 1× line.
 */
import { CustomChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { OperationAxis, Range } from "../api/types";
import { chartPoints, isRound, ticksFor } from "../lib/operations";
import { fillSeries } from "../lib/spectrum";
import { axisNumber } from "../lib/axis";
import { token, tokenNumber } from "../lib/theme";
import { REFERENCE_CURVES } from "../pages/referenceStore";

use([CustomChart, LineChart, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, CanvasRenderer]);

const props = withDefaults(
  defineProps<{
    title: string;
    values: (number | null)[] | null;
    yRange: Range | null;
    yLabel: string;
    xLabel: string;
    axis: OperationAxis;
    legend?: string | null;
    variant?: "input" | "result";
    ratio?: boolean;
    referenceLine?: boolean;
    note?: string | null;
    centerText?: string | null;
    emptyHeading?: string | null;
    emptyDetail?: string | null;
    hideYLabels?: boolean;
    testId: string;
  }>(),
  {
    legend: null,
    variant: "input",
    ratio: false,
    referenceLine: false,
    note: null,
    centerText: null,
    emptyHeading: null,
    emptyDetail: null,
    hideYLabels: false,
  },
);
const host = ref<HTMLDivElement | null>(null);
const width = ref(0);
let chart: ECharts | null = null;
let observer: ResizeObserver | null = null;
const reference = inject(REFERENCE_CURVES, null);

function option() {
  const axis = token("--chart-axis");
  const grid = token("--chart-grid");
  const line = token(props.variant === "result" ? "--chart-result" : "--chart-spectrum");
  const fill = token(props.variant === "result" ? "--chart-result-fill" : "--chart-spectrum-fill");
  const fontSize = tokenNumber("--font-size-xs");
  const ticks = ticksFor(props.axis, width.value);
  const [min, max] = props.yRange ?? [0, 1];
  const shown = props.values !== null;
  const points = chartPoints(props.values, props.axis.start_nm);
  const coloured = shown && !props.ratio ? (reference?.state.data ?? null) : null;
  return {
    animation: false,
    textStyle: { fontFamily: token("--font-family"), fontSize },
    grid: { left: 64, right: 24, top: 28, bottom: 44 },
    legend: {
      show: shown && props.legend !== null,
      data: props.legend !== null ? [props.legend] : [],
      right: 8,
      top: 0,
      textStyle: { color: axis, fontSize },
    },
    tooltip: {
      trigger: "axis",
      show: shown,
      backgroundColor: token("--color-surface"),
      borderColor: token("--color-outline-variant"),
      textStyle: { color: token("--color-on-surface"), fontSize },
      valueFormatter: (value: unknown) => (value === null || value === undefined ? "—" : String(value)),
    },
    xAxis: {
      type: "value",
      min: props.axis.start_nm,
      max: props.axis.end_nm,
      name: props.xLabel,
      nameLocation: "middle",
      nameGap: 26,
      nameTextStyle: { color: axis },
      axisLine: { lineStyle: { color: axis } },
      axisTick: { customValues: ticks },
      axisLabel: { customValues: ticks, color: axis },
      splitLine: { show: true, lineStyle: { color: grid } },
    },
    yAxis: {
      type: "value",
      min,
      max,
      name: props.hideYLabels ? "" : props.yLabel,
      nameTextStyle: { color: axis, align: "left" },
      axisLine: { show: true, lineStyle: { color: axis } },
      axisTick: { show: !props.hideYLabels },
      // the service's range ends are rarely round numbers (e.g. a ratio's padded minimum): label them only when
      // they are, like Matplotlib's ticks in V1.0.3, so no long decimals sit on the axis; an end that is round but
      // for binary residue (a sum's maximum doubled, 2.0380000000000003) is printed without it (issue 108)
      axisLabel: {
        show: !props.hideYLabels,
        color: axis,
        showMinLabel: isRound(min),
        showMaxLabel: isRound(max),
        formatter: axisNumber,
      },
      splitLine: { show: !props.hideYLabels, lineStyle: { color: grid } },
    },
    series: shown
      ? [
          {
            type: "line",
            name: props.legend ?? "",
            data: points,
            connectNulls: false,
            showSymbol: false,
            lineStyle: { color: line, width: tokenNumber("--chart-line-width"), ...(coloured ? { opacity: 0 } : {}) },
            itemStyle: { color: line },
            ...(props.ratio || coloured ? {} : { areaStyle: { color: fill, origin: "auto" } }),
            markLine: props.referenceLine
              ? {
                  silent: true,
                  symbol: "none",
                  label: { show: false },
                  lineStyle: { color: token("--chart-reference"), type: "dashed", width: 1 },
                  data: [{ yAxis: 1 }],
                }
              : undefined,
          },
          ...(coloured ? [fillSeries(points, coloured)] : []),
        ]
      : [],
  };
}

function redraw(): void {
  chart?.setOption(option(), { notMerge: true });
}

onMounted(() => {
  if (!host.value) return;
  chart = init(host.value);
  width.value = host.value.clientWidth;
  chart.setOption(option());
  observer = new ResizeObserver(() => {
    const next = host.value?.clientWidth ?? 0;
    chart?.resize();
    if (ticksFor(props.axis, next) !== ticksFor(props.axis, width.value)) {
      width.value = next;
      redraw();
    } else {
      width.value = next;
    }
  });
  observer.observe(host.value);
});

watch(
  () => [
    props.values,
    props.yRange,
    props.ratio,
    props.referenceLine,
    props.hideYLabels,
    props.legend,
    props.yLabel,
    reference?.state.data,
  ],
  redraw,
);

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <section class="panel chart-panel">
    <h2 class="chart-title" :data-testid="`${props.testId}-title`">{{ props.title }}</h2>
    <div class="plot">
      <div ref="host" class="chart" :data-testid="props.testId"></div>
      <p v-if="props.note" class="note">{{ props.note }}</p>
      <div v-if="props.values === null && props.emptyHeading" class="empty" :data-testid="`${props.testId}-empty`">
        <strong>{{ props.emptyHeading }}</strong>
        <span v-if="props.emptyDetail" class="muted">{{ props.emptyDetail }}</span>
      </div>
      <p v-else-if="props.centerText" class="center">{{ props.centerText }}</p>
    </div>
  </section>
</template>

<style scoped>
.chart-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  padding: var(--space-2) var(--space-3);
}
.chart-title {
  margin: 0;
  text-align: center;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-medium);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plot {
  position: relative;
  flex: 1;
  min-height: var(--operation-chart-min-height);
}
.chart {
  position: absolute;
  inset: 0;
}
.note {
  position: absolute;
  top: var(--space-6);
  left: calc(64px + var(--space-2));
  margin: 0;
  padding: 0 var(--space-1);
  font-size: var(--font-size-xs);
  background: var(--color-surface);
  color: var(--color-on-surface);
}
.empty,
.center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  margin: 0;
  pointer-events: none;
  text-align: center;
}
.empty strong {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-regular);
  color: var(--color-on-surface-variant);
}
.empty span {
  font-size: var(--font-size-sm);
}
.center {
  font-size: var(--font-size-md);
}
</style>
