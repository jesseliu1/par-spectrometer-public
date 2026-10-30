<script setup lang="ts">
/**
 * 日志详情 (V1.0.3 MainWindow._show_settings_log_details; UI-100..104): the snapshot of the double-clicked row as
 * the service wrote it, plain text and selectable, with 复制全部 and 关闭. The text is the one passed when the
 * dialog opened, so a background refresh never replaces it (UI-102). Nothing here asks the device for anything.
 */
import { nextTick, onMounted, ref } from "vue";

const props = defineProps<{ title: string; text: string; copyLabel: string }>();
const emit = defineEmits<{ close: [] }>();
const close = ref<HTMLButtonElement | null>(null);
const copyError = ref<string | null>(null);
const COPY_FAILED = "复制失败，请选中文字后手动复制";

onMounted(async () => {
  await nextTick();
  close.value?.focus();
});

async function copyAll(): Promise<void> {
  copyError.value = null;
  try {
    await navigator.clipboard.writeText(props.text);
  } catch (error) {
    copyError.value = `${COPY_FAILED}（${String(error)}）`;
  }
}
</script>

<template>
  <div class="scrim" @click.self="emit('close')" @keydown.esc="emit('close')">
    <div class="dialog panel" role="dialog" aria-modal="true" :aria-label="props.title" data-role="log-details">
      <h2 class="panel-title">{{ props.title }}</h2>
      <pre class="text" data-role="log-details-text">{{ props.text }}</pre>
      <p v-if="copyError" class="copy-error" role="alert">{{ copyError }}</p>
      <div class="buttons">
        <button type="button" data-role="log-copy" @click="copyAll()">{{ props.copyLabel }}</button>
        <button ref="close" type="button" data-role="log-close" @click="emit('close')">关闭</button>
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
  width: min(820px, 90vw);
  height: min(520px, 90vh);
  padding: var(--space-4);
}
.text {
  flex: 1;
  margin: 0;
  padding: var(--space-2);
  overflow: auto;
  border: var(--border-width) solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  font-family: inherit;
  font-size: var(--font-size-sm);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  user-select: text;
}
.copy-error {
  margin: 0;
  color: var(--color-error);
  font-size: var(--font-size-sm);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
