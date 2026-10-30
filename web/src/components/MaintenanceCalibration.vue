<script setup lang="ts">
/**
 * 光谱校准 (V1.0.3 calibration editor inside the maintenance window): 从硬件读取 / 写入硬件并回读 / 放弃待写入修改, the
 * preview with draggable nodes, the 13 fields and 校准信息. A field sends what was typed when it is committed (change
 * event); the service rounds it to the box's decimals and answers the new values (17_ 3.3). Nothing is computed here.
 */
import { computed, reactive } from "vue";
import type { CalibrationField, MaintenanceCalibration } from "../api/types";
import CalibrationChart from "./CalibrationChart.vue";

const props = defineProps<{ calibration: MaintenanceCalibration; busy: boolean }>();
const emit = defineEmits<{
  read: [];
  write: [];
  discard: [];
  edit: [name: string, value: number];
  drag: [index: number, x: number, y: number];
}>();

const byName = computed(() => new Map(props.calibration.fields.map((field) => [field.name, field])));
const NODES = [
  ["P0", "x_min", "y0"],
  ["P1", "x1", "y1"],
  ["P2", "x2", "y2"],
  ["P3", "x3", "y3"],
  ["P4", "x_max", "y4"],
] as const;
const GLOBALS = ["k_global", "limit_min", "limit_max"] as const;

/** What is being typed and not yet committed: the service's view refreshes on every event and must not overwrite it. */
const typed = reactive<Record<string, string>>({});

function field(name: string): CalibrationField | undefined {
  return byName.value.get(name);
}

function shown(name: string): string {
  return typed[name] ?? field(name)?.text ?? "";
}

function type(name: string, event: Event): void {
  typed[name] = (event.target as HTMLInputElement).value;
}

function commit(name: string, event: Event): void {
  const input = event.target as HTMLInputElement;
  const value = Number.parseFloat(input.value);
  delete typed[name];
  if (Number.isFinite(value)) emit("edit", name, value);
  else input.value = field(name)?.text ?? "";
}

function step(decimals: number): string {
  return (10 ** -decimals).toFixed(decimals);
}
</script>

<template>
  <section class="calibration" data-role="calibration">
    <div class="actions">
      <button
        type="button"
        class="secondary"
        data-role="calibration-read"
        :disabled="!props.calibration.read_enabled || props.busy"
        :title="props.calibration.unavailable_reason || undefined"
        @click="emit('read')"
      >
        从硬件读取
      </button>
      <button
        type="button"
        class="primary"
        data-role="calibration-write"
        :disabled="!props.calibration.write_enabled || props.busy"
        @click="emit('write')"
      >
        写入硬件并回读
      </button>
      <button
        type="button"
        data-role="calibration-discard"
        :disabled="!props.calibration.discard_enabled || props.busy"
        @click="emit('discard')"
      >
        放弃待写入修改
      </button>
      <span class="spacer"></span>
      <span v-if="props.calibration.history" class="history" data-role="calibration-history">历史值（本次读取失败）</span>
      <span
        v-if="props.calibration.value_state"
        class="value-state"
        :class="{ error: props.calibration.value_state_error }"
        data-role="calibration-value-state"
        >{{ props.calibration.value_state }}</span
      >
    </div>
    <CalibrationChart
      :curve="props.calibration.curve"
      :editable="props.calibration.editable && !props.busy"
      :message="props.calibration.out_of_order ? props.calibration.out_of_order_text : null"
      @drag="(index, x, y) => emit('drag', index, x, y)"
    />
    <div class="details">
      <fieldset class="group">
        <legend>校准节点（硬件对象 ID：3）</legend>
        <div class="grid">
          <span class="head">节点</span>
          <span class="head">波长 (nm)</span>
          <span class="head">修正值 (%)</span>
          <template v-for="[label, x, y] in NODES" :key="label">
            <span>{{ label }}</span>
            <label class="field">
              <span class="muted">{{ x }}</span>
              <input
                type="number"
                class="numeric"
                :name="`calibration-${x}`"
                :value="shown(x)"
                @input="type(x, $event)"
                :step="step(field(x)?.decimals ?? 1)"
                :disabled="!field(x)?.enabled || props.busy"
                @change="commit(x, $event)"
              />
            </label>
            <label class="field">
              <span class="muted">{{ y }}</span>
              <input
                type="number"
                class="numeric"
                :name="`calibration-${y}`"
                :value="shown(y)"
                @input="type(y, $event)"
                :step="step(field(y)?.decimals ?? 2)"
                :disabled="!field(y)?.enabled || props.busy"
                @change="commit(y, $event)"
              />
            </label>
          </template>
        </div>
      </fieldset>
      <fieldset class="group">
        <legend>全局参数</legend>
        <label v-for="name in GLOBALS" :key="name" class="field global">
          <span>{{ field(name)?.caption }}</span>
          <span class="muted">{{ name }}</span>
          <input
            type="number"
            class="numeric"
            :name="`calibration-${name}`"
            :value="shown(name)"
            @input="type(name, $event)"
            :step="step(field(name)?.decimals ?? 2)"
            :disabled="!field(name)?.enabled || props.busy"
            @change="commit(name, $event)"
          />
        </label>
      </fieldset>
      <fieldset class="group info" data-role="calibration-info">
        <legend>校准信息</legend>
        <span :title="props.calibration.status_tooltip || undefined">{{ props.calibration.status }}</span>
        <span :title="props.calibration.error_tooltip || undefined">{{ props.calibration.error }}</span>
        <span>{{ props.calibration.version_text }}</span>
        <span class="muted">上次校准时间（北京时间）</span>
        <span class="numeric">{{ props.calibration.time }}</span>
      </fieldset>
    </div>
    <p v-if="props.calibration.note" class="note" :class="{ error: props.calibration.note_error }" data-role="calibration-note">
      {{ props.calibration.note }}
    </p>
  </section>
</template>

<style scoped>
.calibration {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.actions {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.spacer {
  flex: 1;
}
.value-state,
.history {
  font-size: var(--font-size-sm);
  color: var(--color-on-surface-variant);
}
.value-state.error,
.history {
  color: var(--color-error);
}
.details {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}
.group {
  border: var(--border-width) solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  padding: var(--space-2) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.grid {
  display: grid;
  grid-template-columns: auto auto auto;
  gap: var(--space-1) var(--space-4);
  align-items: center;
}
.head {
  font-size: var(--font-size-sm);
  color: var(--color-on-surface-variant);
}
.field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.field input {
  width: 112px;
}
.global span:first-child {
  width: 96px;
}
.info {
  min-width: 220px;
  font-size: var(--font-size-sm);
}
.note {
  margin: 0;
  color: var(--color-on-surface-variant);
}
.note.error {
  color: var(--color-error);
}
</style>
