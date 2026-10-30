<script setup lang="ts">
/**
 * 设备维护 (tier 2; 内部文档 section 2): V1.0.3's device maintenance window as a page.
 * Top: the maintenance device, its address, communication state and the window's state line (a halt first,
 * MAINT-059). Tabs in V1.0.3's order, the diagnostics tab first (MAINT-014). Bottom: why resuming is refused, the
 * result line (D-158) and 退出通信维护并恢复采集 (only in maintenance). Every write shows the service's confirmation
 * text first (是 / 否, 否 default). There is no control that clears a hardware latch.
 *
 * Opening the page opens the service's single page session (17_ 3.4); leaving the page closes it (with unwritten
 * calibration edits the service asks first, as V1.0.3 does when its window closes).
 */
import { computed, onBeforeUnmount, onMounted } from "vue";
import CalibrationCalibration from "../components/MaintenanceCalibration.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import ErrorNotice from "../components/ErrorNotice.vue";
import MaintenanceComm from "../components/MaintenanceComm.vue";
import MaintenanceDiagnostics from "../components/MaintenanceDiagnostics.vue";
import type { MaintenanceStore } from "./maintenanceStore";
import type { TakeoverStore } from "./takeoverStore";

const TABS = ["设备状态与诊断", "光谱校准", "通信参数维护"] as const;
const props = defineProps<{ store: MaintenanceStore; takeover?: TakeoverStore }>();
const state = props.store.state;
const view = computed(() => state.view.data);
const busy = computed(() => state.action.loading || state.confirming.loading || Boolean(view.value?.busy));
let unlisten: (() => void) | null = null;

onMounted(async () => {
  unlisten = props.takeover?.listen((event) => props.store.onEvent(event)) ?? null;
  await props.store.load();
  if (view.value?.available && !view.value.session) await props.store.open(0);
});

onBeforeUnmount(() => {
  unlisten?.();
  if (view.value?.session && !view.value.calibration?.dirty) void props.store.close();
});
</script>

