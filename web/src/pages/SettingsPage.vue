<script setup lang="ts">
/**
 * 设置与导出, alpha read-only version (docs/design/ui-v2-pages.md 2.5; D-209, D-210).
 *
 * Left: 通信设置 and 设备登记; tier 0 reads no configuration, so each value says "档位 0 不读取配置" and there is no
 * device (issue #82); tier 1 edits the alpha's own configuration (TIER_1). Right: 采集记录导出 (the V1.0.3 rules, see
 * settingsStore.ts) and the status area of the viewed device, both on the devices' own databases; in tier 1 the status
 * area is V1.0.3's 设备状态与最近日志 (status line, log table, 日志详情 on a double-click; API-16, GitHub issue 107). The whole page
 * scrolls when it is not tall enough (UI-096). While shown, the count is refreshed every REFRESH_MS like the
 * V1.0.3 settings timer, so a preset window moves on (EXP-051); in 自定义时间 it recounts the range last applied
 * and never touches the editors while the user types (only their change event normalises them).
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ExportKind, LogEntry } from "../api/types";
import AcquisitionConfigEditor from "../components/AcquisitionConfigEditor.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import ErrorNotice from "../components/ErrorNotice.vue";
import LogDetailsDialog from "../components/LogDetailsDialog.vue";
import SettingsMaintenance from "../components/SettingsMaintenance.vue";
import AboutPanel from "../components/AboutPanel.vue";
import SupportPanel from "../components/SupportPanel.vue";
import TierPanel from "../components/TierPanel.vue";
import type { MaintenanceStore } from "./maintenanceStore";
import { exportDevices, type SettingsStore } from "./settingsStore";
import type { SupportStore } from "./supportStore";
import type { TakeoverStore } from "./takeoverStore";

const REFRESH_MS = 3000;
/** Tier 1 (16_ 3.1): the left column edits the alpha's own configuration; the export reads those devices' databases. */
const TIER_ONE_TEXT =
  "左侧是采集配置：通信设置与设备登记；右侧导出这些设备采集的数据。";

const props = defineProps<{
  store: SettingsStore;
  takeover?: TakeoverStore;
  maintenance?: MaintenanceStore;
  /** 导出诊断包 and 维护记录 (D-226), every tier; absent in tests that do not exercise them */
  support?: SupportStore;
  /** the build version for 关于与技术支持 (health), null before it is read */
  version?: string | null;
}>();
const state = props.store.state;
const tierOne = computed(() => (props.takeover?.state.tier.data?.tier ?? 0) >= 1);
const tierTwo = computed(() => (props.takeover?.state.tier.data?.tier ?? 0) >= 2);

/** The tier-1 configuration is read when the page opens in tier 1 and when tier 1 is turned on. */
watch(
  tierOne,
  (on) => {
    if (on) void props.takeover?.loadConfig();
  },
  { immediate: true },
);
const view = computed(() => state.view.data);
const texts = computed(() => view.value?.export ?? null);
const devices = computed(() => exportDevices(state));
const exportDevice = computed(() => devices.value.find((item) => item.key === state.exportKey) ?? null);
const custom = computed(() => state.range === "custom");
const countText = computed(() => {
  if (texts.value === null) return "";
  if (state.exportKey === null) return texts.value.no_device_text;
  return state.count.data?.text ?? texts.value.counting_text;
});
const canExport = computed(
  () =>
    state.count.data !== null &&
    state.count.data.can_export &&
    state.count.data.device.key === state.exportKey &&
    !state.exporting.loading,
);
const logs = computed(() => (tierOne.value ? state.logs.data : null));
/** The 日志详情 text of the double-clicked row, taken when it was clicked (UI-102). */
const details = ref<{ title: string; text: string; copyLabel: string } | null>(null);
let timer: ReturnType<typeof setInterval> | null = null;

function openDetails(entry: LogEntry): void {
  const shown = logs.value;
  if (shown === null) return;
  details.value = { title: shown.details_title, text: entry.details_text, copyLabel: shown.copy_label };
}

onMounted(() => {
  timer = setInterval(() => {
    // like the overview and DLI pages: no new read while the last one is still under way (a slow database read
    // must not pile up requests that each replace the previous one)
    const busy = state.count.loading || state.exporting.loading || state.summary.loading || state.logs.loading;
    if (state.pending === null && !busy) void props.store.tick();
  }, REFRESH_MS);
});

onBeforeUnmount(() => {
  if (timer !== null) clearInterval(timer);
});

function onFormat(kind: ExportKind, event: Event): void {
  void props.store.setFormat(kind, (event.target as HTMLInputElement).checked);
}
</script>

