<script setup lang="ts">
/**
 * 历史回放 (docs/design/ui-v2-pages.md 2.2): list about 40 % on the left, spectrum, metric cards and detail about
 * 60 % on the right. Errors keep the last valid data on screen and offer a retry (R-1-5).
 */
import { computed } from "vue";
import DetailPanel from "../components/DetailPanel.vue";
import ErrorNotice from "../components/ErrorNotice.vue";
import KpiCards from "../components/KpiCards.vue";
import QueryBar from "../components/QueryBar.vue";
import RecordTable from "../components/RecordTable.vue";
import SpectrumChart from "../components/SpectrumChart.vue";
import { NO_DEVICE_TEXT } from "../lib/view";
import type { HistoryStore } from "./historyStore";

const props = defineProps<{ store: HistoryStore }>();
const state = props.store.state;

const detail = computed(() => state.detail.data);
const caption = computed(() => {
  const shown = detail.value;
  if (!shown) return "未选择记录";
  if (shown.spectrum_state === "none") return `#${shown.record.id} 无光谱`;
  if (shown.spectrum_state === "invalid") return `#${shown.record.id} 光谱数据无法解析`;
  return `#${shown.record.id} · ${shown.header.time_text}`;
});
const pageKeeping = computed(() =>
  state.page.data ? `仍显示上次查询结果（${state.page.data.range.start} 至 ${state.page.data.range.end}）` : null,
);
const detailKeeping = computed(() =>
  state.detail.data ? `仍显示 #${state.detail.data.record.id} 的详情` : null,
);

function retry(resource: { retry: (() => Promise<boolean>) | null }): void {
  void resource.retry?.();
}
</script>

<template>
  <main class="history">
    <div class="left">
      <section class="panel records-panel">
        <header class="records-head">
          <h2 class="panel-title">历史记录</h2>
          <span v-if="state.page.data" class="muted numeric count">{{ state.page.data.items.length }} 条</span>
        </header>
        <QueryBar
          v-model="state.rangeInput"
          :busy="state.page.loading"
          :disabled="state.deviceKey === null"
          :limit-reached="state.page.data?.limit_reached ?? false"
          :input-error="state.inputError"
          @query="props.store.query()"
        />
        <ErrorNotice
          :error="state.page.error"
          :keeping="pageKeeping"
          :busy="state.page.loading"
          @retry="retry(state.page)"
        />
        <template v-if="state.deviceKey === null">
          <!-- with a failed device list the page-wide error says why; "no device" would mislead (N-5) -->
          <p v-if="!state.devices.error" class="muted empty" data-role="no-device">{{ NO_DEVICE_TEXT }}</p>
        </template>
        <RecordTable
          v-else
          :items="state.page.data?.items ?? []"
          :selected-id="state.selectedId"
          @select="props.store.select($event)"
        />
      </section>
    </div>
    <div class="right">
      <ErrorNotice
        :error="state.detail.error"
        :keeping="detailKeeping"
        :busy="state.detail.loading"
        @retry="retry(state.detail)"
      />
      <SpectrumChart class="spectrum" :spectrum="detail?.spectrum ?? null" :caption="caption" />
      <KpiCards :groups="detail?.groups ?? null" />
      <DetailPanel :detail="detail ?? null" />
    </div>
  </main>
</template>

<style scoped>
.history {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  gap: var(--space-3);
  padding: var(--space-3);
  min-height: 0;
  height: 100%;
}
.left,
.right {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 0;
}
.left {
  overflow: hidden;
}
.right {
  overflow-y: auto;
}
.records-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  min-height: 0;
  flex: 1;
}
.records-head {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}
.count {
  font-size: var(--font-size-sm);
}
.spectrum {
  flex: 0 0 auto;
  height: 340px;
}
.empty {
  padding: var(--space-4);
}
</style>