<template>
  <main class="maintenance" data-view="maintenance">
    <ErrorNotice
      :error="state.view.error"
      :keeping="view ? '仍显示上次读取的维护状态' : null"
      :busy="state.view.loading"
      @retry="state.view.retry?.()"
    />
    <p v-if="view && !view.available" class="banner" data-role="maintenance-unavailable">{{ view.reason }}</p>
    <p v-else-if="view && !view.session" class="banner" data-role="maintenance-closed">
      设备维护页未打开。
      <button type="button" data-role="maintenance-open" :disabled="busy" @click="props.store.open(0)">打开设备维护</button>
    </p>
    <template v-if="view && view.available && view.session && view.header">
      <header class="panel head">
        <label class="device">
          <span>维护设备</span>
          <select
            name="maintenance-device"
            :value="view.target"
            :disabled="view.target_locked || busy"
            @change="props.store.target(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="device in view.devices" :key="device.key" :value="device.key">{{ device.label }}</option>
          </select>
        </label>
        <span class="numeric">{{ view.header.address }}</span>
        <span>{{ view.header.communication }}</span>
        <span class="state" :class="view.header.state_level" data-role="maintenance-state">{{ view.header.state }}</span>
      </header>
      <div v-if="view.halt" class="halt" role="alert" data-role="maintenance-halt">
        {{ view.halt.message }}（锁停：只能在“实时概览”停止采集，重新上电后再开始；本页不提供清除）
      </div>
      <nav class="tabs" aria-label="维护页签">
        <button
          v-for="(label, index) in TABS"
          :key="label"
          type="button"
          class="tab"
          :class="{ active: view.tab === index }"
          :aria-current="view.tab === index ? 'page' : undefined"
          :data-tab="index"
          @click="props.store.tab(index)"
        >
          {{ label }}
        </button>
      </nav>
      <section class="panel body">
        <MaintenanceDiagnostics
          v-if="view.tab === 0 && view.diagnostics"
          :diagnostics="view.diagnostics"
          :non-zero="state.nonZero"
          :busy="busy"
          @refresh="props.store.refresh()"
          @export="props.store.exportDiagnostics()"
          @non-zero="props.store.setNonZero($event)"
          @details="props.store.showDetails($event)"
        />
        <CalibrationCalibration
          v-else-if="view.tab === 1 && view.calibration"
          :calibration="view.calibration"
          :busy="busy"
          @read="props.store.readCalibration()"
          @write="props.store.writeCalibration()"
          @discard="props.store.discard()"
          @edit="(name, value) => props.store.edit({ field: name, value })"
          @drag="(node, x, y) => props.store.edit({ node, x, y })"
        />
        <MaintenanceComm
          v-else-if="view.tab === 2 && view.communication"
          :communication="view.communication"
          :form="state.form"
          :busy="busy"
          @enter="props.store.enter()"
          @read="props.store.commRead()"
          @write="props.store.commWrite()"
          @verify="props.store.commVerify()"
        />
      </section>
      <ErrorNotice :error="state.action.error" :busy="state.action.loading" @retry="state.action.retry?.()" />
      <ErrorNotice :error="state.confirming.error" :busy="state.confirming.loading" @retry="state.confirming.retry?.()" />
      <footer v-if="view.footer" class="foot">
        <p v-if="view.footer.resume_reason" class="reason" data-role="resume-reason">{{ view.footer.resume_reason }}</p>
        <div class="row">
          <span
            v-if="view.footer.result"
            class="result"
            :class="{ error: view.footer.result_error }"
            :title="view.footer.exported_file ?? undefined"
            data-role="maintenance-result"
            >{{ view.footer.result }}</span
          >
          <span class="spacer"></span>
          <button
            v-if="view.footer.resume_visible"
            type="button"
            class="primary"
            data-role="maintenance-leave"
            :disabled="!view.footer.resume_enabled || busy"
            :title="view.footer.resume_reason || undefined"
            @click="props.store.leave()"
          >
            退出通信维护并恢复采集
          </button>
          <button
            type="button"
            data-role="maintenance-close"
            :disabled="!view.footer.close_enabled || busy"
            @click="props.store.close()"
          >
            {{ view.footer.close_text }}
          </button>
        </div>
      </footer>
    </template>
    <ConfirmDialog
      v-if="state.pending"
      :title="state.pending.confirmation.title"
      :text="state.pending.confirmation.text"
      @yes="props.store.answer(true)"
      @no="props.store.answer(false)"
    />
    <ConfirmDialog
      v-else-if="view?.notice"
      :title="view.notice.title"
      :text="view.notice.text"
      :single="true"
      @yes="props.store.dismissNotice()"
      @no="props.store.dismissNotice()"
    />
    <div v-if="state.details" class="scrim" @click.self="props.store.showDetails(null)">
      <div class="dialog panel" role="dialog" aria-label="事件详情" data-role="event-details">
        <h2 class="panel-title">事件详情</h2>
        <pre class="numeric">{{ state.details }}</pre>
        <div class="buttons">
          <button type="button" @click="props.store.showDetails(null)">关闭</button>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.maintenance {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  overflow: auto;
}
.banner {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-surface-container);
  color: var(--color-on-surface-variant);
}
.head {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-2) var(--space-3);
}
.device {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.device select {
  min-width: 180px;
}
.state {
  flex: 1;
  min-width: 0;
}
.state.error,
.state.busy {
  color: var(--color-error);
}
.state.maintenance {
  color: var(--color-maintenance);
}
.halt {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-error-container);
  color: var(--color-on-error-container);
}
.tabs {
  display: flex;
  gap: var(--space-1);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
}
.tab {
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: transparent;
  min-width: 180px;
}
.tab.active {
  border-bottom-color: var(--color-primary);
  font-weight: var(--font-weight-medium);
}
.body {
  padding: var(--space-3) var(--space-4);
}
.foot .row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.reason {
  margin: 0 0 var(--space-1);
  color: var(--color-on-surface-variant);
}
.result.error {
  color: var(--color-error);
}
.spacer {
  flex: 1;
}
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
  width: min(700px, 90vw);
  max-height: 80vh;
  padding: var(--space-4);
}
.dialog pre {
  overflow: auto;
  margin: 0;
  font-size: var(--font-size-sm);
}
.buttons {
  display: flex;
  justify-content: flex-end;
}
</style>
