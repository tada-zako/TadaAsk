<script setup lang="ts">
import { MessageSquareText } from "@lucide/vue";

withDefaults(
  defineProps<{
    label?: string;
  }>(),
  { label: "Open TadaAsk Assistant" },
);

defineEmits<{ open: [] }>();
</script>

<template>
  <button
    class="widget-launcher"
    type="button"
    :aria-label="label"
    @click="$emit('open')"
  >
    <MessageSquareText aria-hidden="true" />
  </button>
</template>
