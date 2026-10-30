<script setup lang="ts">
/**
 * The six summary cards of the overview (UI-012: order and titles), texts exactly as the service wrote them, value
 * and unit together as V1.0.3 shows them ("1234.5 lx"; "—" without a record). Six in a row once the available
 * width reaches 1500 px, else two rows of three; the font never shrinks (UI-011, UI-271).
 */
import type { OverviewKpi } from "../api/types";

const props = defineProps<{ kpis: OverviewKpi[] }>();
</script>

<template>
  <div class="kpis-wrap">
    <div class="kpis" data-role="kpis">
      <article v-for="card in props.kpis" :key="card.key" class="kpi" :data-key="card.key">
        <span class="label muted" :title="card.title">{{ card.title }}</span>
        <span class="value numeric">{{ card.text }}</span>
      </article>
    </div>
  </div>
</template>

<style scoped>
.kpis-wrap {
  container-type: inline-size;
}
.kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}
@container (min-width: 1500px) {
  .kpis {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}
.kpi {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  min-width: 0;
  border: var(--border-width) solid var(--color-outline-variant);
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-control);
  background: var(--color-surface);
}
.label {
  font-size: var(--font-size-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.value {
  font-size: var(--font-size-kpi);
  font-weight: var(--font-weight-medium);
  line-height: 1.15;
  overflow-wrap: anywhere;
}
</style>
