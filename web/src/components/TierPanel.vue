<script setup lang="ts">
/**
 * 设置页“设备维护模式” (16_ 4.2-4.4, 17_ 6.1; issue 119): the service's mode text and the maintenance switch. Since
 * issue 119 the product starts in tier 1 and the page offers no way back to tier 0: from tier 1, 开启维护模式 opens
 * the two confirmation layers (the service issues them; a hidden button is not a confirmation); 2 → 1 asks once
 * (maintenance stays as it is). 开启采集 is shown only if the settings file still says tier 0 (written by an earlier
 * version or the self-test). When the tier reads 0 while a takeover is still not released (settings file
 * unreadable or changed, D-215), 停止采集 replaces it (PR #54 review M2).
 */
import { computed } from "vue";
import type { TakeoverStore } from "../pages/takeoverStore";
import ErrorNotice from "./ErrorNotice.vue";

const props = defineProps<{ store: TakeoverStore }>();
const state = props.store.state;
const tier = computed(() => state.tier.data);
const heldOver = computed(() => props.store.heldOver());
const busy = computed(
  () =>
    state.confirming.loading ||
    state.tierChange.loading ||
    tier.value === null ||
    tier.value.takeover === "starting" ||
    tier.value.takeover === "stopping",
);

function choose(target: number): void {
  if (tier.value === null || target === tier.value.tier) return;
  void props.store.askTier(target);
}
</script>

<template>
  <section class="panel section" data-role="tier-panel">
    <h2 class="panel-title">设备维护模式</h2>
    <div class="row">
      <span v-if="tier" class="tier" :class="tier.level" data-role="tier-current">{{ tier.text }}</span>
      <button
        v-if="heldOver"
        type="button"
        data-role="tier-stop"
        :disabled="tier?.takeover !== 'running' || state.action.loading"
        @click="props.store.askStop()"
      >
        停止采集…
      </button>
      <button
        v-else-if="tier && tier.tier === 0"
        type="button"
        class="primary"
        data-role="tier-up"
        :disabled="busy"
        @click="choose(1)"
      >
        开启采集…
      </button>
      <button
        v-if="tier && tier.tier === 1"
        type="button"
        class="primary"
        data-role="tier-up-2"
        :disabled="busy"
        @click="choose(2)"
      >
        开启维护模式…
      </button>
      <button v-if="tier && tier.tier === 2" type="button" data-role="tier-down-1" :disabled="busy" @click="choose(1)">
        关闭维护模式…
      </button>
    </div>
    <p class="muted small">
      本软件打开后自动开始采集，可在“实时概览”手动开始或停止。维护模式另开放“设备维护”页（诊断、校准与通信参数写入），供工程人员使用，开启前需确认两次。
    </p>
    <p v-if="heldOver" class="problem small" role="alert" data-role="tier-held-over">
      设置显示为只读模式，但采集仍在运行并占用串口。请先停止采集；停止前不能开始采集或保存配置。
    </p>
    <p v-if="tier?.settings_problem" class="problem small" role="alert" data-role="settings-problem">设置文件无法读取，按默认的采集模式运行：{{ tier.settings_problem }}</p>
    <p v-if="tier" class="muted small path" data-role="settings-path" :title="tier.settings_path">
      设置文件：{{ tier.settings_path }}
    </p>
    <ErrorNotice
      :error="state.tier.error"
      :keeping="tier ? '仍显示上次读取的模式' : null"
      :busy="state.tier.loading"
      @retry="state.tier.retry?.()"
    />
    <ErrorNotice :error="state.confirming.error" :busy="state.confirming.loading" @retry="state.confirming.retry?.()" />
    <ErrorNotice v-if="heldOver" :error="state.action.error" :busy="state.action.loading" @retry="state.action.retry?.()" />
    <ErrorNotice :error="state.tierChange.error" :busy="state.tierChange.loading" @retry="state.tierChange.retry?.()" />
  </section>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
}
.row {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  flex-wrap: wrap;
}
.tier {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-control);
  font-size: var(--font-size-sm);
}
.tier.muted {
  background: var(--color-surface-container);
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
.small {
  margin: 0;
  font-size: var(--font-size-sm);
}
.path {
  overflow-wrap: anywhere;
}
.problem {
  color: var(--color-error);
}
</style>
