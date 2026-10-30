<script setup lang="ts">
/**
 * 通信设置与设备登记, tier 1: the alpha's own configuration (16_ 3.1-3.3; D-214).
 *
 * The form is V1.0.3's settings form as the service describes it (labels, choices, ranges, hints, tooltips, the four
 * registration rows); the page keeps no rule of its own. 保存并应用全部配置 sends the four rows as typed: the service
 * applies V1.0.3's form rules and DeviceHub.apply decides, with V1.0.3's own messages; a refusal keeps what was
 * typed (R-1-5). The database column shows the file each registered device uses (always under the alpha's data
 * directory); new rows get theirs when saved, or reuse the same-name database already in the alpha's folder when
 * "沿用 alpha 目录中的同名库" is checked (D-215; the service checks it). "从 V1.0.3 配置导入副本" reads a V1.0.3 configuration without writing
 * anything and puts the importable devices into the form; saving is still the user's step.
 *
 * 计算机串口 is V1.0.3's editable list (#74): the computer's serial ports (read when the RTU fields are shown and on
 * 刷新串口) are offered under the field, picking one fills in its name, and any other name can still be typed. The
 * list's tooltip is V1.0.3's hint after a refresh; a failed read keeps the last list and offers a retry (R-1-5).
 *
 * When the service names a `problem` (D-220) the page shows it and, with nothing taken over, offers
 * "以空配置重新配置…" (V1.0.3's way out at startup; the service backs the original file up when saving). A saved
 * configuration that failed to apply in the background is marked 未生效 from the status (D-221); saving stays open.
 */
import { computed, ref, watch } from "vue";
import type { BusValues, ConfigRow } from "../api/types";
import type { TakeoverStore } from "../pages/takeoverStore";
import ErrorNotice from "./ErrorNotice.vue";

const props = defineProps<{ store: TakeoverStore }>();
const state = props.store.state;
const config = computed(() => state.config.data);
const form = computed(() => config.value?.form ?? null);
const draft = computed(() => state.draft);
const running = computed(() => state.tier.data?.takeover === "running");
const labels = computed(() => Object.fromEntries((form.value?.labels ?? []).map((item) => [item.key, item.label])));
const step = computed(() => 10 ** -(form.value?.poll_decimals ?? 1));
const preview = computed(() => state.importing.data);
/** 从 V1.0.3 配置导入副本: not shown since issue 119 (customer trial); the store and the service keep it. */
const SHOW_V103_IMPORT = false;
const applyError = computed(() => state.status.data?.config_apply_error ?? null);
const ports = computed(() => state.serialPorts.data?.ports ?? []);
const portsOpen = ref(false);
/** The option the arrow keys are on (aria-activedescendant); -1 while none is. */
const activePort = ref(-1);
/** V1.0.3 sets the port box's tooltip to the refresh hint; before the first list the form's own hint. */
const portHint = computed(() => state.serialPorts.data?.hint ?? form.value?.serial_port_hint ?? "");
const portsEmpty = computed(() =>
  state.serialPorts.data !== null ? state.serialPorts.data.hint : state.serialPorts.loading ? "正在读取本机串口…" : "未能读取本机串口",
);
const rtuShown = computed(() => form.value !== null && draft.value?.bus.transport === "rtu");

// V1.0.3 refreshes the list whenever the settings page shows the port box (populate_settings, showEvent).
watch(
  rtuShown,
  (shown) => {
    if (shown) void props.store.loadSerialPorts();
    else portsOpen.value = false;
  },
  { immediate: true },
);

function choosePort(value: string): void {
  bus("serial_port", value);
  portsOpen.value = false;
}

/** ArrowDown / ArrowUp open the list and move through it (starting at the current port); Enter takes it. */
function movePort(step: number): void {
  if (!portsOpen.value) {
    portsOpen.value = true;
    activePort.value = ports.value.findIndex((port) => port.value === draft.value?.bus.serial_port);
    if (activePort.value >= 0) return;
  }
  const count = ports.value.length;
  if (count === 0) return;
  activePort.value = activePort.value < 0 ? (step > 0 ? 0 : count - 1) : (activePort.value + step + count) % count;
}

function enterPort(event: KeyboardEvent): void {
  const port = portsOpen.value ? ports.value[activePort.value] : undefined;
  if (port === undefined) return;
  event.preventDefault();
  choosePort(port.value);
}

function leavePorts(event: FocusEvent): void {
  const next = event.relatedTarget as Node | null;
  if (next === null || !(event.currentTarget as HTMLElement).contains(next)) portsOpen.value = false;
}

