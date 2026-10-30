<script setup lang="ts">
/**
 * 光谱计算 (docs/design/ui-v2-pages.md 2.4), read only. Two control rows (UI-188): A's source and record, the
 * swap button, B's source and record; then the nearest-time option, the operation, the time difference, 执行计算
 * and 导出计算结果. The rows wrap instead of squeezing controls when the window is narrow (UI-190). Below, four
 * areas (UI-189): A and B, the result and the guide. Every list, number and text comes from the service
 * (calcStore.ts); a failed request keeps what is shown and offers a retry (R-1-5).
 */
import { computed, ref } from "vue";
import ErrorNotice from "../components/ErrorNotice.vue";
import ExportDialog from "../components/ExportDialog.vue";
import OperationChart from "../components/OperationChart.vue";
import OperationGuide from "../components/OperationGuide.vue";
import type { ExportKind, OperationKey, OperationSourceItem } from "../api/types";
import { options, type CalcStore, type SideKey } from "./calcStore";

const props = defineProps<{ store: CalcStore }>();
const state = props.store.state;
const page = computed(() => state.page.data);
const texts = computed(() => page.value?.texts ?? null);
const sources = computed<OperationSourceItem[]>(() => state.sources.data?.items ?? []);
const inputs = computed(() => state.inputs.data);
const result = computed(() => state.result);
const exportOpen = ref(false);
const runEnabled = computed(() => props.store.canRun());
const SIDES: SideKey[] = ["a", "b"];

function sourceTooltip(key: string | null): string {
  return sources.value.find((item) => item.key === key)?.tooltip ?? "";
}

function onSource(which: SideKey, event: Event): void {
  void props.store.setSource(which, (event.target as HTMLSelectElement).value);
}

function onRecord(which: SideKey, event: Event): void {
  void props.store.setRecord(which, Number((event.target as HTMLSelectElement).value));
}

function onOperation(event: Event): void {
  props.store.setOperation((event.target as HTMLSelectElement).value as OperationKey);
}

function onAutoMatch(event: Event): void {
  void props.store.setAutoMatch((event.target as HTMLInputElement).checked);
}

async function onExport(formats: ExportKind[]): Promise<void> {
  exportOpen.value = false;
  await props.store.exportResult(formats);
}

const resultPlaceholder = computed(() => inputs.value?.placeholder ?? null);
const keepingInputs = computed(() =>
  inputs.value ? `仍显示上次读取的光谱（${inputs.value.a.title}；${inputs.value.b.title}）` : null,
);
</script>

