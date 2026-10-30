<script setup lang="ts">
/**
 * 通信参数维护 (V1.0.3 MaintenanceDialog embedded in the maintenance window): 停止全部采集并进入通信维护, then the
 * computer's serial port (typed, D-216 question 9), 读取连接参数, 准备写入的新参数, the isolation declaration and 读取目标
 * 设备 / 确认并写入 / 使用新参数核对. The state line and the identity summary are the service's. While a write waits to be
 * verified the fields show it and cannot change, the declaration too: it keeps the tick this page session gave it, so
 * only the session that wrote can 使用新参数核对 (as V1.0.3, D-218 question 1; the defect is #57).
 */
import type { CommForm, MaintenanceCommunication } from "../api/types";

const props = defineProps<{ communication: MaintenanceCommunication; form: CommForm; busy: boolean }>();
const emit = defineEmits<{ enter: []; read: []; write: []; verify: [] }>();

function number(event: Event): number {
  return Number.parseInt((event.target as HTMLInputElement | HTMLSelectElement).value, 10);
}
</script>

<template>
  <section class="communication" data-role="communication">
    <button
      v-if="props.communication.enter_visible"
      type="button"
      class="danger"
      data-role="maintenance-enter"
      :disabled="!props.communication.enter_enabled || props.busy"
      @click="emit('enter')"
    >
      停止全部采集并进入通信维护
    </button>
    <p class="state" :class="{ attention: props.communication.attention }" data-role="communication-state">
      {{ props.communication.state }}
    </p>
    <label class="row">
      <span class="label">电脑串口</span>
      <input
        v-model="props.form.serial_port"
        name="maintenance-port"
        :disabled="!props.communication.form_enabled"
        autocomplete="off"
      />
    </label>
    <div class="groups">
      <fieldset v-for="[title, key] in [['读取连接参数', 'old'], ['准备写入的新参数', 'new']] as const" :key="key" class="group">
        <legend>{{ title }}</legend>
        <label class="row">
          <span class="label">从站 ID</span>
          <input
            v-model.number="props.form[key].slave_id"
            type="number"
            min="1"
            max="247"
            :name="`maintenance-${key}-slave`"
            :disabled="!props.communication.form_enabled"
          />
        </label>
        <label class="row">
          <span class="label">波特率</span>
          <select
            :name="`maintenance-${key}-baudrate`"
            :value="props.form[key].baudrate"
            :disabled="!props.communication.form_enabled"
            @change="props.form[key].baudrate = number($event)"
          >
            <option v-for="value in props.communication.baudrates" :key="value" :value="value">{{ value }}</option>
          </select>
        </label>
        <label class="row">
          <span class="label">奇偶校验</span>
          <select
            :name="`maintenance-${key}-parity`"
            :value="props.form[key].parity"
            :disabled="!props.communication.form_enabled"
            @change="props.form[key].parity = ($event.target as HTMLSelectElement).value"
          >
            <option v-for="item in props.communication.parities" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>
      </fieldset>
    </div>
    <p class="muted small">{{ props.communication.fixed_parameters }}</p>
    <label class="check">
      <input
        v-model="props.form.isolated"
        type="checkbox"
        name="maintenance-isolated"
        :disabled="!props.communication.isolation_enabled"
      />
      已确认通信链路只连接目标设备
    </label>
    <div class="actions">
      <button
        type="button"
        data-role="comm-read"
        :disabled="!props.communication.read_enabled || props.busy"
        @click="emit('read')"
      >
        读取目标设备
      </button>
      <button
        type="button"
        class="primary"
        data-role="comm-write"
        :disabled="!props.communication.write_enabled || props.busy"
        @click="emit('write')"
      >
        确认并写入
      </button>
      <button
        type="button"
        data-role="comm-verify"
        :disabled="!props.communication.verify_enabled || props.busy"
        @click="emit('verify')"
      >
        使用新参数核对
      </button>
    </div>
    <div class="identity numeric" data-role="comm-identity">
      <p v-for="(line, index) in props.communication.identity" :key="index">{{ line }}</p>
    </div>
  </section>
</template>

<style scoped>
.communication {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: flex-start;
}
.state {
  margin: 0;
  white-space: pre-wrap;
}
.state.attention {
  color: var(--color-error);
}
.row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.label {
  width: 90px;
}
.row input,
.row select {
  width: 180px;
}
.groups {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-5);
}
.group {
  border: var(--border-width) solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  padding: var(--space-2) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.small {
  margin: 0;
  font-size: var(--font-size-sm);
}
.check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.check input {
  height: auto;
}
.actions {
  display: flex;
  gap: var(--space-5);
}
.identity p {
  margin: 0 0 var(--space-1);
  white-space: pre-wrap;
  font-size: var(--font-size-sm);
}
button.danger {
  background: var(--color-error);
  border-color: var(--color-error);
  color: var(--color-on-error);
}
</style>
