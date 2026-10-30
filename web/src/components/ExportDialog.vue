<script setup lang="ts">
/**
 * 导出计算结果 format dialog (EXP-026, UI-233): CSV is ticked at first, Excel can be added; at least one is needed.
 * Cancelling sends nothing, so nothing is created (EXP-021); confirming exports the result shown when the dialog
 * opened (EXP-022, UI-289) into the alpha's output folder named in the dialog (D-207). The dialog never changes
 * the selection (UI-234).
 */
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import type { ExportKind, OperationExportTexts } from "../api/types";

const props = defineProps<{ texts: OperationExportTexts }>();
const emit = defineEmits<{ confirm: [formats: ExportKind[]]; cancel: [] }>();
const chosen = reactive<Record<string, boolean>>(
  Object.fromEntries(props.texts.formats.map((item) => [item.key, item.checked])),
);
const formats = computed(() => props.texts.formats.filter((item) => chosen[item.key]).map((item) => item.key));
const first = ref<HTMLInputElement[] | null>(null);

onMounted(async () => {
  await nextTick();
  first.value?.[0]?.focus();
});
</script>

<template>
  <div class="scrim" @click.self="emit('cancel')" @keydown.esc="emit('cancel')">
    <form class="dialog panel" role="dialog" aria-modal="true" :aria-label="props.texts.title" @submit.prevent="emit('confirm', formats)">
      <h2 class="panel-title">{{ props.texts.title }}</h2>
      <fieldset class="formats">
        <legend>{{ props.texts.formats_label }}</legend>
        <label v-for="item in props.texts.formats" :key="item.key" class="choice">
          <input ref="first" v-model="chosen[item.key]" type="checkbox" :name="item.key" />
          {{ item.label }}
        </label>
      </fieldset>
      <p class="note muted">{{ props.texts.note }}</p>
      <p class="directory numeric" :title="props.texts.directory">{{ props.texts.directory }}</p>
      <div class="buttons">
        <button type="submit" class="primary" :disabled="formats.length === 0">{{ props.texts.confirm_label }}</button>
        <button type="button" @click="emit('cancel')">{{ props.texts.cancel_label }}</button>
      </div>
    </form>
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
  width: min(520px, 90vw);
  padding: var(--space-4);
}
.formats {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border: var(--border-width) solid var(--color-outline-variant);
  border-radius: var(--radius-control);
}
.choice {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.choice input {
  height: auto;
}
.note,
.directory {
  margin: 0;
  font-size: var(--font-size-sm);
}
.directory {
  overflow-wrap: anywhere;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
