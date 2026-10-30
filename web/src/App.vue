<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from "vue";
import ErrorNotice from "./components/ErrorNotice.vue";
import PageNav from "./components/PageNav.vue";
import StatusLine from "./components/StatusLine.vue";
import TakeoverDialogs from "./components/TakeoverDialogs.vue";
import TopBar from "./components/TopBar.vue";
import CalcPage from "./pages/CalcPage.vue";
import DliPage from "./pages/DliPage.vue";
import HistoryPage from "./pages/HistoryPage.vue";
import OverviewPage from "./pages/OverviewPage.vue";
import SettingsPage from "./pages/SettingsPage.vue";
import MaintenancePage from "./pages/MaintenancePage.vue";
import type { MaintenanceStore } from "./pages/maintenanceStore";
import type { CalcStore } from "./pages/calcStore";
import type { DliStore } from "./pages/dliStore";
import type { HistoryStore } from "./pages/historyStore";
import type { OverviewStore } from "./pages/overviewStore";
import { REFERENCE_CURVES, type ReferenceStore } from "./pages/referenceStore";
import type { SettingsStore } from "./pages/settingsStore";
import type { SupportStore } from "./pages/supportStore";
import { STREAM_DOWN, type TakeoverStore } from "./pages/takeoverStore";
import { runStatusView, withNotice } from "./lib/runStatus";
import { searchFor, type PageKey } from "./lib/view";

const props = defineProps<{
  store: HistoryStore;
  dli: DliStore;
  calc: CalcStore;
  settings: SettingsStore;
  overview: OverviewStore;
  /** tier and takeover (16_); absent in tests that only exercise tier-0 pages */
  takeover?: TakeoverStore;
  /** tier 2 device maintenance (17_); absent in tests that do not exercise it */
  maintenance?: MaintenanceStore;
  /** 导出诊断包 and 维护记录 on the settings page (D-226); absent in tests that do not exercise them */
  support?: SupportStore;
  /** API-08 reference curves and fill colours of the spectrum charts; absent in tests: the charts stay plain */
  reference?: ReferenceStore;
  initialView?: PageKey;
}>();
if (props.reference) provide(REFERENCE_CURVES, props.reference);
const tierState = computed(() => props.takeover?.state.tier.data ?? null);
/** issue #73: the run status in the top bar and its failure lines below it, on every page (UI-253, UI-252). */
const runView = computed(() => runStatusView(tierState.value, props.takeover?.state.status.data ?? null));
/** 16_ section 6: the event stream is down; the page keeps its data and says so until it reconnects. */
const streamDown = computed(() => props.takeover?.state.stream === "reconnecting");
/** D-225 item 1: the service's last unexpected error, in its own words, until 知道了. */
const fault = computed(() => props.takeover?.faultShown() ?? null);
const state = props.store.state;
const view = ref<PageKey>(props.initialView ?? "history");

const device = computed(() => state.devices.data?.items.find((item) => item.key === state.deviceKey) ?? null);
const asOf = computed(() => {
  if (view.value === "dli") return props.dli.state.day.data?.as_of ?? state.devices.data?.as_of ?? null;
  if (view.value === "calc") {
    const calc = props.calc.state;
    return calc.inputs.data?.as_of ?? calc.sources.data?.as_of ?? state.devices.data?.as_of ?? null;
  }
  if (view.value === "overview") {
    const overview = props.overview.state;
    const live = (tierState.value?.tier ?? 0) >= 1 ? overview.live.data?.as_of : null;
    return live ?? overview.overview.data?.as_of ?? state.devices.data?.as_of ?? null;
  }
  if (view.value === "settings") {
    const settings = props.settings.state;
    return settings.count.data?.as_of ?? settings.view.data?.as_of ?? state.devices.data?.as_of ?? null;
  }
  return state.page.data?.as_of ?? state.devices.data?.as_of ?? null;
});
const sourceText = computed(() =>
  device.value?.configured ? `数据：${device.value.name}（本机 2.0 采集的设备库）` : null,
);

function navigate(next: PageKey): void {
  view.value = next;
  try {
    window.history.replaceState(null, "", window.location.pathname + searchFor(window.location.search, next));
  } catch {
    // the address cannot be changed (e.g. inside a test): the page still switches
  }
}

/** The DLI page follows the top bar's device (UI-040: viewing only) and reloads whenever it is opened, and when the
 * viewed position got another database (the device list was read again, #82); the picked date is kept. */
watch(
  () => [view.value, state.deviceKey, device.value?.snapshot_id ?? null] as const,
  ([current, key]) => {
    if (current === "dli") void props.dli.showDevice(key);
  },
);

/** The calculation page keeps its own A/B sources (UI-159, UI-254): it does not follow the top bar's device; it
 * loads when opened and refreshes its lists when the device list changed meanwhile (UI-204, UI-267). */
watch(
  () => [view.value, state.devices.data] as const,
  ([current]) => {
    if (current === "calc") void props.calc.show();
  },
);

/** The settings page keeps its own export device (EXP-041, EXP-042); its status area follows the top bar's device
 * (UI-080). It reloads when opened, when the viewed device changes and when the device list changed. */
watch(
  () => [view.value, state.deviceKey, state.devices.data] as const,
  ([current, key]) => {
    if (current === "settings") void props.settings.show(key);
  },
);

