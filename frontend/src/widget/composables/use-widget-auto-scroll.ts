import { nextTick, onBeforeUnmount, ref, type Ref } from "vue";

const BOTTOM_THRESHOLD = 72;

/** 仅在访客接近底部时跟随流式输出 */
export function useWidgetAutoScroll(container: Ref<HTMLElement | null>) {
  const followsOutput = ref(true); // 是否跟随 message 输出滚动

  // 消息列表滚动处理：更新底部 pin 状态
  function handleScroll() {
    const element = container.value;
    if (!element) return;
    followsOutput.value =
      element.scrollHeight - element.scrollTop - element.clientHeight <=
      BOTTOM_THRESHOLD;
  }

  // 滚动到最底部
  async function scrollToLatest(force = false) {
    if (!force && !followsOutput.value) return;
    await nextTick();
    const element = container.value;
    if (element) element.scrollTop = element.scrollHeight;
  }

  function followLatest() {
    followsOutput.value = true;
    void scrollToLatest(true);
  }

  onBeforeUnmount(() => {
    followsOutput.value = false;
  });

  return { followsOutput, followLatest, handleScroll, scrollToLatest };
}
