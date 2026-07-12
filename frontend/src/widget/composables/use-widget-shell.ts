import { ref } from "vue";

/** 面板显隐与生成生命周期解耦；关闭只隐藏，不取消或卸载聊天状态。 */
export function useWidgetShell() {
  const isOpen = ref(false);

  return {
    isOpen,
    open: () => (isOpen.value = true),
    close: () => (isOpen.value = false),
    toggle: () => (isOpen.value = !isOpen.value),
  };
}