<template>
  <main class="settings">
    <TierPanel v-if="props.takeover" :store="props.takeover" />
    <SettingsMaintenance v-if="tierTwo && props.maintenance && props.takeover" :store="props.maintenance" :takeover="props.takeover" />
    <p v-if="view && !tierOne" class="banner" data-role="read-only">{{ view.read_only_text }}</p>
    <p v-else-if="tierOne" class="banner" data-role="tier-one">{{ TIER_ONE_TEXT }}</p>
    <ErrorNotice :error="state.view.error" :keeping="view ? '仍显示上次读取的设置' : null" :busy="state.view.loading" @retry="state.view.retry?.()" />

    <div v-if="view && texts" class="columns">
      <AcquisitionConfigEditor v-if="tierOne && props.takeover" :store="props.takeover" />
      <div v-else class="column">
        <section class="panel section" data-role="bus">
          <h2 class="panel-title">{{ view.groups[0] }}</h2>
          <dl class="fields">
            <div v-for="item in view.bus" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd class="muted">{{ item.text }}</dd>
            </div>
          </dl>
          <p class="note muted">{{ view.config_note }}</p>
        </section>

        <section class="panel section" data-role="devices">
          <h2 class="panel-title">{{ view.groups[1] }}</h2>
          <table class="devices">
            <thead>
              <tr>
                <th v-for="column in view.device_columns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in view.devices"
                :key="row.key"
                :class="{ unconfigured: !row.configured }"
                :title="row.tooltip ?? undefined"
              >
                <td>{{ row.configured ? row.name : row.state_text }}</td>
                <td class="muted">{{ row.slave_id_text ?? "—" }}</td>
                <td class="muted">{{ row.enabled_text ?? "—" }}</td>
                <td class="muted">{{ row.fail_stop_text ?? "—" }}</td>
                <td class="numeric file">{{ row.database_name ?? "—" }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <div class="column">
        <section class="panel section" data-role="export">
          <h2 class="panel-title">{{ texts.title }}</h2>
          <div class="form">
            <label class="row">
              <span class="label">{{ texts.device_label }}</span>
              <select
                name="export-device"
                :value="state.exportKey ?? ''"
                :title="exportDevice?.tooltip ?? ''"
                :disabled="devices.length === 0"
                @change="props.store.selectExportDevice(($event.target as HTMLSelectElement).value)"
              >
                <option v-for="item in devices" :key="item.key" :value="item.key" :title="item.tooltip ?? ''">
                  {{ item.name }}
                </option>
              </select>
            </label>
            <label class="row">
              <span class="label">{{ texts.range_label }}</span>
              <select
                name="export-range"
                :value="state.range"
                @change="props.store.setRange(($event.target as HTMLSelectElement).value)"
              >
                <option v-for="item in texts.ranges" :key="item.key" :value="item.key">{{ item.label }}</option>
              </select>
            </label>
            <label class="row">
              <span class="label">{{ texts.start_label }}</span>
              <input
                v-model="state.startInput"
                name="export-start"
                class="numeric"
                type="text"
                placeholder="年-月-日 时:分:秒"
                spellcheck="false"
                :disabled="!custom"
                @change="props.store.applyCustom()"
              />
            </label>
            <label class="row">
              <span class="label">{{ texts.end_label }}</span>
              <input
                v-model="state.endInput"
                name="export-end"
                class="numeric"
                type="text"
                placeholder="年-月-日 时:分:秒"
                spellcheck="false"
                :disabled="!custom"
                @change="props.store.applyCustom()"
              />
            </label>
            <p v-if="state.inputError" class="row input-error" role="alert">{{ state.inputError }}</p>
            <div class="row">
              <span class="label">{{ texts.count_label }}</span>
              <span data-role="count">{{ countText }}</span>
            </div>
            <div class="row">
              <span class="label">{{ texts.content_label }}</span>
              <span class="muted small" :title="texts.content_tooltip">{{ texts.content_note }}</span>
            </div>
            <div class="row">
              <span class="label">{{ texts.formats_label }}</span>
              <span class="formats">
                <label v-for="item in texts.formats" :key="item.key" class="choice">
                  <input type="checkbox" :name="`format-${item.key}`" :checked="state.formats[item.key]" @change="onFormat(item.key, $event)" />
                  {{ item.label }}
                </label>
              </span>
            </div>
          </div>
          <ErrorNotice
            :error="state.count.error"
            :keeping="state.count.data ? '预计记录数为上次统计的结果' : null"
            :busy="state.count.loading"
            @retry="state.count.retry?.()"
          />
          <div class="action">
            <button
              type="button"
              class="primary"
              data-role="export-button"
              :disabled="!canExport"
              @click="props.store.requestExport()"
            >
              {{ state.exporting.loading ? "正在导出…" : texts.button_label }}
            </button>
          </div>
          <p v-if="state.notice" class="notice" role="status" data-role="export-notice">{{ state.notice }}</p>
          <p v-if="state.exporting.data && !state.exporting.error" class="done" role="status" data-role="export-done">
            {{ state.exporting.data.text }}
          </p>
          <ErrorNotice :error="state.exporting.error" :keeping="null" :busy="state.exporting.loading" @retry="props.store.requestExport()" />
          <p class="note muted">{{ texts.note }}</p>
          <p class="directory numeric muted" :title="texts.directory">{{ texts.directory }}</p>
        </section>

        <section class="panel section" data-role="status">
          <h2 class="panel-title">{{ view.groups[3] }}</h2>
          <template v-if="state.summary.data">
            <p
              v-if="logs"
              data-role="status-line"
              :class="`tone-${logs.status.tone}`"
              :title="logs.status.tooltip"
            >
              {{ logs.status.text }}
            </p>
            <p v-else data-role="status-line" :title="state.summary.data.serial_text">{{ state.summary.data.status_text }}</p>
            <p class="small">{{ state.summary.data.records_text }}</p>
            <p class="small">{{ state.summary.data.database_text }}</p>
            <p class="small muted">记录中的轮询周期：{{ state.summary.data.poll_cycle_text }}</p>
          </template>
          <p v-else-if="state.summaryKey === null" class="muted small">{{ texts.no_device_text }}</p>
          <ErrorNotice
            :error="state.summary.error"
            :keeping="state.summary.data ? '仍显示上次读取的状态' : null"
            :busy="state.summary.loading"
            @retry="state.summary.retry?.()"
          />
          <template v-if="tierOne">
            <div v-if="logs" class="log-wrap">
              <table class="log" data-role="log">
                <thead>
                  <tr>
                    <th v-for="column in logs.columns" :key="column">{{ column }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(entry, index) in logs.items"
                    :key="entry.id ?? `row-${index}`"
                    :class="{ error: entry.error }"
                    @dblclick="openDetails(entry)"
                  >
                    <td class="numeric" :title="entry.time_text">{{ entry.time_text }}</td>
                    <td :title="entry.category_tooltip">{{ entry.category_text }}</td>
                    <td :title="entry.result_tooltip">{{ entry.result_text }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <ErrorNotice
              :error="state.logs.error"
              :keeping="state.logs.data ? '仍显示上次读取的状态与日志' : null"
              :busy="state.logs.loading"
              @retry="state.logs.retry?.()"
            />
          </template>
          <p v-else class="muted small">只读模式不连接设备，不显示设备日志与通信状态。</p>
        </section>
      </div>
    </div>

    <SupportPanel v-if="props.support" :store="props.support" />
    <AboutPanel :version="props.version ?? null" />

    <LogDetailsDialog
      v-if="details"
      :title="details.title"
      :text="details.text"
      :copy-label="details.copyLabel"
      @close="details = null"
    />

    <ConfirmDialog
      v-if="state.pending?.confirm"
      :title="state.pending.confirm.title"
      :text="state.pending.confirm.text"
      @yes="props.store.confirmExport()"
      @no="props.store.cancelExport()"
    />
  </main>
</template>

<style scoped>
.settings {
  overflow: auto;
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.banner {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-warning-container);
  color: var(--color-on-warning-container);
  font-size: var(--font-size-sm);
}
.columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 700px));
  justify-content: center;
  gap: var(--space-5);
  align-items: start;
}
.column {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}
.section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
}
.fields {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-1);
  margin: 0;
}
.fields div {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: var(--space-2);
  align-items: center;
  min-height: var(--table-row-height);
}
.fields dt {
  color: var(--color-on-surface);
}
.fields dd {
  margin: 0;
}
.note,
.directory,
.small {
  margin: 0;
  font-size: var(--font-size-sm);
}
.directory {
  overflow-wrap: anywhere;
}
.devices {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
  table-layout: fixed;
}
.devices th,
.devices td {
  height: var(--table-row-height);
  padding: 0 var(--space-2);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.devices th {
  background: var(--color-surface-container);
  font-weight: var(--font-weight-medium);
}
.devices tr.unconfigured td {
  color: var(--color-disabled);
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.row {
  display: grid;
  grid-template-columns: 105px minmax(0, 1fr);
  gap: var(--space-2);
  align-items: center;
  margin: 0;
}
.label {
  color: var(--color-on-surface);
}
.formats {
  display: flex;
  gap: var(--space-4);
}
.choice {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.choice input {
  height: auto;
}
.input-error {
  color: var(--color-error);
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
.notice,
.done {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  font-size: var(--font-size-sm);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.notice {
  background: var(--color-surface-container);
}
.done {
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
.tone-warning {
  color: var(--color-warning);
}
.tone-error {
  color: var(--color-error);
}
.tone-muted {
  color: var(--color-on-surface-variant);
}
.log-wrap {
  max-height: calc(8 * var(--table-row-height) + var(--table-row-height));
  overflow: auto;
  border: var(--border-width) solid var(--color-outline-variant);
}
.log {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.log th,
.log td {
  height: var(--table-row-height);
  padding: 0 var(--space-2);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 0;
}
.log th {
  position: sticky;
  top: 0;
  background: var(--color-surface-container);
  font-weight: var(--font-weight-medium);
}
.log th:nth-child(1),
.log th:nth-child(2) {
  width: 1%;
}
.log td:nth-child(1),
.log td:nth-child(2) {
  max-width: none;
}
.log tbody tr {
  cursor: default;
  user-select: none;
}
.log tbody tr.error td {
  color: var(--color-error);
}
p {
  margin: 0;
}
</style>
