import { defineCustomElement } from "vue";

import TadaAskWidget from "./TadaAskWidget.ce.vue";

const TADAASK_WIDGET_TAG = "tada-ask-widget";

// Vite HMR 可能重复执行入口，注册前先检查，避免 CustomElementRegistry 抛错。
if (!customElements.get(TADAASK_WIDGET_TAG)) {
  customElements.define(TADAASK_WIDGET_TAG, defineCustomElement(TadaAskWidget));
}
