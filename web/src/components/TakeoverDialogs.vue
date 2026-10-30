<script setup lang="ts">
/** The takeover's confirmations, wherever they were asked from: the two layers of 0 → 1, and the one confirmation of
 * 1 → 0 and of 停止采集 (both stop a running takeover, which can take up to one transaction, about 40 s), and
 * 以空配置重新配置 (D-220). Every text is the service's (GET /tier, GET /acquisition-config). */
import { computed } from "vue";
import type { TakeoverStore } from "../pages/takeoverStore";
import ConfirmDialog from "./ConfirmDialog.vue";
import TierDialog from "./TierDialog.vue";

const props = defineProps<{ store: TakeoverStore }>();
const state = props.store.state;
const reconfigureText = computed(() => {
  const config = state.config.data;
  if (config === null) return "";
  const problem = config.problem;
  const reason = problem === null ? "" : `${problem.message}${problem.detail ? `\n${problem.detail}` : ""}\n\n`;
  return `${reason}${config.form.reconfigure_text}`;
});
</script>

<template>
  <TierDialog
    v-if="(state.dialog === 'notice' || state.dialog === 'confirm') && state.confirming.data"
    :step="state.dialog"
    :confirmation="state.confirming.data"
    :acknowledged="state.acknowledged"
    @next="props.store.continueTier()"
    @acknowledge="props.store.setAcknowledged($event)"
    @accept="props.store.acceptTier()"
    @cancel="props.store.cancelDialog()"
  />
  <ConfirmDialog
    v-else-if="state.dialog === 'down'"
    title="切回只读模式"
    :text="state.tier.data?.down_text ?? ''"
    @yes="props.store.confirmDown()"
    @no="props.store.cancelDialog()"
  />
  <ConfirmDialog
    v-else-if="state.dialog === 'down1'"
    title="关闭维护模式"
    :text="state.tier.data?.down_to_1_text ?? ''"
    @yes="props.store.confirmDown()"
    @no="props.store.cancelDialog()"
  />
  <ConfirmDialog
    v-else-if="state.dialog === 'stop'"
    title="停止采集"
    :text="state.tier.data?.stop_text ?? ''"
    @yes="props.store.confirmStop()"
    @no="props.store.cancelDialog()"
  />
  <ConfirmDialog
    v-else-if="state.dialog === 'reconfigure' && state.config.data"
    :title="state.config.data.form.reconfigure_title"
    :text="reconfigureText"
    @yes="props.store.confirmReconfigure()"
    @no="props.store.cancelDialog()"
  />
</template>
