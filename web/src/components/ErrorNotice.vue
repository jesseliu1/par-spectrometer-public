<script setup lang="ts">
/** A failed request: what went wrong, that the shown data is the last valid one, and a retry (R-1-5). */
import type { ApiError } from "../api/client";

const props = defineProps<{ error: ApiError | null; keeping?: string | null; busy?: boolean }>();
const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <div v-if="props.error" class="notice" role="alert" :data-code="props.error.code">
    <div class="text">
      <strong>{{ props.error.message }}</strong>
      <span v-if="props.keeping" class="keeping">{{ props.keeping }}</span>
      <span v-if="props.error.detail" class="detail" :title="props.error.detail">{{ props.error.detail }}</span>
    </div>
    <button v-if="props.error.retryable" type="button" :disabled="props.busy" @click="emit('retry')">重试</button>
  </div>
</template>

<style scoped>
.notice {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-error-container);
  color: var(--color-on-error-container);
  font-size: var(--font-size-sm);
}
.text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.detail {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 0.85;
}
</style>
