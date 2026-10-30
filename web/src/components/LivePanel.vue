<script setup lang="ts">
/**
 * 实时概览 in tier 1: the takeover and the bus as the service reports them (16_ section 6), 开始采集 / 停止采集
 * (stopping asks first), the live devices to view, and V1.0.3's halt message in a red banner whose 确认 only closes
 * it: there is no control that clears a halt (red line); stopping and starting again builds a new coordinator.
 * Maintenance left unfinished pauses acquisition; tier 1 cannot end it (that is tier 2). A start refused with
 * nobody clicking (the automatic start when the service starts, issue #92) shows the status's reason here.
 */
import { computed } from "vue";
import type { TakeoverStore } from "../pages/takeoverStore";
import { noticeText, withNotice } from "../lib/runStatus";
import { positionNumber } from "../lib/view";
import ErrorNotice from "./ErrorNotice.vue";

export interface LiveDeviceItem {
  key: string;
  name: string;
  text: string;
  level: string;
}

const props = defineProps<{ store: TakeoverStore; devices: LiveDeviceItem[]; selected: string | null }>();
const emit = defineEmits<{ select: [key: string] }>();
const state = props.store.state;
const tier = computed(() => state.tier.data);
const status = computed(() => state.status.data);
const takeover = computed(() => tier.value?.takeover ?? "released");
const halt = computed(() => (props.store.haltVisible() ? (status.value?.halt ?? null) : null));
/** Why the last start was refused, when no request of this page reports it (the automatic start, issue #92). */
const refused = computed(() =>
  takeover.value === "released" && !state.action.error ? (status.value?.error ?? null) : null,
);
/** issue 136: a start refused by a click shows the action's error; its record is the status's error_notice. */
const actionNotice = computed(() => {
  const error = state.action.error;
  const refusedText = status.value?.error;
  if (!error || takeover.value !== "released" || !refusedText || !error.message.startsWith(refusedText)) return null;
  return status.value?.error_notice ?? null;
});
// the coordinator's own messages already say "总线已连接" / "总线连接失败：…"; others ("正在连接 COM3 …") get the label
/** issue 131: no enabled device answers; the same 总线：异常 as the top bar, with why. */
const silent = computed(() => (status.value?.run_status?.bus.devices_silent ? status.value.run_status.bus : null));
const busText = computed(() => {
  if (silent.value) return `${silent.value.text}（${silent.value.detail}）`;
  const message = status.value?.bus.message ?? "—";
  return message.startsWith("总线") ? message : `总线：${message}`;
});
/** issue 136: say when run events did not reach logs/events.jsonl; the shown notices still go into a bundle. */
const eventLogProblem = computed(() => {
  const health = status.value?.event_log;
  if (!health || (health.dropped === 0 && health.failed === 0)) return null;
  const parts = [];
  if (health.dropped) parts.push(`${health.dropped} 条因写盘排满未写入`);
  if (health.failed) parts.push(`${health.failed} 条写盘失败（${health.last_error ?? "原因未知"}）`);
  return `运行日志有记录未写入文件：${parts.join("；")}。当前提示的记录号仍在，导出诊断包时会补上。`;
});
const busLevel = computed(() => {
  if (silent.value) return "error";
  const level = status.value?.bus.level ?? "idle";
  return level === "ok" ? "ok" : level === "error" ? "error" : level === "warning" ? "warn" : "idle";
});
</script>

