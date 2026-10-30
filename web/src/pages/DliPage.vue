<script setup lang="ts">
/**
 * 光积累计算 (DLI, docs/design/ui-v2-pages.md 2.3): period line (UI-178), date picker, the location editors with 保存经纬度并重置周期
 * (issue 116, as V1.0.3), the enable time, four charts in two columns and two rows (UI-179), the interruptions of the
 * period and what the states mean. The page scrolls when it is not tall enough (UI-182). A failed load keeps the shown
 * period and offers a retry (R-1-5). Without a picked date (the current-period view, = V1.0.3), or while the period
 * shown is still in progress, it reloads every REFRESH_MS so the state, the "统计截至" time and, after the next sunrise,
 * the period itself move on (DLI-041; V1.0.3 refreshes every 3 s, a snapshot needs far less). In the D-165 gap the
 * current view shows the period that just ended (current=false) and keeps reloading; only a picked date whose period
 * has ended is marked "已结束的周期" and left alone (PR #47 review M-2).
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import DliChart from "../components/DliChart.vue";
import ErrorNotice from "../components/ErrorNotice.vue";
import { latestDate } from "../lib/dli";
import { NO_DEVICE_TEXT } from "../lib/view";
import type { DliStore } from "./dliStore";

const REFRESH_MS = 30_000;

const props = defineProps<{ store: DliStore }>();
const state = props.store.state;
const day = computed(() => state.day.data);
/** After a failed load the shown answer can be older than the applied date: the note then names what did not
 * load, so the period on screen is not read as the picked one (review N-5). */
const keeping = computed(() => {
  const data = day.value;
  if (data === null) return null;
  const base = `仍显示上次读取的结果（${data.device.name}）`;
  if (state.appliedDate === data.requested_date) return base;
  if (state.appliedDate === null) return `${base}；已选“当前周期”，尚未读取成功`;
  return `${base}；所选日期 ${state.appliedDate} 的周期尚未读取成功`;
});
const ended = computed(() => day.value !== null && day.value.requested_date !== null && !day.value.period.current);
/** Days after today can only give a 400 (review N-2). Today is as_of's day moved on by the time elapsed since the
 * answer arrived, so the limit passes Beijing midnight while a finished period stays on screen unreloaded (review
 * review M-1); `elapsed` is stepped on every timer tick. */
const receivedAt = ref(performance.now());
const elapsed = ref(0);
watch(day, () => {
  receivedAt.value = performance.now();
  elapsed.value = 0;
});
const maxDate = computed(() => (day.value ? latestDate(day.value.as_of, elapsed.value) : undefined));
let timer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  timer = setInterval(() => {
    elapsed.value = performance.now() - receivedAt.value;
    const live = state.appliedDate === null || day.value?.period.current === true;
    if (live && state.deviceKey !== null && !state.day.loading) void props.store.refresh();
  }, REFRESH_MS);
});

onBeforeUnmount(() => {
  if (timer !== null) clearInterval(timer);
});

function onDate(): void {
  void props.store.applyDate();
}
</script>

