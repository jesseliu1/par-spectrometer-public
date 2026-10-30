<script setup lang="ts">
/**
 * Settings page, tier 2 (17_ section 2): V1.0.3's "通信参数当前值" of one registered device (asked as V1.0.3 asks
 * when the settings page opens, G9: the service answers only a state text when V1.0.3 would not read) and the second
 * "退出维护并恢复采集" entry, with the same conditions as the maintenance page (D-110).
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { MaintenanceStore } from "../pages/maintenanceStore";
import type { TakeoverStore } from "../pages/takeoverStore";
import ConfirmDialog from "./ConfirmDialog.vue";
import ErrorNotice from "./ErrorNotice.vue";

const props = defineProps<{ store: MaintenanceStore; takeover: TakeoverStore }>();
const state = props.store.state;
const position = ref("p1");
const view = computed(() => state.view.data);
const devices = computed(() => (view.value?.devices ?? []).filter((device) => device.position !== null));
const current = computed(() => {
  const key = devices.value.find((device) => device.position === position.value)?.key;
  return (key && view.value?.settings?.[key]) || state.settings.data;
});
const LABELS = ["从站地址", "波特率", "校验位"];
let unlisten: (() => void) | null = null;

async function read(): Promise<void> {
  await props.store.settingsComm(position.value);
  await props.store.load();
}

function choose(event: Event): void {
  position.value = (event.target as HTMLSelectElement).value;
  void read();
}

onMounted(async () => {
  unlisten = props.takeover.listen((event) => props.store.onEvent(event));
  await props.store.load();
  if (view.value?.available) await read();
});

onBeforeUnmount(() => {
  unlisten?.();
  if (view.value?.available) void props.store.settingsLeft();
});
</script>

<template>
  <section class="panel section" data-role="settings-maintenance">
    <h2 class="panel-title">通信参数当前值（维护模式）</h2>
    <p v-if="view && !view.available" class="muted small">{{ view.reason }}</p>
    <template v-else>
      <div class="row">
        <select name="settings-comm-device" :value="position" @change="choose">
          <option v-for="device in devices" :key="device.key" :value="device.position ?? ''">{{ device.label }}</option>
        </select>
        <button type="button" data-role="settings-comm-read" :disabled="state.settings.loading" @click="read()">
          读取
        </button>
      </div>
      <p v-if="current" class="small" :class="{ error: current.error }" :title="current.tooltip || undefined" data-role="settings-comm-source">
        {{ current.source }}
      </p>
      <p v-if="current?.stale" class="small attention" data-role="settings-comm-stale">{{ current.stale_text }}</p>
      <dl v-if="current" class="values" data-role="settings-comm-values">
        <div v-for="(item, index) in current.values" :key="index">
          <dt class="muted">{{ LABELS[index] }}</dt>
          <dd class="numeric" :class="{ error: item.mismatch }" :title="item.tooltip">{{ item.text }}</dd>
        </div>
      </dl>
      <template v-if="view?.maintenance && view.footer">
        <p class="small attention" data-role="settings-resume-reason">
          {{ view.footer.resume_reason || "维护模式：采集、对时和自动重连已停止" }}
        </p>
        <button
          type="button"
          class="primary"
          data-role="settings-resume"
          :disabled="!view.footer.resume_enabled || state.action.loading"
          @click="props.store.leave()"
        >
          退出维护并恢复采集
        </button>
      </template>
      <ErrorNotice :error="state.settings.error" :busy="state.settings.loading" @retry="state.settings.retry?.()" />
      <ErrorNotice :error="state.action.error" :busy="state.action.loading" @retry="state.action.retry?.()" />
      <ErrorNotice :error="state.confirming.error" :busy="state.confirming.loading" @retry="state.confirming.retry?.()" />
    </template>
    <ConfirmDialog
      v-if="state.pending"
      :title="state.pending.confirmation.title"
      :text="state.pending.confirmation.text"
      @yes="props.store.answer(true)"
      @no="props.store.answer(false)"
    />
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
  gap: var(--space-3);
  align-items: center;
}
.small {
  margin: 0;
  font-size: var(--font-size-sm);
}
.values {
  display: flex;
  gap: var(--space-5);
  margin: 0;
}
.values dd {
  margin: 0;
}
.error,
.attention {
  color: var(--color-error);
}
</style>