<template>
  <section class="panel live" data-role="live">
    <header class="head">
      <h2 class="panel-title">采集控制</h2>
      <span v-if="tier" class="state" :class="tier.level" data-role="takeover-text">{{ tier.text }}</span>
      <span class="spacer"></span>
      <button
        type="button"
        class="primary"
        data-role="start"
        :disabled="takeover !== 'released' || state.action.loading"
        @click="props.store.start()"
      >
        开始采集
      </button>
      <button
        type="button"
        data-role="stop"
        :disabled="takeover !== 'running' || state.action.loading"
        @click="props.store.askStop()"
      >
        停止采集
      </button>
    </header>
    <p class="bus" :class="busLevel" data-role="bus-state" :title="withNotice(status?.bus.message ?? '', status?.bus.notice)">
      {{ busText }}
    </p>
    <p v-if="eventLogProblem" class="refused small" role="status" data-role="event-log-problem">
      {{ eventLogProblem }}
    </p>
    <p v-if="status?.maintenance" class="maintenance" role="status" data-role="maintenance">
      设备维护尚未完成，采集已暂停。请联系工程人员开启维护模式，在“设备维护”页完成核对。
    </p>
    <p
      v-if="refused"
      class="refused"
      role="alert"
      data-role="start-refused"
      :title="noticeText(status?.error_notice)"
    >
      未能开始采集：{{ refused }}
    </p>
    <ErrorNotice :error="state.action.error" :busy="state.action.loading" @retry="state.action.retry?.()" />
    <p v-if="actionNotice" class="muted small" data-role="action-notice">{{ noticeText(actionNotice) }}</p>
    <ErrorNotice
      :error="state.status.error"
      :keeping="status ? '仍显示上次读取的采集状态' : null"
      :busy="state.status.loading"
      @retry="state.status.retry?.()"
    />
    <div v-if="halt" class="halt" role="alert" data-role="halt">
      <strong>采集已停止（锁停）</strong>
      <p class="halt-text">{{ halt.text }}</p>
      <p v-if="halt.notice" class="halt-notice small" data-role="halt-notice">{{ noticeText(halt.notice) }}</p>
      <div class="halt-actions">
        <button type="button" data-role="halt-ok" @click="props.store.dismissHalt()">确认</button>
      </div>
    </div>
    <nav v-if="props.devices.length" class="devices" aria-label="实时设备" data-role="live-devices">
      <button
        v-for="device in props.devices"
        :key="device.key"
        type="button"
        class="device"
        :class="[device.level, { active: device.key === props.selected }]"
        :aria-pressed="device.key === props.selected"
        :title="device.text"
        :data-key="device.key"
        @click="emit('select', device.key)"
      >
        <span class="position">{{ positionNumber(device.key) }}</span>
        <span class="name">{{ device.name }}</span>
      </button>
    </nav>
    <p v-else class="muted small">还没有登记设备：请在“设置与导出”页填写并保存（需先开始采集）。</p>
  </section>
</template>

<style scoped>
.live {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) var(--space-3);
}
.head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.spacer {
  flex: 1;
}
.refused {
  margin: 0;
  color: var(--color-error);
  font-size: var(--font-size-sm);
}
.state {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-control);
  font-size: var(--font-size-sm);
}
.state.muted {
  background: var(--color-surface-container);
  color: var(--color-on-surface-variant);
}
.state.info {
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
.state.warn {
  background: var(--color-warning-container);
  color: var(--color-on-warning-container);
}
.state.error {
  background: var(--color-error-container);
  color: var(--color-on-error-container);
}
.bus {
  margin: 0;
  font-size: var(--font-size-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bus.ok {
  color: var(--color-on-surface);
}
.bus.warn {
  color: var(--color-warning);
}
.bus.error {
  color: var(--color-error);
}
.bus.idle {
  color: var(--color-on-surface-variant);
}
.maintenance {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-warning-container);
  color: var(--color-on-warning-container);
  font-size: var(--font-size-sm);
}
.halt {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-error-container);
  color: var(--color-on-error-container);
  border: var(--border-width) solid var(--color-error);
}
.halt-text {
  margin: 0;
  white-space: pre-wrap;
  font-size: var(--font-size-sm);
}
.halt-actions {
  display: flex;
  justify-content: flex-end;
}
.devices {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.device {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  max-width: 260px;
}
.device .name {
  overflow: hidden;
  text-overflow: ellipsis;
}
.device .position {
  color: var(--color-on-surface-variant);
}
.device.warning,
.device.warn {
  color: var(--color-warning);
}
.device.error {
  color: var(--color-error);
}
.device.active {
  background: var(--color-primary-container);
  border-color: var(--color-primary);
  color: var(--color-on-primary-container);
}
.small {
  margin: 0;
  font-size: var(--font-size-sm);
}
</style>
