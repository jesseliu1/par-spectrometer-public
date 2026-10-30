<script setup lang="ts">
/** Top bar: the company logo and the product name (as V1.0.3's 关于与技术支持), the trial notice (S-2, issue 119), the
 * viewed device (UI-255; switching only changes the view, UI-040) and, at the right, the run status on every page
 * (UI-253, issue #73). */
import type { Device } from "../api/types";
import { BRAND_NAME, buildLabel, LOGO_URL, PRODUCT_MODEL, PRODUCT_NAME } from "../lib/brand";
import type { RunView } from "../lib/runStatus";
import RunStatus from "./RunStatus.vue";

const props = defineProps<{ devices: Device[]; deviceKey: string | null; version: string | null; run: RunView }>();
const emit = defineEmits<{ select: [key: string] }>();

/** UI-259: a disabled device reads 停用; a database the alpha may not read is a fault (16_ 3.2). */
const STATE_SUFFIX: Partial<Record<Device["display_state"], string>> = { disabled: "（停用）", fault: "（库不可用）" };

function hover(device: Device): string {
  if (!device.configured) return `位置 ${device.position}：未登记设备`;
  return `${device.name}${STATE_SUFFIX[device.display_state] ?? ""}\n${device.database_path ?? ""}`;
}
</script>

<template>
  <header class="bar">
    <div class="brand">
      <img class="logo" :src="LOGO_URL" :alt="BRAND_NAME" data-role="brand-logo" />
      <span class="divider" aria-hidden="true"></span>
      <span class="names">
        <span class="product" data-role="product-name">{{ PRODUCT_NAME }}</span>
        <span class="model">{{ PRODUCT_MODEL }}</span>
      </span>
      <span class="edition" data-role="product-version" :title="props.version ? `V2.0 试用版 · ${buildLabel(props.version)}` : undefined"
        >V2.0 试用版</span
      >
    </div>
    <nav class="devices" aria-label="查看设备">
      <span class="muted label">查看设备</span>
      <button
        v-for="device in props.devices"
        :key="device.key"
        type="button"
        class="device"
        :class="[device.display_state, { active: device.key === props.deviceKey }]"
        :disabled="!device.configured"
        :aria-pressed="device.key === props.deviceKey"
        :title="hover(device)"
        :data-key="device.key"
        @click="emit('select', device.key)"
      >
        <span class="position">{{ device.position }}</span>
        <span class="name">{{ device.configured ? device.name : "未配置" }}</span>
        <span v-if="STATE_SUFFIX[device.display_state]" class="state" data-role="device-state">{{
          STATE_SUFFIX[device.display_state]
        }}</span>
      </button>
    </nav>
    <RunStatus :view="props.run" />
  </header>
</template>

<style scoped>
.state {
  color: var(--color-on-surface-variant);
  font-size: var(--font-size-sm);
}
.bar {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  min-height: var(--nav-height);
  padding: 0 var(--space-4);
  background: var(--color-surface);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
}
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  white-space: nowrap;
}
.logo {
  display: block;
  height: 36px; /* the 405 × 196 logo, as wide as the two name lines are tall */
  width: auto;
}
.divider {
  align-self: stretch;
  width: 1px;
  margin: var(--space-1) 0;
  background: var(--color-outline-variant);
}
.names {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.product {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  letter-spacing: 0.02em;
}
.model {
  color: var(--color-on-surface-variant);
  font-size: var(--font-size-xs);
  letter-spacing: 0.08em;
}
/* below 1280 px the brand gives room to the devices and the run status: smaller logo, no model line */
@media (max-width: 1279px) {
  .logo {
    height: 28px;
  }
  .model,
  .divider {
    display: none;
  }
}
.edition {
  padding: 2px var(--space-2);
  border-radius: var(--radius-control);
  background: var(--color-primary-container);
  color: var(--color-on-primary-container);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
}
.devices {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  overflow-x: auto;
}
.label {
  font-size: var(--font-size-sm);
  white-space: nowrap;
}
.device {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  max-width: 220px;
}
.device .name {
  overflow: hidden;
  text-overflow: ellipsis;
}
.device .position {
  font-variant-numeric: var(--font-numeric);
  color: var(--color-on-surface-variant);
}
.device.active {
  background: var(--color-primary-container);
  border-color: var(--color-primary);
  color: var(--color-on-primary-container);
}
.device.unconfigured {
  color: var(--color-disabled);
}
</style>
