import { ref } from "vue";
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

const startNewChat = vi.fn();
const sendMessage = vi.fn();

vi.mock("@/widget/composables/use-widget-chat", () => ({
  useWidgetChat: vi.fn(() => ({
    messages: ref([]),
    draft: ref(""),
    phase: ref("idle"),
    canSend: ref(true),
    errorMessage: ref(null),
    cancelGeneration: vi.fn(),
    dismissError: vi.fn(),
    startNewChat,
    sendMessage,
  })),
}));

import TadaAskWidget from "@/widget/TadaAskWidget.ce.vue";

describe("widget root integration", () => {
  it("初始化根组件，并将 launcher/panel 关键动作连接到 chat 状态", async () => {
    const wrapper = mount(TadaAskWidget, {
      props: {
        apiBaseUrl: "https://api.example.com",
        projectUid: "project-1",
        widgetUid: "widget-1",
        assistantTitle: "Help",
      },
      global: {
        stubs: {
          WidgetLauncher: {
            props: ["label"],
            template:
              '<button data-test="launcher" @click="$emit(\'open\')">{{ label }}</button>',
          },
          WidgetPanel: {
            props: ["title"],
            methods: {
              focusComposer() {},
            },
            template:
              '<section data-test="panel"><button @click="$emit(\'new-chat\')">new</button><button @click="$emit(\'send\')">send</button></section>',
          },
        },
      },
    });

    expect(wrapper.get('[data-test="launcher"]').text()).toContain("Help");
    await wrapper.get('[data-test="launcher"]').trigger("click");
    await wrapper.get('[data-test="panel"] button').trigger("click");
    await wrapper
      .get('[data-test="panel"] button:nth-of-type(2)')
      .trigger("click");

    expect(startNewChat).toHaveBeenCalledTimes(1);
    expect(sendMessage).toHaveBeenCalledTimes(1);
  });
});
