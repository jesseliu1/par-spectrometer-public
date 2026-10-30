<script setup lang="ts">
/**
 * 设备状态与诊断 (V1.0.3 DeviceMaintenanceDialog page 0): the snapshot lines, the 22 error counters with "较上次读取新增"
 * (counted from this page session, D-134 A), the newest 100 software events with 事件详情, 刷新 and 导出诊断. Texts and
 * enabled states are the service's; 仅显示非零项 only hides rows whose count is 0.
 */
import { computed } from "vue";
import type { MaintenanceDiagnostics } from "../api/types";

const props = defineProps<{ diagnostics: MaintenanceDiagnostics; nonZero: boolean; busy: boolean }>();
const emit = defineEmits<{ refresh: []; export: []; nonZero: [value: boolean]; details: [text: string] }>();
const rows = computed(() => props.diagnostics.rows.filter((row) => !(props.nonZero && row.zero)));
</script>

<template>
  <section class="diagnostics" data-role="diagnostics">
    <div class="actions">
      <button
        type="button"
        data-role="diagnostics-refresh"
        :disabled="!props.diagnostics.refresh_enabled || props.busy"
        :title="props.diagnostics.read_reason || '读取当前设备诊断'"
        @click="emit('refresh')"
      >
        刷新
      </button>
      <button
        type="button"
        data-role="diagnostics-export"
        :disabled="!props.diagnostics.export_enabled || props.busy"
        @click="emit('export')"
      >
        {{ props.diagnostics.export_text }}
      </button>
      <label class="check">
        <input
          type="checkbox"
          name="diagnostics-nonzero"
          :checked="props.nonZero"
          @change="emit('nonZero', ($event.target as HTMLInputElement).checked)"
        />
        仅显示非零项
      </label>
    </div>
    <p v-if="props.diagnostics.read_reason" class="reason" data-role="diagnostics-reason">
      {{ props.diagnostics.read_reason }}
    </p>
    <div class="summary">
      <span data-role="diagnostics-stamp">{{ props.diagnostics.stamp }}</span>
      <span class="numeric" data-role="diagnostics-identity">{{ props.diagnostics.identity }}</span>
      <span class="numeric">{{ props.diagnostics.values }}</span>
      <span class="numeric">{{ props.diagnostics.exposure }}</span>
      <span>{{ props.diagnostics.data }}</span>
    </div>
    <h3 class="heading">硬件错误计数</h3>
    <p v-if="props.diagnostics.has_snapshot && rows.length === 0" class="muted empty">
      {{ props.diagnostics.empty_text }}
    </p>
    <table v-else class="table" data-role="diagnostics-errors">
      <thead>
        <tr>
          <th>类别</th>
          <th>错误项目</th>
          <th>累计次数</th>
          <th>较上次读取新增</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.name" :title="row.tooltip || undefined">
          <td>{{ row.category }}</td>
          <td>{{ row.name }}</td>
          <td class="numeric center">{{ row.count }}</td>
          <td class="numeric center">{{ row.delta }}</td>
        </tr>
      </tbody>
    </table>
    <h3 class="heading">软件事件记录</h3>
    <table class="table events" data-role="diagnostics-events">
      <thead>
        <tr>
          <th>时间</th>
          <th>级别</th>
          <th>操作</th>
          <th>事件内容</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(event, index) in props.diagnostics.events" :key="index" @dblclick="emit('details', event.details)">
          <td class="numeric">{{ event.time }}</td>
          <td class="center">{{ event.level }}</td>
          <td>{{ event.operation }}</td>
          <td class="message" :title="event.message">
            <button type="button" class="link" @click="emit('details', event.details)">{{ event.message }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.diagnostics {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.actions {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.check {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.check input {
  height: auto;
}
.reason {
  margin: 0;
  color: var(--color-on-surface-variant);
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-5);
  font-size: var(--font-size-sm);
}
.heading {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
}
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.table th,
.table td {
  padding: var(--space-1) var(--space-2);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
  text-align: left;
}
.center {
  text-align: center;
}
.events .message {
  max-width: 0;
  width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.link {
  border: none;
  background: transparent;
  padding: 0;
  height: auto;
  color: inherit;
  text-align: left;
  font: inherit;
}
.empty {
  margin: 0;
}
</style>
