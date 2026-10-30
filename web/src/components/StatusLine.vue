<script setup lang="ts">
/**
 * Bottom status line. Its left block is the mode as the service writes it (16_ 4.4: 只读模式 / 采集模式 · 未在采集 /
 * 正在开始 / 正在采集 / 正在停止 / 锁停), always shown, coloured by the service's level token. Before the service's
 * text is known it names the mode from the health tier alone (tier 0: the read-only text, S-4).
 */
import type { TierState } from "../api/types";
import { serviceTime } from "../lib/view";

const props = defineProps<{
  asOf: string | null;
  /** the viewed device's data source (issue #82: the alpha's own device database), null without a device */
  sourceText: string | null;
  tier: number | null;
  tierState?: TierState | null;
}>();
</script>

<template>
  <footer class="status" role="status">
    <span v-if="props.tierState" class="mode tier" :class="props.tierState.level" data-role="tier-text">{{
      props.tierState.text
    }}</span>
    <template v-else>
      <span v-if="props.tier !== null && props.tier > 0" class="mode" data-role="tier-fallback">{{
        props.tier === 2 ? "维护模式" : "采集模式"
      }}</span>
      <span v-else-if="props.tier === 0" class="mode" data-role="tier-fallback">只读模式 · 不连接设备</span>
      <span v-else class="mode muted" data-role="tier-fallback">正在读取状态…</span>
    </template>
    <span v-if="props.sourceText" class="muted source" :title="props.sourceText">{{ props.sourceText }}</span>
    <span class="spacer"></span>
    <span v-if="props.asOf" class="muted numeric"><span title="页面最近一次从软件读到数据的时间；页面刷新或操作时更新">数据更新于 {{ serviceTime(props.asOf) }}（北京时间）</span></span>
  </footer>
</template>

<style scoped>
.status {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  height: var(--status-height);
  padding: 0 var(--space-4);
  background: var(--color-surface-container);
  border-top: var(--border-width) solid var(--color-outline-variant);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}
.mode {
  font-weight: var(--font-weight-medium);
}
.tier {
  padding: 0 var(--space-2);
  border-radius: var(--radius-control);
}
.tier.muted {
  color: var(--color-on-surface-variant);
}
.tier.info {
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
.tier.warn {
  background: var(--color-warning-container);
  color: var(--color-on-warning-container);
}
.tier.maintenance {
  background: var(--color-maintenance-container);
  color: var(--color-on-maintenance-container);
}
.tier.error {
  background: var(--color-error-container);
  color: var(--color-on-error-container);
}
.source {
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.spacer {
  flex: 1;
}
</style>
