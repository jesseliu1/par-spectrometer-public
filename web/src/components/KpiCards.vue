<script setup lang="ts">
/** Six metric cards of the selected record (UI-012 set and order); texts as the service gives them. */
import { computed } from "vue";
import type { MetricGroup } from "../api/types";
import { EM_DASH, kpis } from "../lib/kpis";

const props = defineProps<{ groups: MetricGroup[] | null }>();
const cards = computed(() => kpis(props.groups));
</script>

<template>
  <section class="kpis-wrap" aria-label="主要指标">
    <div class="kpis">
      <article v-for="card in cards" :key="card.key" class="panel kpi" :data-key="card.key">
        <span class="label muted">{{ card.label }}</span>
        <span class="value numeric">{{ card.text }}</span>
        <span class="unit muted">{{ card.text === EM_DASH ? "" : card.unit }}</span>
      </article>
    </div>
  </section>
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
/* six in a row once the available width reaches 1500 px, else two rows of three; the font never shrinks (UI-011,
   the overview rule, reused here) */
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
}
.unit {
  font-size: var(--font-size-xs);
  min-height: 1em;
}
</style>
