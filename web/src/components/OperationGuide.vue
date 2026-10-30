<script setup lang="ts">
/**
 * 光谱计算应用说明 (UI-224..UI-232): the panel beside the result chart holds the four-paragraph summary with bold
 * inline headings (UI-226), scrolling inside itself when short of room instead of stretching the page (UI-227),
 * and a button opening the full guide. The dialog has the same title (UI-229), four chapter links (UI-231),
 * opens at 960×760 but never above 90 % of the window (UI-232), keeps the external reference links clickable in
 * a new window (UI-230, UI-250) and changes nothing on the page (UI-234, UI-289). All words are the service's
 * copy of the V1.0.3 texts; nothing is injected as HTML.
 */
import { computed, nextTick, ref } from "vue";
import type { OperationGuide } from "../api/types";

const props = defineProps<{ guide: OperationGuide }>();
const open = ref(false);
const body = ref<HTMLElement | null>(null);
const closeButton = ref<HTMLButtonElement | null>(null);

/** UI-232: the service's 960×760 and 90 % go in as custom properties; the CSS takes the smaller of the two */
const size = computed(() => ({
  "--dialog-width": `${props.guide.dialog.width_px}px`,
  "--dialog-height": `${props.guide.dialog.height_px}px`,
  "--dialog-max-width": `${props.guide.dialog.screen_fraction * 100}vw`,
  "--dialog-max-height": `${props.guide.dialog.screen_fraction * 100}vh`,
}));

async function show(): Promise<void> {
  open.value = true;
  await nextTick();
  closeButton.value?.focus();
}

function jump(anchor: string): void {
  body.value?.querySelector(`[data-anchor="${anchor}"]`)?.scrollIntoView({ block: "start" });
}
</script>

<template>
  <section class="panel guide" aria-label="应用说明">
    <h2 class="guide-title">{{ props.guide.title }}</h2>
    <div class="summary" data-testid="guide-summary">
      <p v-for="item in props.guide.summary" :key="item.head ?? item.text">
        <b v-if="item.head">{{ item.head }}</b>{{ item.text }}
      </p>
    </div>
    <div class="actions">
      <button type="button" @click="show">{{ props.guide.details_button }}</button>
    </div>
  </section>

  <div v-if="open" class="scrim" @click.self="open = false" @keydown.esc="open = false">
    <div class="dialog panel" role="dialog" aria-modal="true" :aria-label="props.guide.title" :style="size">
      <header class="dialog-head">
        <h2 class="panel-title">{{ props.guide.title }}</h2>
        <nav class="chapters" aria-label="章节">
          <a
            v-for="item in props.guide.navigation"
            :key="item.anchor"
            :href="`#${item.anchor}`"
            @click.prevent="jump(item.anchor)"
            >{{ item.text }}</a
          >
        </nav>
      </header>
      <div ref="body" class="dialog-body" data-testid="guide-details">
        <p>{{ props.guide.intro }}</p>
        <section v-for="section in props.guide.sections" :key="section.title" :data-anchor="section.anchor ?? undefined">
          <h3>{{ section.title }}</h3>
          <p v-for="item in section.paragraphs" :key="item.text">
            <b v-if="item.head">{{ item.head }}</b>{{ item.text }}
          </p>
          <p v-if="section.links.length" class="links">
            <a v-for="link in section.links" :key="link.url" :href="link.url" target="_blank" rel="noopener noreferrer">{{
              link.text
            }}</a>
          </p>
        </section>
      </div>
      <footer class="dialog-foot">
        <button ref="closeButton" type="button" @click="open = false">{{ props.guide.close_button }}</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.guide {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  padding: var(--space-2) var(--space-3);
  gap: var(--space-2);
}
.guide-title {
  margin: 0;
  text-align: center;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-medium);
}
/* UI-227: the summary scrolls inside the panel; the panel never grows the page */
.summary {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  font-size: var(--font-size-md);
}
.summary p {
  margin: 0 0 var(--space-2);
  line-height: 1.6;
}
.actions {
  display: flex;
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
  width: min(var(--dialog-width), var(--dialog-max-width));
  height: min(var(--dialog-height), var(--dialog-max-height));
}
.dialog-head {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-4) var(--space-2);
  border-bottom: var(--border-width) solid var(--color-outline-variant);
}
.chapters {
  display: flex;
  gap: var(--space-4);
}
.chapters a,
.links a {
  color: var(--color-primary);
}
.dialog-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-2) var(--space-4);
}
.dialog-body p {
  margin: var(--space-1) 0 var(--space-3);
  line-height: 1.6;
}
.dialog-body h3 {
  margin: var(--space-4) 0 var(--space-1);
  font-size: var(--font-size-lg);
}
.links {
  display: flex;
  flex-direction: column;
}
.dialog-foot {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-2) var(--space-4);
  border-top: var(--border-width) solid var(--color-outline-variant);
}
</style>
