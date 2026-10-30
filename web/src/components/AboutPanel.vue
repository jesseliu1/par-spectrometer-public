<script setup lang="ts">
/**
 * 关于与技术支持 (V1.0.3 settings page about_support_group and its 关于与技术支持 dialog): the logo, the product,
 * its version and the support contact, all selectable for copying.
 */
import {
  BRAND_NAME,
  LOGO_URL,
  buildLabel,
  PRODUCT_MODEL,
  PRODUCT_NAME,
  PRODUCT_PURPOSE,
  SUPPORT_CONTACT,
  SUPPORT_EMAIL,
} from "../lib/brand";

const props = defineProps<{ version: string | null }>();

const rows = (): [string, string][] => [
  ["软件名称", `${PRODUCT_NAME} ${PRODUCT_MODEL}`],
  ["软件版本", props.version ? `V2.0 试用版 · ${buildLabel(props.version)}` : "V2.0 试用版"],
  ["技术支持", SUPPORT_CONTACT],
  ["电子邮箱", SUPPORT_EMAIL],
];
</script>

<template>
  <section class="panel section about" data-role="about">
    <h2 class="panel-title">关于与技术支持</h2>
    <div class="intro">
      <img class="logo" :src="LOGO_URL" :alt="BRAND_NAME" />
      <div class="text">
        <p class="name">{{ PRODUCT_NAME }} <span class="model">{{ PRODUCT_MODEL }}</span></p>
        <p class="purpose muted">{{ PRODUCT_PURPOSE }}</p>
      </div>
    </div>
    <dl class="facts">
      <div v-for="[label, value] in rows()" :key="label" :class="{ wide: label === '办公地址' }">
        <dt class="muted">{{ label }}</dt>
        <dd :data-label="label">{{ value }}</dd>
      </div>
    </dl>
    <p class="muted small copyright">© 2026 jesse.sijia.liu。保留所有权利。</p>
  </section>
</template>

<style scoped>
.about {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
}
.intro {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-outline-variant);
}
.logo {
  display: block;
  width: 140px;
  height: auto;
  flex: none;
}
.text {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}
.name {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
}
.model {
  margin-left: var(--space-2);
  color: var(--color-on-surface-variant);
  font-size: var(--font-size-sm);
  font-weight: normal;
  letter-spacing: 0.06em;
}
.purpose {
  margin: 0;
  line-height: 1.6;
}
.facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2) var(--space-5);
  margin: 0;
}
.facts > div {
  display: flex;
  gap: var(--space-3);
  min-width: 0;
}
.facts > div.wide {
  grid-column: 1 / -1;
}
.facts dt {
  flex: none;
  width: 4.5em;
  margin: 0;
}
.facts dd {
  margin: 0;
  min-width: 0;
  user-select: text;
  overflow-wrap: anywhere;
}
.copyright {
  margin: 0;
}
</style>