<template>
  <main class="calc">
    <ErrorNotice
      :error="state.page.error ?? state.sources.error"
      :keeping="state.sources.data ? '来源清单为上次读取的结果' : null"
      :busy="state.page.loading || state.sources.loading"
      @retry="props.store.show()"
    />
    <p v-if="state.sources.data && sources.length === 0 && texts" class="muted empty-sources">{{ texts.empty_sources }}</p>

    <section v-if="texts && page" class="panel toolbar" aria-label="选择与执行">
      <div class="row">
        <template v-for="(which, index) in SIDES" :key="which">
          <button
            v-if="index === 1"
            type="button"
            class="swap"
            :title="texts.swap_tooltip"
            :aria-label="texts.swap_tooltip"
            :disabled="!runEnabled"
            data-testid="swap"
            @click="props.store.swap()"
          >
            ⇄
          </button>
          <div class="source" :data-side="which">
            <span class="side-label">{{ texts.source_labels[index] }}</span>
            <select
              :value="state[which].source ?? ''"
              :title="sourceTooltip(state[which].source)"
              :aria-label="`${texts.source_labels[index]} 数据库`"
              :disabled="sources.length === 0"
              :data-testid="`${which}-source`"
              @change="onSource(which, $event)"
            >
              <option v-for="item in sources" :key="item.key" :value="item.key" :title="item.tooltip">
                {{ item.device_name }}
              </option>
            </select>
            <select
              class="record numeric"
              :value="state[which].selected ?? ''"
              :aria-label="`${texts.source_labels[index]} 记录`"
              :disabled="options(state[which]).length === 0"
              :data-testid="`${which}-record`"
              @change="onRecord(which, $event)"
            >
              <option v-if="options(state[which]).length === 0" value="">{{ texts.no_spectrum }}</option>
              <option v-for="item in options(state[which])" :key="item.id" :value="item.id">{{ item.label }}</option>
            </select>
          </div>
        </template>
      </div>
      <div class="row">
        <label class="auto-match" :title="texts.auto_match_tooltip">
          <input type="checkbox" :checked="state.autoMatch" data-testid="auto-match" @change="onAutoMatch" />
          {{ texts.auto_match_label }}
        </label>
        <label class="operation">
          <span>{{ texts.operation_label }}</span>
          <select :value="state.operation" data-testid="operation" @change="onOperation">
            <option v-for="item in page.operations" :key="item.key" :value="item.key">{{ item.label }}</option>
          </select>
        </label>
        <strong class="time numeric" :title="inputs?.time_difference.tooltip ?? texts.time_tooltip" data-testid="time-difference">
          {{ inputs?.time_difference.text ?? "" }}
        </strong>
        <button type="button" class="primary" :disabled="!runEnabled" data-testid="run" @click="props.store.calculate()">
          {{ texts.run_label }}
        </button>
        <button type="button" :disabled="result === null || state.exporting.loading" data-testid="export" @click="exportOpen = true">
          {{ texts.export_label }}
        </button>
      </div>
    </section>

    <div class="notices">
      <ErrorNotice
        v-for="which in SIDES"
        :key="which"
        :error="state[which].records.error"
        :keeping="state[which].records.data ? '记录列表为上次读取的结果' : null"
        :busy="state[which].records.loading"
        @retry="state[which].records.retry?.()"
      />
      <ErrorNotice :error="state.match.error" :busy="state.match.loading" @retry="state.match.retry?.()" />
      <ErrorNotice :error="state.inputs.error" :keeping="keepingInputs" :busy="state.inputs.loading" @retry="state.inputs.retry?.()" />
      <ErrorNotice
        :error="state.compute.error"
        :keeping="result ? null : '计算结果已清除，请重新执行计算'"
        :busy="state.compute.loading"
        @retry="props.store.calculate()"
      />
      <div v-if="state.exporting.data" class="outcome" role="status" data-testid="export-done">
        <strong>{{ page?.export.done_title }}</strong>
        <span class="numeric">{{ state.exporting.data.text }}</span>
        <button type="button" @click="props.store.clearExport()">确定</button>
      </div>
      <div v-if="state.exporting.error" class="outcome failed" role="alert" data-testid="export-failed">
        <strong>{{ state.exporting.error.message }}</strong>
        <span class="numeric">{{ state.exporting.error.detail }}</span>
        <button type="button" @click="props.store.clearExport()">关闭</button>
      </div>
    </div>

    <section v-if="texts && page" class="grid">
      <OperationChart
        v-for="which in SIDES"
        :key="which"
        :title="inputs?.[which].title ?? ''"
        :values="inputs?.[which].values ?? null"
        :y-range="inputs?.[which].y_range ?? null"
        :y-label="texts.power_y_label"
        :x-label="texts.x_label"
        :axis="page.axis"
        :legend="inputs?.[which].legend ?? null"
        :empty-heading="texts.input_empty_heading"
        :empty-detail="texts.input_empty_detail"
        :test-id="`chart-${which}`"
      />
      <OperationChart
        :title="result?.result.title ?? texts.result_title"
        :values="result?.result.plotted ?? null"
        :y-range="result?.result.y_range ?? null"
        :y-label="result?.result.y_label ?? ''"
        :x-label="texts.x_label"
        :axis="page.axis"
        :legend="result?.result.legend ?? null"
        variant="result"
        :ratio="result?.result.ratio ?? false"
        :reference-line="result?.result.reference_line ?? false"
        :note="result?.result.ratio_note ?? null"
        :center-text="result?.result.empty_text ?? null"
        :empty-heading="resultPlaceholder?.heading ?? null"
        :empty-detail="resultPlaceholder?.detail ?? null"
        :hide-y-labels="result === null"
        test-id="chart-result"
      />
      <OperationGuide :guide="page.guide" />
    </section>

    <ExportDialog v-if="exportOpen && page" :texts="page.export" @confirm="onExport" @cancel="exportOpen = false" />
  </main>
</template>

<style scoped>
.calc {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) var(--space-3);
  overflow-y: auto;
  min-height: 0;
}
.toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
}
/* UI-188, UI-190: centred rows that wrap instead of squeezing the controls */
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--space-2) var(--space-5);
}
.source {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.side-label {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
}
.source select:first-of-type {
  width: 8.5em;
}
.record {
  width: 21em;
}
.swap {
  font-size: var(--font-size-xl);
  width: var(--control-height);
  padding: 0;
}
.auto-match,
.operation {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.auto-match input {
  height: auto;
}
.time {
  min-width: 20em;
  font-weight: var(--font-weight-bold);
}
.notices {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.notices:empty {
  display: none;
}
.outcome {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
  font-size: var(--font-size-sm);
}
.outcome span {
  flex: 1;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.outcome.failed {
  background: var(--color-error-container);
  color: var(--color-on-error-container);
}
/* UI-189: A | B over result | guide; the guide spans the same column as B (UI-228) */
.grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(var(--operation-row-min-height), 1fr));
  gap: var(--space-2);
  min-height: 0;
}
.empty-sources {
  padding: var(--space-3);
  margin: 0;
}
</style>
