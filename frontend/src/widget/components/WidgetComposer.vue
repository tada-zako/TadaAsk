<script setup lang="ts">
import { ArrowUp, Square } from "@lucide/vue";
import { ref } from "vue";

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

const textareaRef = ref<HTMLTextAreaElement | null>(null);

function handleInput(event: Event) {
  emit("update:modelValue", (event.target as HTMLTextAreaElement).value);
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  // 生成中不可发送，但 Enter 仍应保留为普通换行输入。
  if (!props.canSend) return;
  event.preventDefault();
  emit("send");
}

function focus(options: FocusOptions = { preventScroll: true }) {
  textareaRef.value?.focus(options);
}

// 将子组件中的 focus 方法暴露给父组件，
// 允许父组件调用 composer 内部的 textarea 的 focus 方法
defineExpose({ focus });
</script>

<template>
  <section
    class="widget-composer"
    :class="{ 'composer-compact': compact }"
    aria-label="Message composer"
  >
    <textarea
      ref="textareaRef"
      aria-label="Message"
      :aria-busy="busy || undefined"
      :value="modelValue"
      :placeholder="placeholder"
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
