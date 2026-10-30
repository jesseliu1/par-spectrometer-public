<script setup lang="ts">
/** Main navigation of the alpha: the pages migrated so far, in the UI-124 order and with the V1.0.3 tab names.
 * `live` (tier 1): the overview reads the alpha's own device databases, so a page tag (none at present) is not shown (D-214). */
import { PAGES, type PageKey } from "../lib/view";

const props = defineProps<{ view: PageKey; live?: boolean; tier?: number }>();
const shown = () => PAGES.filter((page) => (page.tier ?? 0) <= (props.tier ?? 0));
const emit = defineEmits<{ navigate: [view: PageKey] }>();
</script>

<template>
  <nav class="tabs" aria-label="主导航">
    <button
      v-for="page in shown()"
      :key="page.key"
      type="button"
      class="tab"
      :class="{ active: page.key === props.view }"
      :aria-current="page.key === props.view ? 'page' : undefined"
      :data-view="page.key"
      @click="emit('navigate', page.key)"
    >
      <span class="label">{{ page.label }}</span>
      <span v-if="page.tag && !props.live" class="tag" data-role="snapshot-tag" :title="page.tag.tooltip">{{ page.tag.text }}</span>
    </button>
  </nav>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3) 0;
  background: var(--color-surface);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
}
.tab {
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-md);
  color: var(--color-on-surface-variant);
}
.tag {
  margin-left: var(--space-1);
  padding: 0 var(--space-1);
  border-radius: var(--radius-control);
  background: var(--color-warning-container);
  color: var(--color-on-warning-container);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-regular);
}
.tab.active {
  border-bottom-color: var(--color-primary);
  color: var(--color-on-surface);
  font-weight: var(--font-weight-medium);
}
</style>
