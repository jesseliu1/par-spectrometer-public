<script setup lang="ts">
/** Start/end editing takes effect only on "查询" (UI-049); the end never advances by itself (UI-050). */
import type { RangeInput } from "../lib/timeRange";

const range = defineModel<RangeInput>({ required: true });
const props = defineProps<{ busy: boolean; disabled: boolean; limitReached: boolean; inputError: string | null }>();
const emit = defineEmits<{ query: [] }>();

function update(field: keyof RangeInput, event: Event): void {
  range.value = { ...range.value, [field]: (event.target as HTMLInputElement).value };
}
</script>

<template>
  <form class="query" @submit.prevent="emit('query')">
    <label>
      <span>开始</span>
      <input type="datetime-local" step="1" name="start" :value="range.start" @input="update('start', $event)" />
    </label>
    <label>
      <span>结束</span>
      <input type="datetime-local" step="1" name="end" :value="range.end" @input="update('end', $event)" />
    </label>
    <button class="primary" type="submit" :disabled="props.disabled || props.busy">查询</button>
    <p class="hint" :class="{ warn: props.limitReached }">
      <template v-if="props.inputError">{{ props.inputError }}</template>
      <template v-else-if="props.limitReached">范围内超过 500 条，只显示最近 500 条，请缩小时间范围</template>
      <template v-else>最多显示所选时间范围内最近 500 条记录，超出请缩小时间范围</template>
    </p>
  </form>
</template>

<style scoped>
.query {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: var(--space-2);
}
label {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--color-on-surface-variant);
}
input {
  font-variant-numeric: var(--font-numeric);
}
.hint {
  flex-basis: 100%;
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--color-on-surface-variant);
}
.hint.warn {
  color: var(--color-warning);
}
</style>
