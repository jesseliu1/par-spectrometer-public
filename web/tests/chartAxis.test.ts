import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import OperationChart from "../src/components/OperationChart.vue";
import OverviewChart from "../src/components/OverviewChart.vue";
import SpectrumChart from "../src/components/SpectrumChart.vue";
import { axisNumber } from "../src/lib/axis";
import { responseAxis } from "../src/lib/spectrum";
import { operationPage, overview, referenceCurves } from "./fixtures";

// happy-dom has no canvas: ECharts is replaced by a recorder of the options the chart component sets
const charts = vi.hoisted(() => ({ options: [] as Record<string, unknown>[] }));
vi.mock("echarts/core", () => ({
  use: () => undefined,
  init: () => ({
    setOption: (option: Record<string, unknown>) => charts.options.push(option),
    resize: () => undefined,
    dispose: () => undefined,
  }),
}));

interface YAxis {
  min?: number;
  max?: number;
  axisLabel: { showMinLabel?: boolean; showMaxLabel?: boolean; formatter?: (value: number) => string };
}

function yAxes(): YAxis[] {
  const y = charts.options.at(-1)?.yAxis as YAxis | YAxis[];
  return Array.isArray(y) ? y : [y];
}

describe("value-axis tick text (issue 108)", () => {
  it("drops binary floating-point residue and keeps the decimals the value has", () => {
    // y ranges the service sent for sums and differences of the e2e demo spectra
    expect(axisNumber(2.0380000000000003)).toBe("2.038");
    expect(axisNumber(0.08399999999999999)).toBe("0.084");
    expect(axisNumber(-1.3940000000000001)).toBe("-1.394");
    expect(axisNumber(-2.5959999999999996)).toBe("-2.596");
    expect(axisNumber(0.1 + 0.2)).toBe("0.3");
    // ordinary ticks print as ECharts printed them, thousands separators included
    expect(["0", "0.5", "1.5", "0.0002", "0.00002", "1,050", "12,345.5"]).toEqual(
      [0, 0.5, 1.5, 0.0002, 0.00002, 1050, 12345.5].map(axisNumber),
    );
    expect(axisNumber(-0)).toBe("0");
    expect(axisNumber(1e-7)).toBe("0.0000001"); // never exponent notation
  });

  it("labels a sum's residual maximum as 2.038 without changing the axis range", () => {
    const range: [number, number] = [0, 2.0380000000000003];
    const axis = operationPage().axis;
    const props = { title: "计算结果", yRange: range, yLabel: "功率", xLabel: "波长", axis, values: [1, 2] };
    mount(OperationChart, { props: { ...props, testId: "chart-result" } });
    const [y] = yAxes();
    expect([y?.min, y?.max]).toEqual(range);
    expect(y?.axisLabel.showMaxLabel).toBe(true);
    expect(y?.axisLabel.formatter?.(2.0380000000000003)).toBe("2.038");
  });

  it("formats the y axes of the spectrum, overview and response axes the same way", () => {
    const spectrum = { wavelength_start: 350, wavelength_step: 1, spectral_coefficient: 3, points: [1], values: [1] };
    mount(SpectrumChart, { props: { spectrum, caption: "" } });
    expect(yAxes()[0]?.axisLabel.formatter).toBe(axisNumber);
    const data = overview();
    mount(OverviewChart, { props: { chart: data.chart, texts: data.texts, metricsVisible: true } });
    expect(yAxes()[0]?.axisLabel.formatter).toBe(axisNumber);
    expect((responseAxis(referenceCurves(), "", "") as YAxis).axisLabel.formatter).toBe(axisNumber);
  });
});