<template>
  <main class="dli">
    <section class="panel period-panel">
      <p class="period numeric" :title="day?.location.text ?? ''" data-role="period">
        {{ day?.period.text ?? "积分周期：—" }}
      </p>
      <form class="controls" @submit.prevent="onDate">
        <label class="field">
          <span class="muted">周期日期</span>
          <input v-model="state.dateInput" type="date" :max="maxDate" :disabled="state.deviceKey === null" aria-label="周期日期" />
        </label>
        <button type="submit" :disabled="state.deviceKey === null || state.day.loading">查看</button>
        <button
          type="button"
          :disabled="state.deviceKey === null || state.day.loading || state.appliedDate === null"
          @click="props.store.showCurrent()"
        >
          当前周期
        </button>
        <span v-if="state.inputError" class="input-error" role="alert">{{ state.inputError }}</span>
        <span v-if="ended" class="badge muted">已结束的周期</span>
      </form>
      <form v-if="day" class="controls" data-role="location-form" @submit.prevent="props.store.saveLocation()">
        <label class="field" title="正值为北纬，负值为南纬">
          <span class="muted">纬度（°N）</span>
          <input
            v-model="state.latitudeInput"
            name="dli-latitude"
            type="number"
            class="numeric"
            min="-89.9"
            max="89.9"
            step="0.0001"
            aria-label="纬度（°N）"
          />
        </label>
        <label class="field" title="正值为东经，负值为西经">
          <span class="muted">经度（°E）</span>
          <input
            v-model="state.longitudeInput"
            name="dli-longitude"
            type="number"
            class="numeric"
            min="-180"
            max="180"
            step="0.0001"
            aria-label="经度（°E）"
          />
        </label>
        <button type="submit" data-role="save-location" :disabled="state.saving.loading || state.day.loading">
          保存经纬度并重置周期
        </button>
        <span v-if="state.locationError" class="input-error" role="alert" data-role="location-error">{{
          state.locationError
        }}</span>
      </form>
      <dl v-if="day" class="facts">
        <div>
          <dt class="muted">位置</dt>
          <dd class="numeric">
            {{ day.location.coordinates_text }}
            <span class="muted">{{ day.location.stored ? "（已保存）" : "（尚未保存，按默认北京坐标）" }}</span>
          </dd>
        </div>
        <div>
          <dt class="muted">DLI 启用时间</dt>
          <dd class="numeric">
            {{ day.enabled.text }}
            <span v-if="!day.enabled.stored" class="muted">（库中未记录，按当前时刻，周期内暂无记录计入）</span>
          </dd>
        </div>
        <div>
          <dt class="muted">允许间隔</dt>
          <dd>{{ day.gap_text }}</dd>
        </div>
        <div>
          <dt class="muted">数据来源</dt>
          <dd>{{ day.snapshot_text }}</dd>
        </div>
      </dl>
      <ErrorNotice :error="state.saving.error" :busy="state.saving.loading" @retry="state.saving.retry?.()" />
    </section>

    <ErrorNotice :error="state.day.error" :keeping="keeping" :busy="state.day.loading" @retry="props.store.refresh()" />

    <p v-if="state.deviceKey === null" class="muted empty" data-role="no-device">{{ NO_DEVICE_TEXT }}</p>

    <section v-if="day" class="charts" aria-label="四项 DLI">
      <DliChart v-for="metric in day.metrics" :key="metric.key" :metric="metric" :ticks="day.ticks" />
    </section>

    <div v-if="day" class="bottom">
      <section class="panel side" aria-label="中断">
        <h2 class="panel-title">本周期的 DLI 中断</h2>
        <table v-if="day.interruptions.length" class="interruptions">
          <thead>
            <tr>
              <th>时间（北京时间）</th>
              <th>原因</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in day.interruptions" :key="item.occurred_at + item.reason">
              <td class="numeric">{{ item.occurred_at_text }}</td>
              <td>{{ item.reason }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">本周期内没有记录到 DLI 中断。</p>
      </section>
      <section class="panel side" aria-label="状态说明">
        <h2 class="panel-title">状态说明</h2>
        <ul class="legend">
          <li><span class="state-ok">积分中</span>：周期开始后数据连续，正常累计。</li>
          <li>
            <span class="state-warn">部分累计</span>：有缺测、无效值、中断或超长空档；断开处不补零、不跨段，恢复后在此前累计值上继续。
          </li>
          <li><span class="state-muted">有效数据不足</span>：周期内还没有形成有效连续区段，累计值显示“—”。</li>
          <li><span class="state-warn">数据未更新</span>：最后一个有效点到统计截至时刻已超过允许间隔，括号内为持续时长。</li>
          <li>覆盖率 = 有效连续时长 ÷ 本周期已过去的时长；把鼠标停在覆盖率一行上可看起始、内部、尾部未覆盖。</li>
        </ul>
      </section>
    </div>
  </main>
</template>

<style scoped>
.dli {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  overflow-y: auto;
  min-height: 0;
}
.period-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
}
.period {
  margin: 0;
  text-align: center;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-medium);
}
.controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  justify-content: center;
}
.field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
.input-error {
  color: var(--color-error);
  font-size: var(--font-size-sm);
}
.badge {
  padding: 0 var(--space-2);
  border-radius: var(--radius-control);
  background: var(--color-surface-container);
  font-size: var(--font-size-sm);
}
.facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-1) var(--space-4);
  margin: 0;
  font-size: var(--font-size-sm);
}
.facts div {
  display: flex;
  gap: var(--space-2);
  min-width: 0;
}
.facts dt {
  flex: 0 0 auto;
}
.facts dd {
  margin: 0;
  min-width: 0;
}
.note {
  margin: 0;
  font-size: var(--font-size-xs);
}
/* UI-179: two columns, two rows */
.charts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}
.bottom {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}
.side {
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
}
.interruptions {
  width: 100%;
  border-collapse: collapse;
}
.interruptions th,
.interruptions td {
  text-align: left;
  padding: var(--space-1) var(--space-2);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
}
.legend {
  margin: 0;
  padding-left: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
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
.empty {
  padding: var(--space-4);
}
</style>
