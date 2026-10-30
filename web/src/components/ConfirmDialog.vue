<script setup lang="ts">
/**
 * The one confirmation before an acquisition export (EXP-053, EXP-059): V1.0.3's QMessageBox.question text as the
 * service wrote it, with 是 / 否 (否 is the default, as in V1.0.3). Answering 否, Esc or a click outside writes
 * nothing.
 */
import { nextTick, onMounted, ref } from "vue";

const props = defineProps<{ title: string; text: string; single?: boolean }>();
const emit = defineEmits<{ yes: []; no: [] }>();
const no = ref<HTMLButtonElement | null>(null);

onMounted(async () => {
  await nextTick();
  no.value?.focus();
});
</script>

<template>
  <div class="scrim" @click.self="emit('no')" @keydown.esc="emit('no')">
    <div class="dialog panel" role="dialog" aria-modal="true" :aria-label="props.title">
      <h2 class="panel-title">{{ props.title }}</h2>
      <p class="text">{{ props.text }}</p>
      <div class="buttons">
        <button v-if="props.single" ref="no" type="button" data-role="confirm-ok" @click="emit('yes')">确定</button>
        <template v-else>
          <button type="button" class="primary" data-role="confirm-yes" @click="emit('yes')">是</button>
          <button ref="no" type="button" data-role="confirm-no" @click="emit('no')">否</button>
        </template>
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
  width: min(560px, 90vw);
  padding: var(--space-4);
}
.text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
