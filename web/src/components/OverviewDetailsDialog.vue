<script setup lang="ts">
/**
 * "全部指标" of the overview (UI-009): the shown record's 7 groups / 54 values (API-06, the history detail's
 * groups) in V1.0.3's three columns 指标 / 数值 / 单位, titled "全部指标 · #ID · time". A failed load keeps what
 * was shown and offers a retry (R-1-5). Esc, a click outside or 关闭 closes it.
 */
import { nextTick, onMounted, ref } from "vue";
import type { ApiError } from "../api/client";
import type { AcquisitionDetail } from "../api/types";
import ErrorNotice from "./ErrorNotice.vue";

const props = defineProps<{
  title: string;
  columns: string[];
  closeText: string;
  detail: AcquisitionDetail | null;
  error: ApiError | null;
  busy: boolean;
}>();
const emit = defineEmits<{ close: []; retry: [] }>();
const close = ref<HTMLButtonElement | null>(null);

onMounted(async () => {
  await nextTick();
  close.value?.focus();
});
</script>

<template>
  <div class="scrim" @click.self="emit('close')" @keydown.esc="emit('close')">
    <div class="dialog panel" role="dialog" aria-modal="true" :aria-label="props.title" data-role="details-dialog">
      <h2 class="panel-title">{{ props.title }}</h2>
      <ErrorNotice
        :error="props.error"
        :keeping="props.detail ? '仍显示上次读取的指标' : null"
        :busy="props.busy"
        @retry="emit('retry')"
      />
      <div class="scroll">
        <table v-if="props.detail">
          <thead>
            <tr>
              <th v-for="column in props.columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody v-for="group in props.detail.groups" :key="group.title">
            <tr class="group">
              <th colspan="3">{{ group.title }}</th>
            </tr>
            <tr v-for="item in group.items" :key="item.key" :data-key="item.key">
              <td>{{ item.label }}</td>
              <td class="numeric">{{ item.text }}</td>
              <td class="muted">{{ item.unit }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="props.busy" class="muted">正在读取…</p>
      </div>
      <div class="buttons">
        <button ref="close" type="button" @click="emit('close')">{{ props.closeText }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrim {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-scrim);
  z-index: 10;
}
.dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  width: min(760px, 90vw);
  max-height: min(720px, 90vh);
  padding: var(--space-4);
}
.scroll {
  overflow-y: auto;
  min-height: 0;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
th,
td {
  text-align: left;
  padding: 2px var(--space-2);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
}
thead th {
  position: sticky;
  top: 0;
  background: var(--color-surface);
}
tr.group th {
  background: var(--color-surface-container);
  font-weight: var(--font-weight-medium);
}
.buttons {
  display: flex;
  justify-content: flex-end;
}
</style>
