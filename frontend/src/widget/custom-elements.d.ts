// 为 Custom Element <tada-ask-widget> 注册 Vue 全局组件类型，消除 IDE 类型报错
import type TadaAskWidget from "./TadaAskWidget.ce.vue";

declare module "vue" {
  interface GlobalComponents {
    "tada-ask-widget": typeof TadaAskWidget;
  }
}

export {};
