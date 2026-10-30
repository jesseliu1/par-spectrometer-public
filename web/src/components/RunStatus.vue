<script setup lang="ts">
/**
 * The top bar's run status (issue #73; UI-253): V1.0.3's "总线：… ｜ 采集…" at the right of the device bar, the bus
 * message on hover, the acquisition state in bold. Long states wrap within a width limit instead of being cut
 * (UI-043). The failure lines below the bar are App's (UI-252). Colours are the level tokens; ok is body text, as
 * everywhere in the 2.0 UI (tokens.css; V1.0.3 drew it green, D-227 item 3).
 */
import { withNotice, type RunView } from "../lib/runStatus";

const props = defineProps<{ view: RunView }>();
</script>

<template>
  <div class="run" data-role="run-status" role="status">
    <template v-if="props.view.bus">
      <span class="bus" :class="props.view.bus.level" :title="withNotice(props.view.bus.detail, props.view.bus.notice)" data-role="run-bus">{{
        props.view.bus.text
      }}</span>
      <span class="separator" aria-hidden="true">｜</span>
    </template>
    <span
      class="acquisition"
      :class="props.view.acquisition.level"
      :title="withNotice(props.view.acquisition.text, props.view.acquisition.notice)"
      data-role="run-acquisition"
      >{{ props.view.acquisition.text }}</span
    >
  </div>
</template>

<style scoped>
.run {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-left: auto;
  padding: var(--space-1) 0;
  font-size: var(--font-size-sm);
}
.bus {
  max-width: 300px;
}
.acquisition {
  max-width: 320px;
  font-weight: var(--font-weight-bold);
}
.separator {
  color: var(--color-on-surface-variant);
}
.ok {
  color: var(--color-on-surface);
}
.warn {
  color: var(--color-warning);
}
.error {
  color: var(--color-error);
}
.muted {
  color: var(--color-on-surface-variant);
}
.info {
  color: var(--color-primary);
}
.maintenance {
  color: var(--color-maintenance);
}
</style>
