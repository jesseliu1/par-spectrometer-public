<script setup lang="ts">
/**
 * The calibration preview (V1.0.3 CalibrationCanvas): the combined correction the MCU applies per wavelength, the
 * hardware limit band and the five draggable nodes P0..P4. Every number is the service's (17_ 3.3: the page computes
 * nothing); a drag only moves the marker under the pointer and, on release, sends the node and the point where it was
 * dropped. The service clamps it (dragged_node) and recomputes the values (node_values), as V1.0.3 does.
 */
import { LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, MarkAreaComponent, MarkLineComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { CalibrationCurve } from "../api/types";
import { token, tokenNumber } from "../lib/theme";

use([LineChart, ScatterChart, GridComponent, MarkAreaComponent, MarkLineComponent, CanvasRenderer]);

/** A press this close (px) to a node grabs it (V1.0.3: PICK_RADIUS in axes units, similar on screen). */
const PICK_PX = 14;
const X_RANGE: [number, number] = [350, 1050];

const props = defineProps<{ curve: CalibrationCurve | null; editable: boolean; message: string | null }>();
const emit = defineEmits<{ drag: [index: number, x: number, y: number] }>();
const host = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let observer: ResizeObserver | null = null;
let dragging: number | null = null;
let nodes: [number, number][] = [];

function yRange(curve: CalibrationCurve): [number, number] {
  const values = [...curve.y, curve.limit_min_percent, curve.limit_max_percent];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const pad = Math.max((high - low) * 0.12, 2);
  return [low - pad, high + pad];
}

function option(curve: CalibrationCurve | null) {
  const axis = token("--chart-axis");
  const fontSize = tokenNumber("--font-size-xs");
  nodes = curve ? curve.nodes.map(([x, y]) => [x, y] as [number, number]) : [];
  const [yMin, yMax] = curve ? yRange(curve) : [-20, 20];
  return {
    animation: false,
    textStyle: { fontFamily: token("--font-family"), fontSize },
    grid: { left: 56, right: 24, top: 20, bottom: 40 },
    xAxis: {
      type: "value",
      min: X_RANGE[0],
      max: X_RANGE[1],
      name: "波长 (nm)",
      nameLocation: "middle",
      nameGap: 26,
      axisLine: { lineStyle: { color: axis } },
      axisLabel: { color: axis },
      splitLine: { lineStyle: { color: token("--chart-grid") } },
    },
    yAxis: {
      type: "value",
      min: yMin,
      max: yMax,
      name: "综合校准修正（%）",
      nameTextStyle: { color: axis, align: "left" },
      axisLine: { show: true, lineStyle: { color: axis } },
      axisLabel: { color: axis, formatter: (value: number) => value.toFixed(1) },
      splitLine: { lineStyle: { color: token("--chart-grid") } },
    },
    series: curve
      ? [
          {
            type: "line",
            name: "综合校准修正（已限幅）",
            data: curve.x.map((x, index) => [x, curve.y[index]]),
            showSymbol: false,
            lineStyle: { color: token("--chart-calibration"), width: 2 },
            markArea: {
              silent: true,
              itemStyle: { color: token("--chart-calibration-band") },
              data: [[{ yAxis: curve.limit_min_percent }, { yAxis: curve.limit_max_percent }]],
            },
            markLine: {
              silent: true,
              symbol: "none",
              lineStyle: { color: token("--chart-calibration-limit"), type: "dashed" },
              label: { show: false },
              data: [{ yAxis: curve.limit_min_percent }, { yAxis: curve.limit_max_percent }],
            },
          },
          {
            type: "scatter",
            name: "可拖拽综合修正点",
            data: nodes.map(([x, y], index) => ({ value: [x, y], name: `P${index}` })),
            symbolSize: 12,
            itemStyle: { color: token("--chart-calibration-node") },
            label: { show: true, formatter: "{b}", position: "top", color: axis, fontSize },
            z: 3,
          },
        ]
      : [],
  };
}

function nearest(px: number, py: number): number | null {
  if (!chart || !props.editable) return null;
  let best: number | null = null;
  let distance = PICK_PX;
  nodes.forEach((node, index) => {
    const point = chart?.convertToPixel({ seriesIndex: 1 }, node) as number[] | undefined;
    if (!point) return;
    const d = Math.hypot(point[0]! - px, point[1]! - py);
    if (d <= distance) {
      distance = d;
      best = index;
    }
  });
  return best;
}

function dataAt(px: number, py: number): [number, number] | null {
  const value = chart?.convertFromPixel({ seriesIndex: 1 }, [px, py]) as number[] | undefined;
  return value && Number.isFinite(value[0]) && Number.isFinite(value[1]) ? [value[0]!, value[1]!] : null;
}

function onDown(event: { offsetX: number; offsetY: number }): void {
  dragging = nearest(event.offsetX, event.offsetY);
}

function onMove(event: { offsetX: number; offsetY: number }): void {
  if (dragging === null || !chart) return;
  const point = dataAt(event.offsetX, event.offsetY);
  if (point === null) return;
  nodes[dragging] = point; // preview only; the service decides where the node ends up
  chart.setOption({ series: [{}, { data: nodes.map(([x, y], index) => ({ value: [x, y], name: `P${index}` })) }] });
}

function onUp(event: { offsetX: number; offsetY: number }): void {
  const index = dragging;
  dragging = null;
  if (index === null) return;
  const point = dataAt(event.offsetX, event.offsetY);
  if (point !== null) emit("drag", index, point[0], point[1]);
}

onMounted(() => {
  if (!host.value) return;
  chart = init(host.value);
  chart.setOption(option(props.curve));
  const zr = chart.getZr?.();
  zr?.on("mousedown", onDown);
  zr?.on("mousemove", onMove);
  zr?.on("mouseup", onUp);
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(host.value);
});

watch(
  () => props.curve,
  (curve) => chart?.setOption(option(curve), { notMerge: true }),
);

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="calibration-chart" data-role="calibration-chart" :class="{ editable: props.editable }">
    <div ref="host" class="chart"></div>
    <p v-if="props.message" class="message" data-role="calibration-chart-message">{{ props.message }}</p>
  </div>
</template>

<style scoped>
.calibration-chart {
  position: relative;
}
.chart {
  height: 300px;
}
.editable .chart {
  cursor: grab;
}
.message {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  color: var(--color-on-surface-variant);
}
</style>
