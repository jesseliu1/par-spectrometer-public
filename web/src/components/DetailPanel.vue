<script setup lang="ts">
/**
 * Record detail: title "记录详情 · 设备名称 · #ID", full Beijing time, elapsed and review (UI-036), then the 7 groups
 * of 54 values (API-06). A failed record shows "—" for every value but keeps elapsed and review (UI-030).
 */
import type { AcquisitionDetail } from "../api/types";

const props = defineProps<{ detail: AcquisitionDetail | null }>();
</script>

<template>
  <section class="panel detail" aria-label="记录详情">
    <template v-if="props.detail">
      <header class="head">
        <h2 class="panel-title">{{ props.detail.header.title }}</h2>
        <dl class="facts">
          <div><dt>采集时间</dt><dd class="numeric">{{ props.detail.header.time_text }}</dd></div>
          <div>
            <dt>采集状态</dt>
            <dd :class="props.detail.header.status_level">{{ props.detail.header.status_text }}</dd>
          </div>
          <div><dt>曝光</dt><dd>{{ props.detail.header.exposure_text }}</dd></div>
          <div><dt>采集耗时（ms）</dt><dd class="numeric">{{ props.detail.elapsed_text }}</dd></div>
          <div><dt>采集校验</dt><dd>{{ props.detail.review_text }}</dd></div>
        </dl>
      </header>
      <div class="groups">
        <section v-for="group in props.detail.groups" :key="group.title" class="group">
          <h3>{{ group.title }}</h3>
          <dl>
            <div v-for="item in group.items" :key="item.key" class="item" :data-key="item.key">
              <dt>{{ item.label }}<span v-if="item.unit" class="unit">（{{ item.unit }}）</span></dt>
              <dd class="numeric">{{ item.text }}</dd>
            </div>
          </dl>
        </section>
      </div>
    </template>
    <p v-else class="empty muted">记录详情 · 未选择记录</p>
  </section>
</template>

<style scoped>
.detail {
  padding: var(--space-3);
  min-height: 0;
}
.head {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
}
.facts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-5);
  margin: 0;
  font-size: var(--font-size-sm);
}
.facts div {
  display: flex;
  gap: var(--space-2);
}
dt {
  color: var(--color-on-surface-variant);
}
dd {
  margin: 0;
}
.ok {
  color: var(--color-success);
}
.warn {
  color: var(--color-warning);
}
.error {
  color: var(--color-error);
}
.groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--space-3) var(--space-5);
  padding-top: var(--space-3);
}
.group h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
}
.group dl {
  margin: 0;
}
.item {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 2px 0;
  border-bottom: var(--border-width) dashed var(--color-outline-variant);
  font-size: var(--font-size-sm);
}
.unit {
  font-size: var(--font-size-xs);
}
.empty {
  margin: 0;
  padding: var(--space-4);
}
</style>
