<script setup lang="ts">
/**
 * 诊断与维护记录 on 设置与导出 (D-226), every tier, read only for devices and databases:
 *   * 导出诊断包 (API-27): one zip into the alpha's output folder; the service's text names the file;
 *   * 维护记录 (API-28): every device write the device databases recorded, newest first, with before, written value,
 *     readback and result (成功 / 失败 / 待核对); fields the database does not hold read "未记录".
 * Colours come from the design tokens only (R-1-5).
 */
import { computed, onMounted } from "vue";
import type { MaintenanceLogResult } from "../api/types";
import { ALL_DEVICES, type SupportStore } from "../pages/supportStore";
import ErrorNotice from "./ErrorNotice.vue";

const BUNDLE_TITLE = "导出诊断包";
const BUNDLE_NOTE =
  "把本机服务日志、版本与构建信息、软件配置、当前状态和各设备库的维护审计表打成一个 zip，保存到数据目录 exports/diagnostics，供我方开发人员内部排查（只读设备库，不含光谱）。配置与库内设置只导出已知字段；日志只做了尽力去除令牌、密码与本机路径，不能保证完全去除，发到公司外部前请先打开看一眼。";
const ALL_LABEL = "全部设备";
/** Until the service's own label arrives (the first read may fail), the checkbox still says what it does. */
const TIME_SYNC_FALLBACK = "包含设备对时";

const props = defineProps<{ store: SupportStore }>();
const state = props.store.state;
const log = computed(() => state.log.data);
const problems = computed(() => (log.value?.devices ?? []).filter((device) => device.problem !== null));
const resultClass = (result: MaintenanceLogResult) => `result-${result}`;

onMounted(() => {
  void props.store.loadLog();
});
</script>

<template>
  <div class="support">
    <section class="panel section" data-role="diagnostics-bundle">
      <h2 class="panel-title">{{ BUNDLE_TITLE }}</h2>
      <p class="note muted">{{ BUNDLE_NOTE }}</p>
      <div class="action">
        <button
          type="button"
          class="primary"
          data-role="diagnostics-export"
          :disabled="state.bundle.loading"
          @click="props.store.exportBundle()"
        >
          {{ state.bundle.loading ? "正在导出…" : BUNDLE_TITLE }}
        </button>
      </div>
      <p v-if="state.bundle.data && !state.bundle.error" class="done" role="status" data-role="diagnostics-done">
        {{ state.bundle.data.text }}
      </p>
      <ErrorNotice
        :error="state.bundle.error"
        :keeping="null"
        :busy="state.bundle.loading"
        @retry="props.store.exportBundle()"
      />
    </section>

    <section class="panel section" data-role="maintenance-log">
      <h2 class="panel-title">{{ log?.texts.title ?? "维护记录" }}</h2>
      <p v-if="log" class="note muted">{{ log.texts.note }}</p>
      <div class="filters">
        <select
          name="log-device"
          :value="state.device"
          :disabled="state.devices.length === 0"
          @change="props.store.setDevice(($event.target as HTMLSelectElement).value)"
        >
          <option :value="ALL_DEVICES">{{ ALL_LABEL }}</option>
          <option v-for="device in state.devices" :key="device.key" :value="device.key">{{ device.name }}</option>
        </select>
        <label class="choice">
          <input
            type="checkbox"
            name="log-time-sync"
            :checked="state.timeSync"
            @change="props.store.setTimeSync(($event.target as HTMLInputElement).checked)"
          />
          {{ log?.texts.time_sync_label ?? TIME_SYNC_FALLBACK }}
        </label>
        <button type="button" data-role="log-refresh" :disabled="state.log.loading" @click="props.store.loadLog()">
          刷新
        </button>
      </div>
      <ErrorNotice
        :error="state.log.error"
        :keeping="log ? '仍显示上次读取的维护记录' : null"
        :busy="state.log.loading"
        @retry="state.log.retry?.()"
      />
      <ul v-if="problems.length > 0" class="problems" data-role="log-problems">
        <li v-for="device in problems" :key="device.key">{{ device.name }}（{{ device.database_name }}）：{{ device.problem }}</li>
      </ul>
      <template v-if="log">
        <p v-if="log.devices.length === 0" class="muted small" data-role="log-no-devices">{{ log.texts.no_devices_text }}</p>
        <p v-else-if="log.items.length === 0" class="muted small" data-role="log-empty">{{ log.texts.empty_text }}</p>
        <div v-else class="table-wrap">
          <table class="log" data-role="log-table">
            <thead>
              <tr>
                <th v-for="column in log.texts.columns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in log.items" :key="`${item.device_key}-${item.source}`" :title="item.source">
                <td class="numeric nowrap">{{ item.occurred_at_text }}</td>
                <td class="nowrap">{{ item.device_name }}</td>
                <td class="nowrap">{{ item.kind_text }}</td>
                <td class="value">{{ item.before_text }}</td>
                <td class="value">{{ item.after_text }}</td>
                <td class="value">{{ item.readback_text }}</td>
                <td class="nowrap" :class="resultClass(item.result)" data-role="log-result">{{ item.result_text }}</td>
                <td class="value">{{ item.detail }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="log.limit_reached" class="muted small" data-role="log-limit">{{ log.texts.limit_text }}</p>
        <p v-if="log.scan_limited" class="muted small" data-role="log-scan-limited">{{ log.texts.scan_limited_text }}</p>
      </template>
    </section>
  </div>
</template>

<style scoped>
.support {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: calc(1400px + var(--space-5));
  width: 100%;
  margin: 0 auto;
}
.section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
}
.note,
.small {
  margin: 0;
  font-size: var(--font-size-sm);
}
.action {
  display: flex;
  justify-content: center;
  padding: var(--space-2) 0;
}
.action button {
  width: 260px;
  font-weight: var(--font-weight-bold);
}
.done {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  font-size: var(--font-size-sm);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
.filters {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.choice {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
}
.choice input {
  height: auto;
}
.problems {
  margin: 0;
  padding: var(--space-2) var(--space-3) var(--space-2) var(--space-5);
  border-radius: var(--radius-control);
  background: var(--color-warning-container);
  color: var(--color-on-warning-container);
  font-size: var(--font-size-sm);
}
.table-wrap {
  overflow-x: auto;
}
.log {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.log th,
.log td {
  padding: var(--space-1) var(--space-2);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
  text-align: left;
  vertical-align: top;
}
.log th {
  height: var(--table-row-height);
  background: var(--color-surface-container);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}
.nowrap {
  white-space: nowrap;
}
.value {
  min-width: 140px;
  overflow-wrap: anywhere;
}
.result-success {
  color: var(--color-success);
}
.result-failure {
  color: var(--color-error);
  font-weight: var(--font-weight-medium);
}
.result-pending {
  color: var(--color-warning);
  font-weight: var(--font-weight-medium);
}
p {
  margin: 0;
}
</style>