/** The overview follows the top bar's device (UI-040: viewing only); it reloads when opened, when the viewed device
 * changes and when the device list changed (another database at the same position). */
watch(
  () => [view.value, state.deviceKey, state.devices.data] as const,
  ([current, key]) => {
    if (current === "overview") void props.overview.showDevice(key);
  },
);

/** The charts' reference curves load once; after a failure, opening a page tries again (R-1-5). */
watch(view, () => void props.reference?.load());

/** Issue #82: the devices are those of the alpha's own configuration, so the list is read again when the tier
 * changes (tier 0 lists none; also after a reconnection, which reads the tier again) and when a saved configuration
 * was applied. */
watch(
  () => tierState.value?.tier,
  (tier, before) => {
    if (before !== undefined && tier !== before) void props.store.reloadDevices();
  },
);
/** The event stream has no replay: a configuration applied while it was down is caught on the reconnection. */
let streamOpened = false;
watch(
  () => props.takeover?.state.stream,
  (stream) => {
    if (stream !== "open") return;
    if (streamOpened) void props.store.reloadDevices(); // every open after the first is a reconnection
    streamOpened = true;
  },
);
let unlisten: (() => void) | null = null;

onMounted(() => {
  void props.reference?.load();
  void props.store.init(); // sets the viewed device, which the watcher above passes on to the DLI page
  unlisten =
    props.takeover?.listen((event) => {
      if (event.name === "config_applied") void props.store.reloadDevices();
    }) ?? null;
  void props.takeover?.init();
});

onBeforeUnmount(() => {
  unlisten?.();
  props.takeover?.dispose();
});
</script>

<template>
  <div class="app">
    <TopBar
      :devices="state.devices.data?.items ?? []"
      :device-key="state.deviceKey"
      :version="state.health.data?.version ?? null"
      :run="runView"
      @select="props.store.selectDevice($event)"
    />
    <div v-if="runView.failures.length" class="run-failures" role="status" data-role="run-failures">
      <p
        v-for="(line, index) in runView.failures"
        :key="index"
        :title="withNotice(line, runView.failureNotices[index])"
        :data-event-id="runView.failureNotices[index]?.event_id"
      >
        {{ line }}
      </p>
    </div>
    <PageNav :view="view" :live="(tierState?.tier ?? 0) >= 1" :tier="tierState?.tier ?? 0" @navigate="navigate" />
    <div v-if="state.health.error || state.devices.error" class="global">
      <ErrorNotice
        :error="state.health.error ?? state.devices.error"
        :keeping="state.devices.data ? '设备清单为上次读取的结果' : null"
        :busy="state.health.loading || state.devices.loading"
        @retry="props.store.retryLoad()"
      />
    </div>
    <p v-if="streamDown" class="stream-down" role="status" data-role="stream-down">{{ STREAM_DOWN }}</p>
    <div v-if="fault" class="service-fault" role="alert" data-role="service-fault" :data-kind="fault.kind">
      <span class="text">{{ fault.message }}<span class="when">（{{ fault.occurred_at }}）</span></span>
      <button type="button" @click="props.takeover?.dismissFault()">知道了</button>
    </div>
    <OverviewPage
      v-if="view === 'overview'"
      class="page"
      :store="props.overview"
      :devices-failed="state.devices.error !== null"
      :takeover="props.takeover"
    />
    <HistoryPage v-else-if="view === 'history'" class="page" :store="props.store" />
    <CalcPage v-else-if="view === 'calc'" class="page" :store="props.calc" />
    <SettingsPage
      v-else-if="view === 'settings'"
      class="page"
      :store="props.settings"
      :takeover="props.takeover"
      :maintenance="props.maintenance"
      :support="props.support"
      :version="state.health.data?.version ?? null"
    />
    <MaintenancePage
      v-else-if="view === 'maintenance' && props.maintenance && (tierState?.tier ?? 0) >= 2"
      class="page"
      :store="props.maintenance"
      :takeover="props.takeover"
    />
    <DliPage v-else class="page" :store="props.dli" />
    <StatusLine
      :as-of="asOf"
      :source-text="sourceText"
      :tier="state.health.data?.tier ?? null"
      :tier-state="tierState"
    />
    <TakeoverDialogs v-if="props.takeover" :store="props.takeover" />
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 1100px;
}
.global {
  padding: var(--space-2) var(--space-3) 0;
}
.run-failures {
  padding: var(--space-1) var(--space-4);
  background: var(--color-surface);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
  color: var(--color-error);
  font-size: var(--font-size-sm);
  white-space: pre-wrap;
  user-select: text;
}
.run-failures p {
  margin: 0;
}
.stream-down {
  margin: var(--space-2) var(--space-3) 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-warning-container);
  color: var(--color-on-warning-container);
  font-size: var(--font-size-sm);
}
.service-fault {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin: var(--space-2) var(--space-3) 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-error-container);
  color: var(--color-on-error-container);
  font-size: var(--font-size-sm);
}
.service-fault .text {
  flex: 1;
  min-width: 0;
}
.service-fault .when {
  opacity: 0.85;
}
.page {
  flex: 1;
  min-height: 0;
}
</style>
