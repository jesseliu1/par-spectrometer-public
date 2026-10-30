<script setup lang="ts">
/**
 * One DLI chart (UI-179..184): the title on the left and the total on the right outside the plot (UI-180), then
 * state, times and coverage (UI-181; coverage tooltip DLI-053), then the cumulative curve. The y axis starts at
 * zero (UI-184), the x axis spans the whole period with the service's ticks (UI-183), and the curve breaks where
 * the service sent null (DLI-049). When the midnight label overlaps its neighbour it moves down one row (UI-185,
 * issue 108): a second, line-less x axis offset by STAGGER_PX carries it, and the chart grows by the same height as
 * V1.0.3's canvas does. Texts and numbers are the service's; colours come from tokens.css.
 */
import { LineChart } from "echarts/charts";
import { GridComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { DliMetric, DliTick } from "../api/types";
import { axisNumber } from "../lib/axis";
import {
  axisEnd,
  curve,
  measuredLabelWidth,
  METRIC_COLOURS,
  midnightIndex,
  midnightStagger,
  STAGGER_PX,
  STATE_CLASSES,
  tickText,
  visibleTicks,
  WIDE_CHART_PX,
  type MidnightStagger,
} from "../lib/dli";
import { token, tokenNumber } from "../lib/theme";

use([LineChart, GridComponent, CanvasRenderer]);

const props = defineProps<{ metric: DliMetric; ticks: DliTick[] }>();
const host = ref<HTMLDivElement | null>(null);
const width = ref(0);
let chart: ECharts | null = null;
let observer: ResizeObserver | null = null;

/** Plot area inside the chart: grid.left and grid.right of option(). */
const GRID = { left: 64, right: 24, top: 16, bottom: 48 };
const NAME_GAP = 36;

const stateClass = computed(() => STATE_CLASSES[props.metric.header.state_level]);
const noData = computed(() => props.metric.summary.covered_seconds === 0);

/** UI-185 for the current width: whether, and to which side, the midnight label moves down one row. */
function staggerAt(chartWidth: number): MidnightStagger {
  const labelWidth = measuredLabelWidth(tokenNumber("--font-size-xs"), token("--font-family"));
  return midnightStagger(visibleTicks(props.ticks, chartWidth), chartWidth - GRID.left - GRID.right, labelWidth);
}
const stagger = ref<MidnightStagger>(null);
/** UI-185: one label row more below the axis, as V1.0.3's canvas grows from 210 to 236 px. */
const hostStyle = computed(() =>
  stagger.value ? { height: `calc(var(--dli-chart-height) + ${STAGGER_PX}px)` } : undefined,
);

function option() {
  const axis = token("--chart-axis");
  const grid = token("--chart-grid");
  const colours = METRIC_COLOURS[props.metric.key] ?? { line: "--chart-spectrum", fill: "--chart-spectrum-fill" };
  const fontSize = tokenNumber("--font-size-xs");
  const ticks = visibleTicks(props.ticks, width.value);
  const offsets = ticks.map((tick) => tick.offset_seconds);
  const moved = stagger.value;
  const midnight = moved ? ticks[midnightIndex(ticks)] : undefined;
  const drop = midnight ? STAGGER_PX : 0;
  const end = axisEnd(props.ticks);
  // UI-185: the staggered midnight label, one row lower on a second x axis without line or ticks
  const staggered = midnight
    ? [
        {
          type: "value",
          min: 0,
          max: end,
          position: "bottom",
          offset: STAGGER_PX,
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: {
            customValues: [midnight.offset_seconds],
            color: axis,
            align: moved,
            formatter: () => midnight.text,
          },
        },
      ]
    : [];
  return {
    animation: false,
    textStyle: { fontFamily: token("--font-family"), fontSize },
    grid: { ...GRID, bottom: GRID.bottom + drop },
    xAxis: [
      {
        type: "value",
        min: 0,
        max: end,
        name: "北京时间",
        nameLocation: "middle",
        nameGap: NAME_GAP + drop,
        nameTextStyle: { color: axis },
        axisLine: { lineStyle: { color: axis } },
        axisTick: { customValues: offsets },
        axisLabel: {
          customValues: offsets,
          color: axis,
          alignMinLabel: "left",
          alignMaxLabel: "right",
          formatter: (value: number) =>
            midnight && value === midnight.offset_seconds ? "" : tickText(props.ticks, value),
        },
        splitLine: { show: false },
      },
      ...staggered,
    ],
    yAxis: {
      type: "value",
      min: 0,
      max: props.metric.y_max,
      name: "累计光积分（mol·m⁻²）",
      nameTextStyle: { color: axis, align: "left" },
      axisLine: { show: true, lineStyle: { color: axis } },
      // the top is the service's y_max (total × 1.15), rarely a round number: label only the even steps below it
      axisLabel: { color: axis, showMaxLabel: false, formatter: axisNumber },
      splitLine: { lineStyle: { color: grid } },
    },
    series: noData.value
      ? []
      : [
          {
            type: "line",
            data: curve(props.metric.series),
            connectNulls: false,
            showSymbol: false,
            silent: true,
            lineStyle: { color: token(colours.line), width: tokenNumber("--chart-dli-line-width") },
            itemStyle: { color: token(colours.line) },
            areaStyle: { color: token(colours.fill) },
          },
        ],
  };
}

function draw(): void {
  stagger.value = staggerAt(width.value);
  chart?.setOption(option(), { notMerge: true });
}

onMounted(() => {
  if (!host.value) return;
  width.value = host.value.clientWidth;
  chart = init(host.value);
  draw();
  observer = new ResizeObserver(() => {
    const now = host.value?.clientWidth ?? 0;
    const crossed = now >= WIDE_CHART_PX !== width.value >= WIDE_CHART_PX;
    width.value = now;
    chart?.resize();
    if (crossed || staggerAt(now) !== stagger.value) draw();
  });
  observer.observe(host.value);
});

watch(() => [props.metric, props.ticks], draw);

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <article class="panel dli-chart" :data-key="props.metric.key">
    <header class="head">
      <h3 class="title">{{ props.metric.title }}</h3>
      <span class="total numeric">{{ props.metric.header.total_text }}</span>
    </header>
    <p class="state" :class="stateClass" data-role="state">{{ props.metric.header.state_text }}</p>
    <p class="muted line numeric" data-role="times">{{ props.metric.header.times_text }}</p>
    <p class="muted line numeric" data-role="coverage" :title="props.metric.header.coverage_tooltip">
      {{ props.metric.header.coverage_text }}
    </p>
    <div class="plot">
      <div ref="host" class="chart" :style="hostStyle" data-testid="dli-chart"></div>
      <span v-if="noData" class="no-data muted">有效数据不足</span>
    </div>
  </article>
</template>

<style scoped>
.dli-chart {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  min-width: 0;
}
/* UI-180: name left, total right; when too narrow they wrap onto two lines */
.head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  column-gap: var(--space-3);
}
.title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-medium);
}
.total {
  font-size: var(--font-size-kpi);
  font-weight: var(--font-weight-medium);
}
.state,
.line {
  margin: 0;
  font-size: var(--font-size-sm);
}
.state-ok {
  color: var(--color-success);
}
.state-warn {
  color: var(--color-warning);
}
.state-muted {
  color: var(--color-on-surface-variant);
}
.plot {
  position: relative;
  flex: 1;
}
.chart {
  height: var(--dli-chart-height);
}
.no-data {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
</style>
