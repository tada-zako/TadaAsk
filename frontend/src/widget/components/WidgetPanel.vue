<script setup lang="ts">
// Widget 主面板，按 data-preview-state 切换四种静态预览状态
import {
  ArrowUp,
  ChevronDown,
  ChevronUp,
  MessageSquareText,
  Plus,
  X,
} from "@lucide/vue";

import WidgetComposer from "./WidgetComposer.vue";
import WidgetSourcesList from "./WidgetSourcesList.vue";
</script>

<template>
  <section class="widget-panel" aria-label="TadaAsk Assistant">
    <header class="panel-header">
      <div class="panel-brand">
        <span class="panel-logo brand-default">T</span>
        <span class="panel-logo brand-custom">A</span>
        <strong class="brand-default">TadaAsk Assistant</strong>
        <strong class="brand-custom">Atlas Research Assistant</strong>
      </div>
      <div class="panel-actions">
        <button type="button" aria-label="Start a new chat">
          <Plus aria-hidden="true" />
        </button>
        <button type="button" aria-label="Close assistant">
          <X aria-hidden="true" />
        </button>
      </div>
    </header>

    <main class="panel-content">
      <!-- 静态预览分支由 :host([data-preview-state]) 控制，后续替换为真实运行时状态 -->

      <!-- 状态 A：空面板 / 欢迎页 -->
      <section class="panel-state state-empty">
        <div class="empty-center">
          <div class="empty-welcome">
            <span><MessageSquareText aria-hidden="true" /></span>
            <h2>How can I help?</h2>
            <p>Ask a question about this site.</p>
          </div>
          <section class="empty-composer" aria-label="Message composer">
            <textarea
              aria-label="Message"
              placeholder="Ask anything…"
            ></textarea>
            <div>
              <span>Enter to send · Shift + Enter for a new line</span>
              <button type="button" aria-label="Send message">
                <ArrowUp aria-hidden="true" />
              </button>
            </div>
          </section>
        </div>
      </section>

      <!-- 状态 B：已完成对话 -->
      <section class="panel-state state-completed messages-scroll">
        <div class="messages-list">
          <article class="message message-user">
            <div>如何把 TadaAsk Widget 嵌入到静态文档站点？</div>
          </article>
          <article class="message message-assistant">
            <div class="assistant-copy">
              <p>
                把 Widget
                脚本放到站点的公共布局中，并为组件传入项目与部署标识。这样每个生成页面都会加载同一个助手实例。<button
                  class="citation-token"
                  type="button"
                  aria-label="Open citation 1"
                >
                  1
                </button>
              </p>
              <h3>推荐步骤</h3>
              <ul>
                <li>在全局 layout 的结束标签前加载 Widget 脚本。</li>
                <li>
                  添加
                  <code>&lt;tada-ask-widget&gt;</code>
                  标签并配置必要属性。<button
                    class="citation-token"
                    type="button"
                    aria-label="Open citation 2"
                  >
                    2
                  </button>
                </li>
                <li>
                  确认当前站点 Origin 已在对应 Widget 部署中启用。<button
                    class="citation-token"
                    type="button"
                    aria-label="Open citation 3"
                  >
                    3
                  </button>
                </li>
              </ul>
              <p>
                样式层面只覆盖公开的语义变量，消息、Markdown
                与引用交互会继续由组件内部控制。<button
                  class="citation-token"
                  type="button"
                  aria-label="Open citation 4"
                >
                  4
                </button>
              </p>
            </div>
            <button
              class="sources-toggle"
              type="button"
              aria-label="Open 4 sources"
            >
              <span>4</span>sources<ChevronDown aria-hidden="true" />
            </button>
          </article>
          <article class="message message-user">
            <div>页面刷新后还会保留这次对话吗？</div>
          </article>
          <article class="message message-assistant">
            <div class="assistant-copy">
              <p>
                不会。Widget
                只维护当前页面生命周期内的一轮可见会话；折叠再打开仍会保留，但刷新页面或点击新会话后，上一轮消息不会重新加载。
              </p>
            </div>
          </article>
        </div>
      </section>

      <!-- 状态 C：引用来源展开 -->
      <section class="panel-state state-sources messages-scroll">
        <div class="messages-list sources-messages">
          <article class="message message-user">
            <div>如何把 TadaAsk Widget 嵌入到静态文档站点？</div>
          </article>
          <article class="message message-assistant">
            <div class="assistant-copy">
              <p>
                将脚本放入公共 layout，并传入项目和 Widget
                标识。所有页面会共享相同的部署配置。<button
                  class="citation-token"
                  type="button"
                  aria-label="Open citation 1"
                >
                  1
                </button>
                样式只通过公开变量覆盖，内部的 Markdown
                和引用行为保持固定。<button
                  class="citation-token"
                  type="button"
                  aria-label="Open citation 2"
                >
                  2
                </button>
              </p>
            </div>
            <button
              class="sources-toggle"
              type="button"
              aria-label="Close 4 sources"
            >
              <span>4</span>sources<ChevronUp aria-hidden="true" />
            </button>
            <WidgetSourcesList />
          </article>
        </div>
      </section>

      <!-- 状态 D：流式回答 -->
      <section class="panel-state state-streaming messages-scroll">
        <div class="messages-list">
          <article class="message message-user">
            <div>RAG Snapshot 在流式回答中是怎样工作的？</div>
          </article>
          <article class="message message-assistant">
            <div class="stream-status"><i></i><span>Writing answer</span></div>
            <div class="assistant-copy">
              <p>
                <code>rag_ready</code> 会先于文本 delta
                到达，因此前端能在回答生成期间提前获得有效 citation ID。<button
                  class="citation-token"
                  type="button"
                  aria-label="Open citation 1"
                >
                  1
                </button>
              </p>
              <p>
                之后每个 delta 只追加正文内容；当完整的
                <code>[[citation:N]]</code> marker
                出现时，渲染器会把它转换为可点击的引用编号，同时隐藏尚未闭合的尾部片段。<span
                  class="typing-caret"
                ></span>
              </p>
            </div>
            <button
              class="sources-toggle"
              type="button"
              aria-label="Open 3 sources"
            >
              <span>3</span>sources ready<ChevronDown aria-hidden="true" />
            </button>
          </article>
        </div>
      </section>

      <WidgetComposer />
    </main>

    <footer class="panel-footer">
      <a href="https://github.com/" target="_blank" rel="noopener noreferrer"
        ><span>Powered by</span><i>T</i><strong>TadaAsk</strong></a
      >
    </footer>
  </section>
</template>
