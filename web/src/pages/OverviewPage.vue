<script setup lang="ts">
/**
 * 实时概览, alpha read-only snapshot version (docs/design/ui-v2-pages.md 2.6; API-09; D-211).
 *
 * Shows the newest successful record with a spectrum of the viewed device's snapshot, as the V1.0.3 overview does:
 * the six summary cards (UI-012), "全部指标" (UI-009, disabled without a record, UI-013), the spectrum with the
 * status line outside the plot (UI-169: single line, elided, full text on hover, UI-056) and the in-chart card
 * (UI-060) behind "显示指标" (UI-061). A banner says the data is a snapshot, not live. There is no acquisition or
 * bus state and no start / stop control: those need tier 1 (later in stage two). While shown, the overview is
 * reloaded every REFRESH_MS like the V1.0.3 timer, so "距今 N 秒" moves on; failures keep the last answer and
 * offer a retry (R-1-5).
 *
 * Tier 1 (16_ section 6; D-214): the page shows the takeover instead - the real acquisition and bus state, 开始采集 /
 * 停止采集 (stopping asks first), the halt banner - and the newest record of the alpha's own database for the live
 * device chosen here, refreshed on every saved record (event stream) and on the same timer; "全部指标" opens the
 * shown live record's 54 values as V1.0.3 does (issue 106). Tier 0 is unchanged.
 */
import { computed, onBeforeUnmount, onMounted, watch } from "vue";
import ErrorNotice from "../components/ErrorNotice.vue";
import LivePanel, { type LiveDeviceItem } from "../components/LivePanel.vue";
import { withNotice } from "../lib/runStatus";
import OverviewChart from "../components/OverviewChart.vue";
import OverviewDetailsDialog from "../components/OverviewDetailsDialog.vue";
import OverviewKpis from "../components/OverviewKpis.vue";
import { NO_DEVICE_TEXT } from "../lib/view";
import type { OverviewStore } from "./overviewStore";
import type { TakeoverStore } from "./takeoverStore";

const REFRESH_MS = 3000;
/** Tier 0 reads no device data (issue #82): the page is empty and says why. */
const NOT_LIVE = "只读模式：不读取设备数据";
const LIVE = "实时数据";
const LIVE_PAUSED = "未在采集：显示设备库中的最后数据";
const HELD_OVER = "设置显示为只读模式，但采集仍在运行：请在下方停止采集（停止前不显示实时记录）";

const props = defineProps<{ store: OverviewStore; devicesFailed?: boolean; takeover?: TakeoverStore }>();
const state = props.store.state;
const live = computed(() => (props.takeover?.state.tier.data?.tier ?? 0) >= 1);
/** Tier reads 0 but the takeover is not released (D-215; PR #54 review M2): the takeover panel stays, with its
 * state, halt banner and 停止采集; no live record is read (the service answers it in tier 1 only). */
const heldOver = computed(() => props.takeover?.heldOver() ?? false);
const snapshot = computed(() =>
  !live.value && !heldOver.value && state.overview.data?.device.key === state.deviceKey ? state.overview.data : null,
);
const liveShown = computed(() =>
  live.value && state.live.data?.device.key === state.liveKey ? state.live.data : null,
);
const shown = computed(() => liveShown.value ?? snapshot.value);
const resource = computed(() => (live.value ? state.live : state.overview));
const banner = computed(() => {
  if (!live.value) return snapshot.value?.snapshot_text ?? NOT_LIVE;
  return props.takeover?.state.tier.data?.takeover === "running" ? LIVE : LIVE_PAUSED;
});

/** Live devices: the running coordinator's (with V1.0.3's status line), else the alpha configuration's. */
const liveDevices = computed<LiveDeviceItem[]>(() => {
  const takeover = props.takeover?.state;
  const running = (takeover?.status.data?.devices ?? []).filter((item) => item.position !== null);
  if (running.length > 0) {
    return running.map((item) => ({
      key: item.position ?? "",
      name: item.name,
      text: withNotice(item.status_text, item.notice),
      level: item.level,
    }));
  }
  return (takeover?.config.data?.devices ?? []).map((item, index) => ({
    key: `p${index + 1}`,
    name: item.name,
    text: item.name,
    level: "idle",
  }));
});

function chooseLive(): void {
  if (!live.value) return;
  const keys = liveDevices.value.map((item) => item.key);
  const key = state.liveKey !== null && keys.includes(state.liveKey) ? state.liveKey : (keys[0] ?? null);
  void props.store.showLive(key);
}

