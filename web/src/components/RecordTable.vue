<script setup lang="ts">
/** The history list: five columns (UI-028), one header line for the time (UI-020), no paging (UI-046, D-201). */
import type { HistoryItem } from "../api/types";

const props = defineProps<{ items: HistoryItem[]; selectedId: number | null }>();
const emit = defineEmits<{ select: [id: number] }>();

function move(event: KeyboardEvent, index: number): void {
  const next = event.key === "ArrowDown" ? index + 1 : event.key === "ArrowUp" ? index - 1 : -1;
  const item = props.items[next];
  if (!item) return;
  event.preventDefault();
  emit("select", item.id);
  const row = (event.currentTarget as HTMLElement).parentElement?.children[next] as HTMLElement | undefined;
  row?.focus();
}
</script>

<template>
  <div class="scroller">
    <table class="records">
      <thead>
        <tr>
          <th class="seq">序号</th>
          <th class="id">ID</th>
          <th class="time">采集时间（北京时间）</th>
          <th class="result">采集结果</th>
          <th class="exposure">曝光状态</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(item, index) in props.items"
          :key="item.id"
          :class="{ selected: item.id === props.selectedId }"
          :aria-selected="item.id === props.selectedId"
          :data-id="item.id"
          tabindex="0"
          @click="emit('select', item.id)"
          @keydown.enter="emit('select', item.id)"
          @keydown.up="move($event, index)"
          @keydown.down="move($event, index)"
        >
          <td class="numeric">{{ item.seq }}</td>
          <td class="numeric">{{ item.id }}</td>
          <td class="numeric">{{ item.acquired_at_text }}</td>
          <td :class="item.success ? 'ok' : 'failed'">{{ item.result_text }}</td>
          <td :class="{ warn: item.exposure_style === 'warn' }">{{ item.exposure_text }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="props.items.length === 0" class="empty muted">所选范围内没有记录</p>
  </div>
</template>

<style scoped>
.scroller {
  overflow: auto;
  min-height: 0;
  flex: 1;
}
.records {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
th,
td {
  height: var(--table-row-height);
  padding: 0 var(--space-2);
  text-align: center;
  white-space: nowrap;
  border-bottom: var(--border-width) solid var(--color-outline-variant);
}
th {
  position: sticky;
  top: 0;
  background: var(--color-surface-container);
  color: var(--color-on-surface-variant);
  font-weight: var(--font-weight-medium);
}
tbody tr {
  cursor: pointer;
}
tbody tr:hover {
  background: var(--color-surface-container-low);
}
tbody tr.selected {
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
.ok {
  color: var(--color-success);
}
.failed {
  color: var(--color-error);
}
.warn {
  color: var(--color-warning);
}
tr.selected .ok,
tr.selected .failed,
tr.selected .warn {
  font-weight: var(--font-weight-medium);
}
/* the plain status colours are below 4.5:1 on the selected row's background (review of PR #48, M-1) */
tr.selected .ok {
  color: var(--color-selected-success);
}
tr.selected .failed {
  color: var(--color-selected-error);
}
tr.selected .warn {
  color: var(--color-selected-warning);
}
.empty {
  padding: var(--space-4);
  text-align: center;
}
</style>