function text(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value;
}

function number(event: Event): number {
  return Number((event.target as HTMLInputElement | HTMLSelectElement).value);
}

function checked(event: Event): boolean {
  return (event.target as HTMLInputElement).checked;
}

function bus<K extends keyof BusValues>(field: K, value: BusValues[K]): void {
  props.store.setBus(field, value);
}

function row<K extends keyof ConfigRow>(index: number, field: K, value: ConfigRow[K]): void {
  props.store.setRow(index, field, value);
}
</script>

<template>
  <div class="editor">
    <ErrorNotice
      :error="state.config.error"
      :keeping="config ? '仍显示上次读取的配置' : null"
      :busy="state.config.loading"
      @retry="state.config.retry?.()"
    />
    <template v-if="config && form && draft">
      <section v-if="config.problem && !state.reconfiguring" class="panel section problem" data-role="config-problem" role="alert">
        <strong>{{ form.reconfigure_title }}</strong>
        <p class="small pre">{{ config.problem.message }}</p>
        <p v-if="config.problem.detail" class="small pre muted">{{ config.problem.detail }}</p>
        <div v-if="props.store.canReconfigure()" class="actions">
          <button type="button" data-role="reconfigure" @click="props.store.askReconfigure()">{{ form.reconfigure_label }}</button>
        </div>
      </section>
      <p v-if="state.reconfiguring" class="panel section small notice" data-role="reconfigure-hint" role="status">
        {{ form.reconfigure_hint }}
      </p>
      <section class="panel section" data-role="bus">
        <h2 class="panel-title">通信设置</h2>
        <p class="muted small path" data-role="config-path" :title="config.path">配置文件：{{ config.path }}</p>
        <div class="fields">
          <label class="field">
            <span>{{ labels.transport }}</span>
            <select name="bus-transport" :value="draft.bus.transport" @change="bus('transport', text($event) as BusValues['transport'])">
              <option v-for="item in form.transports" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <template v-if="draft.bus.transport === 'rtu'">
            <div class="field">
              <span id="serial-port-label">{{ labels.serial_port }}</span>
              <div class="port-row">
                <div class="combo" @focusout="leavePorts">
                  <input
                    name="bus-serial-port"
                    type="text"
                    spellcheck="false"
                    autocomplete="off"
                    role="combobox"
                    aria-labelledby="serial-port-label"
                    aria-autocomplete="none"
                    aria-controls="serial-port-list"
                    :aria-expanded="portsOpen"
                    :value="draft.bus.serial_port"
                    :title="portHint"
                    @input="bus('serial_port', text($event))"
                    :aria-activedescendant="portsOpen && ports[activePort] ? `serial-port-${activePort}` : undefined"
                    @keydown.down.prevent="movePort(1)"
                    @keydown.up.prevent="movePort(-1)"
                    @keydown.enter="enterPort"
                    @keydown.esc="portsOpen = false"
                  />
                  <button
                    type="button"
                    class="toggle"
                    tabindex="-1"
                    data-role="serial-ports-toggle"
                    aria-label="展开本机串口列表"
                    :aria-expanded="portsOpen"
                    @mousedown.prevent
                    @click="portsOpen = !portsOpen"
                  >
                    ▾
                  </button>
                  <ul v-if="portsOpen" id="serial-port-list" class="ports" role="listbox" data-role="serial-ports" :title="portHint">
                    <li
                      v-for="(port, index) in ports"
                      :id="`serial-port-${index}`"
                      :key="port.value"
                      :class="{ active: index === activePort }"
                      role="option"
                      :data-value="port.value"
                      :aria-selected="port.value === draft.bus.serial_port"
                      :title="port.label"
                      @mousedown.prevent
                      @click="choosePort(port.value)"
                    >
                      {{ port.label }}
                    </li>
                    <li v-if="ports.length === 0" class="empty" data-role="serial-ports-empty">{{ portsEmpty }}</li>
                  </ul>
                </div>
                <button
                  type="button"
                  data-role="serial-refresh"
                  :disabled="state.serialPorts.loading"
                  @click="props.store.loadSerialPorts()"
                >
                  刷新串口
                </button>
              </div>
            </div>
            <p class="muted small hint">{{ form.serial_port_hint }}</p>
            <div v-if="state.serialPorts.error" class="hint" data-role="serial-ports-error">
              <ErrorNotice
                :error="state.serialPorts.error"
                :keeping="state.serialPorts.data ? '仍显示上次读取的串口列表' : null"
                :busy="state.serialPorts.loading"
                @retry="state.serialPorts.retry?.()"
              />
            </div>
            <label class="field">
              <span>{{ labels.baudrate }}</span>
              <select name="bus-baudrate" :value="draft.bus.baudrate" @change="bus('baudrate', number($event))">
                <option v-for="value in form.baudrates" :key="value" :value="value">{{ value }}</option>
              </select>
            </label>
            <label class="field">
              <span>{{ labels.parity }}</span>
              <select
                name="bus-parity"
                :value="draft.bus.parity"
                :title="form.parity_tooltip"
                @change="bus('parity', text($event) as BusValues['parity'])"
              >
                <option v-for="item in form.parities" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
          </template>
          <template v-else>
            <label class="field">
              <span>{{ labels.host }}</span>
              <input name="bus-host" type="text" spellcheck="false" :value="draft.bus.host" @input="bus('host', text($event))" />
            </label>
            <label class="field">
              <span>{{ labels.tcp_port }}</span>
              <input
                name="bus-tcp-port"
                type="number"
                class="numeric"
                :min="form.tcp_port_min"
                :max="form.tcp_port_max"
                :value="draft.bus.tcp_port"
                @change="bus('tcp_port', number($event))"
              />
            </label>
          </template>
          <label class="field">
            <span>{{ labels.poll_cycle_seconds }}</span>
            <span class="unit">
              <input
                name="bus-poll-cycle"
                type="number"
                class="numeric"
                :min="form.poll_min"
                :max="form.poll_max"
                :step="step"
                :title="form.poll_tooltip"
                :value="draft.bus.poll_cycle_seconds"
                @change="bus('poll_cycle_seconds', number($event))"
              />
              s
            </span>
          </label>
          <p class="muted small hint">{{ form.poll_hint }}</p>
        </div>
      </section>

      <section class="panel section" data-role="devices">
        <h2 class="panel-title">设备登记</h2>
        <table class="devices">
          <thead>
            <tr>
              <th v-for="column in form.device_columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in draft.rows" :key="index" :data-row="index">
              <td>
                <input
                  :name="`device-name-${index}`"
                  type="text"
                  :placeholder="form.name_placeholders[index]"
                  :value="item.name"
                  @input="row(index, 'name', text($event))"
                />
              </td>
              <td>
                <input
                  :name="`device-slave-${index}`"
                  type="number"
                  class="numeric"
                  :min="form.slave_min"
                  :max="form.slave_max"
                  :value="item.slave_id"
                  @change="row(index, 'slave_id', number($event))"
                />
              </td>
              <td class="center">
                <input
                  :name="`device-enabled-${index}`"
                  type="checkbox"
                  :title="form.enabled_tooltip"
                  :checked="item.enabled"
                  @change="row(index, 'enabled', checked($event))"
                />
              </td>
              <td class="center">
                <input
                  :name="`device-stop-${index}`"
                  type="checkbox"
                  :title="form.fail_stop_tooltip"
                  :checked="item.auto_stop_on_failure"
                  @change="row(index, 'auto_stop_on_failure', checked($event))"
                />
              </td>
              <td class="file numeric" :title="item.database_path || form.new_database_text">
                {{ item.database_name ?? form.new_database_text }}
                <label v-if="item.database_name === null" class="reuse" :title="form.reuse_tooltip">
                  <input
                    :name="`device-reuse-${index}`"
                    type="checkbox"
                    :checked="item.reuse_existing"
                    @change="row(index, 'reuse_existing', checked($event))"
                  />
                  {{ form.reuse_label }}
                </label>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="actions">
          <button
            type="button"
            class="primary"
            data-role="config-save"
            :title="form.save_tooltip"
            :disabled="state.saving.loading"
            @click="props.store.save()"
          >
            {{ state.saving.loading ? "正在保存…" : form.save_label }}
          </button>
          <button v-if="state.dirty" type="button" data-role="config-reset" @click="props.store.resetDraft()">撤销修改</button>
        </div>
        <p v-if="!running && !state.reconfiguring" class="muted small" data-role="save-needs-running">
          {{ form.save_requires_running }}
        </p>
        <div v-if="running && applyError" class="refused" role="alert" data-role="apply-failed">
          <strong class="small">{{ form.apply_failed_text }}</strong>
          <span class="small pre">{{ applyError }}</span>
        </div>
        <p v-else-if="state.saved && !state.saving.error" class="done small" role="status" data-role="config-saved">
          {{ form.saved_text }}
        </p>
        <div v-if="state.saving.error" class="refused" data-role="config-error">
          <strong class="small">{{ form.error_title }}</strong>
          <ErrorNotice
            :error="state.saving.error"
            keeping="表单保留填写的内容"
            :busy="state.saving.loading"
            @retry="props.store.save()"
          />
        </div>
      </section>

      <!-- issue 119: hidden from customers; the import itself stays (issue 120 decides what becomes of it) -->
      <section v-if="SHOW_V103_IMPORT" class="panel section" data-role="import">
        <h2 class="panel-title">从 V1.0.3 配置导入副本</h2>
        <div class="import-row">
          <input
            name="import-path"
            type="text"
            spellcheck="false"
            placeholder="V1.0.3 程序目录，或其中的 config/app_config.json"
            :value="state.importPath"
            @input="props.store.setImportPath(text($event))"
          />
          <button
            type="button"
            data-role="import-preview"
            :disabled="state.importing.loading || state.importPath.trim() === ''"
            @click="props.store.previewImport()"
          >
            {{ state.importing.loading ? "正在读取…" : "读取预览" }}
          </button>
        </div>
        <ErrorNotice :error="state.importing.error" :busy="state.importing.loading" @retry="state.importing.retry?.()" />
        <template v-if="preview">
          <p class="muted small path" :title="preview.source_path">来源：{{ preview.source_path }}</p>
          <table class="devices preview" data-role="import-devices">
            <thead>
              <tr>
                <th>{{ form.device_columns[0] }}</th>
                <th>{{ form.device_columns[1] }}</th>
                <th>{{ form.device_columns[2] }}</th>
                <th>导入</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in preview.devices" :key="item.name" :class="{ blocked: !item.importable }">
                <td>{{ item.name }}</td>
                <td class="numeric">{{ item.slave_id }}</td>
                <td>{{ item.enabled ? "是" : "否" }}</td>
                <td :title="item.problem ?? item.source_database_path">{{ item.problem ?? "可导入" }}</td>
              </tr>
            </tbody>
          </table>
          <p class="small note">{{ preview.note }}</p>
          <div class="actions">
            <button type="button" class="primary" data-role="import-apply" @click="props.store.applyImport()">放入表单</button>
            <button type="button" @click="props.store.closeImport()">关闭预览</button>
          </div>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.editor {
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
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.field {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: var(--space-2);
  align-items: center;
}
.port-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2);
}
.combo {
  position: relative;
  display: flex;
  min-width: 0;
}
.combo input {
  flex: 1;
  min-width: 0;
  padding-right: calc(var(--control-height) + var(--space-1));
}
.toggle {
  position: absolute;
  top: 0;
  right: 0;
  width: var(--control-height);
  height: var(--control-height);
  padding: 0;
  border-color: transparent;
  background: transparent;
}
.ports {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 5;
  max-height: calc(var(--table-row-height) * 8);
  margin: 2px 0 0;
  padding: var(--space-1) 0;
  overflow-y: auto;
  list-style: none;
  border: var(--border-width) solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface);
  box-shadow: var(--elevation-1);
  font-size: var(--font-size-sm);
}
.ports li {
  padding: 2px var(--space-2);
  line-height: var(--table-row-height);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
.ports li:hover,
.ports li.active,
.ports li[aria-selected="true"] {
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
.ports li.empty {
  color: var(--color-on-surface-variant);
  cursor: default;
  white-space: normal;
}
.ports li.empty:hover {
  background: transparent;
  color: var(--color-on-surface-variant);
}
.unit {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.hint {
  margin: 0 0 0 128px;
}
.small {
  margin: 0;
  font-size: var(--font-size-sm);
}
.path {
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
  padding: 2px var(--space-2);
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
.devices input[type="text"],
.devices input[type="number"] {
  width: 100%;
}
.devices input[type="checkbox"] {
  height: auto;
}
.center {
  text-align: center;
}
.reuse {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  white-space: nowrap;
}
.preview tr.blocked td {
  color: var(--color-error);
}
.actions {
  display: flex;
  gap: var(--space-2);
  justify-content: center;
  padding: var(--space-1) 0;
}
.actions .primary {
  min-width: 220px;
  font-weight: var(--font-weight-bold);
}
.done {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
.refused {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  color: var(--color-error);
}
.import-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2);
}
.note,
.pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.problem {
  border-left: var(--border-width) solid var(--color-error);
  color: var(--color-error);
}
.problem .muted {
  color: var(--color-on-surface-variant);
}
.notice {
  margin: 0;
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
</style>
