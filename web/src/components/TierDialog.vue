<script setup lang="ts">
/**
 * The two layers of turning on tier 1 (16_ 4.2), with the texts the service issued together with the confirmation:
 * first the notice (继续 / 取消), then the confirmation sentence with a checkbox; "开启档位 1" stays disabled until it is
 * checked. Esc or a click outside cancels; nothing is written until the service accepts the confirmation id.
 */
import { computed, nextTick, onMounted, ref } from "vue";
import type { TierConfirmation } from "../api/types";

const props = defineProps<{ step: "notice" | "confirm"; confirmation: TierConfirmation; acknowledged: boolean }>();
const emit = defineEmits<{ next: []; accept: []; cancel: []; acknowledge: [value: boolean] }>();
const cancel = ref<HTMLButtonElement | null>(null);
const title = computed(() =>
  props.confirmation.tier === 2 ? "开启维护模式" : "开启采集模式",
);

onMounted(async () => {
  await nextTick();
  cancel.value?.focus();
});
</script>

<template>
  <div class="scrim" @click.self="emit('cancel')" @keydown.esc="emit('cancel')">
    <div class="dialog panel" role="dialog" aria-modal="true" :aria-label="title" data-role="tier-dialog">
      <h2 class="panel-title">{{ title }}</h2>
      <template v-if="props.step === 'notice'">
        <p class="text" data-role="tier-notice">{{ props.confirmation.notice }}</p>
        <div class="buttons">
          <button type="button" class="primary" data-role="tier-next" @click="emit('next')">继续</button>
          <button ref="cancel" type="button" data-role="tier-cancel" @click="emit('cancel')">取消</button>
        </div>
      </template>
      <template v-else>
        <label class="ack">
          <input
            type="checkbox"
            name="tier-acknowledge"
            :checked="props.acknowledged"
            @change="emit('acknowledge', ($event.target as HTMLInputElement).checked)"
          />
          <span data-role="tier-confirmation">{{ props.confirmation.confirmation }}</span>
        </label>
        <p class="muted small">确认在 {{ props.confirmation.expires_at.replace("T", " ") }} 前有效，只能使用一次。</p>
        <div class="buttons">
          <button
            type="button"
            class="primary"
            data-role="tier-accept"
            :disabled="!props.acknowledged"
            @click="emit('accept')"
          >
            {{ props.confirmation.tier === 2 ? "开启维护模式" : "开启采集模式" }}
          </button>
          <button ref="cancel" type="button" data-role="tier-cancel" @click="emit('cancel')">取消</button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
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
  width: min(620px, 90vw);
  padding: var(--space-4);
}
.text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.ack {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
}
.ack input {
  height: auto;
  margin-top: 3px;
}
.small {
  margin: 0;
  font-size: var(--font-size-sm);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
