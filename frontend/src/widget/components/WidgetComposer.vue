<script setup lang="ts">
import { ArrowUp, Square } from "@lucide/vue";

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    busy?: boolean;
    cancelling?: boolean;
    canSend?: boolean;
    compact?: boolean;
    placeholder?: string;
  }>(),
  {
    modelValue: "",
    busy: false,
    cancelling: false,
    canSend: false,
    compact: false,
    placeholder: "Ask anything…",
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: string];
  send: [];
  cancel: [];
}>();

function handleInput(event: Event) {
  emit("update:modelValue", (event.target as HTMLTextAreaElement).value);
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  if (props.canSend) emit("send");
}
</script>

<template>
  <section
    class="widget-composer"
    :class="{ 'composer-compact': compact }"
    aria-label="Message composer"
  >
    <textarea
      aria-label="Message"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="busy"
      @input="handleInput"
      @keydown="handleKeydown"
    ></textarea>
    <div class="composer-footer">
      <span v-if="busy">Generating a response…</span>
      <span v-else>Enter to send · Shift + Enter for a new line</span>
      <button
        v-if="busy"
        class="stop-button"
        type="button"
        :disabled="cancelling"
        :aria-label="cancelling ? 'Stopping generation' : 'Stop generating'"
        @click="$emit('cancel')"
      >
        <Square aria-hidden="true" />
      </button>
      <button
        v-else
        type="button"
        aria-label="Send message"
        :disabled="!canSend"
        @click="$emit('send')"
      >
        <ArrowUp aria-hidden="true" />
      </button>
    </div>
  </section>
</template>