watch(
  live,
  (on) => {
    if (on) {
      void props.takeover?.loadConfig();
      chooseLive();
    }
  },
  { immediate: true },
);
watch(liveDevices, () => {
  if (live.value && (state.liveKey === null || !liveDevices.value.some((item) => item.key === state.liveKey))) {
    chooseLive();
  }
});
/** A record was saved (acquisition_saved): show it now, not at the next timer tick. */
watch(
  () => props.takeover?.state.savedRecords,
  () => {
    if (live.value && state.liveKey !== null) void props.store.refreshLive();
  },
);
const texts = computed(() => shown.value?.texts ?? null);
const keeping = computed(() =>
  shown.value?.display_record ? `仍显示上次读取的 #${shown.value.display_record.id}` : null,
);
/** The title of the record the dialog was opened for, not of a newer one shown since (V1.0.3's dialog is fixed). */
const detailsTitle = computed(() => state.detailsFor?.title ?? "");
let timer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  timer = setInterval(() => {
    if (live.value) {
      if (!state.live.loading && state.liveKey !== null) void props.store.refreshLive();
    } else if (!heldOver.value && !state.overview.loading && state.deviceKey !== null) void props.store.refresh();
  }, REFRESH_MS);
});

onBeforeUnmount(() => {
  if (timer !== null) clearInterval(timer);
});
</script>

<template>
  <main class="overview">
    <p v-if="heldOver" class="banner live-banner" role="alert" data-role="held-over">{{ HELD_OVER }}</p>
    <p v-else-if="!live" class="banner" data-role="snapshot" :title="snapshot?.poll_cycle_text">{{ banner }}</p>
    <p v-else class="banner live-banner" data-role="live-banner">{{ banner }}</p>
    <LivePanel
      v-if="(live || heldOver) && props.takeover"
      :store="props.takeover"
      :devices="liveDevices"
      :selected="state.liveKey"
      @select="live && props.store.showLive($event)"
    />
    <ErrorNotice
      :error="resource.error"
      :keeping="keeping"
      :busy="resource.loading"
      @retry="resource.retry?.()"
    />
    <p
      v-if="!live && !heldOver && state.deviceKey === null && !props.devicesFailed"
      class="muted empty"
      data-role="no-device"
    >
      {{ NO_DEVICE_TEXT }}
    </p>

    <template v-if="shown && texts">
      <section class="panel summary" data-role="summary">
        <header class="head">
          <h2 class="panel-title">{{ texts.summary_title }}</h2>
          <span class="muted context">{{ texts.summary_context }}</span>
          <button
            type="button"
            data-role="details-button"
            :disabled="!shown.details_enabled"
            @click="props.store.openDetails(live)"
          >
            {{ texts.details_button }}
          </button>
        </header>
        <OverviewKpis :kpis="shown.kpis" />
        <div v-if="shown.metrics_error" class="metrics-error" role="alert" data-role="metrics-error">
          <strong>{{ shown.metrics_error.message }}</strong>
          <span class="detail" :title="shown.metrics_error.detail">{{ shown.metrics_error.detail }}</span>
        </div>
      </section>

      <section class="panel spectrum">
        <header class="head">
          <h2 class="panel-title">{{ texts.spectrum_title }}</h2>
          <span
            class="status"
            :class="shown.status.level"
            data-role="status"
            :title="shown.status.text"
            >{{ shown.status.text }}</span
          >
          <label class="toggle">
            <input
              type="checkbox"
              name="overview-metrics"
              :checked="state.metricsVisible"
              @change="props.store.setMetricsVisible(($event.target as HTMLInputElement).checked)"
            />
            {{ texts.metrics_toggle }}
          </label>
        </header>
        <OverviewChart :chart="shown.chart" :texts="texts" :metrics-visible="state.metricsVisible" />
      </section>
    </template>

    <OverviewDetailsDialog
      v-if="state.detailsId !== null && texts"
      :title="detailsTitle"
      :columns="texts.details_columns"
      :close-text="texts.details_close"
      :detail="props.store.shownDetail()"
      :error="state.details.error"
      :busy="state.details.loading"
      @close="props.store.closeDetails()"
      @retry="state.details.retry?.()"
    />
  </main>
</template>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  min-height: 0;
  height: 100%;
  overflow-y: auto;
}
.banner {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-warning-container);
  color: var(--color-on-warning-container);
  font-size: var(--font-size-sm);
}
.empty {
  padding: var(--space-4);
}
.live-banner {
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
}
.summary {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) var(--space-3);
}
.head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}
.context {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-size-sm);
}
.metrics-error {
  display: flex;
  flex-direction: column;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-error-container);
  color: var(--color-on-error-container);
  font-size: var(--font-size-sm);
}
.metrics-error .detail {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.spectrum {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  flex: 1;
  min-height: 420px;
}
/* UI-056 / UI-169: one line outside the plot, elided at the end, the full text on hover */
.status {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-size-sm);
}
.status.ok {
  color: var(--color-success);
}
.status.warn {
  color: var(--color-warning);
}
.status.error {
  color: var(--color-error);
}
.toggle {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  white-space: nowrap;
  font-size: var(--font-size-sm);
}
.toggle input {
  height: auto;
}
</style>
