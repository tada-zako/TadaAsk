<script setup lang="ts">
// 引用来源列表，展示回答所引用的文档和外部链接
import { ExternalLink, FileText, Globe2 } from "@lucide/vue";
</script>

<template>
  <section class="sources-panel" aria-label="Sources">
    <header>
      <strong>Sources used in this answer</strong>
      <span>4 references</span>
    </header>

    <article class="source-row source-highlighted">
      <span class="source-index">1</span>
      <div class="source-main">
        <div class="source-title">
          <FileText aria-hidden="true" /><strong>widget-installation.md</strong>
        </div>
        <p class="source-meta">Product docs · Installation · Local file</p>
        <p class="source-excerpt">
          Add the widget script to the shared layout so every generated page
          loads the same assistant deployment.
        </p>
      </div>
    </article>

    <article class="source-row">
      <span class="source-index">2</span>
      <div class="source-main">
        <div class="source-title">
          <FileText aria-hidden="true" /><strong
            >frontend-ui-scope-constraints.md</strong
          >
        </div>
        <p class="source-meta">Frontend notes · Widget CSS boundary · Page 6</p>
        <p class="source-excerpt">
          Widget styling is exposed through controlled semantic tokens while
          message rendering and interaction remain internal.
        </p>
      </div>
    </article>

    <a
      class="source-row"
      href="https://example.com/docs/deploy"
      target="_blank"
      rel="noopener noreferrer"
    >
      <span class="source-index">3</span>
      <div class="source-main">
        <div class="source-title">
          <Globe2 aria-hidden="true" /><strong
            >Deploying on a static site</strong
          >
        </div>
        <p class="source-meta">docs.arcfield.dev · External page</p>
      </div>
      <ExternalLink class="source-open" aria-hidden="true" />
    </a>

    <a
      class="source-row"
      href="https://developer.mozilla.org/"
      target="_blank"
      rel="noopener noreferrer"
    >
      <span class="source-index">4</span>
      <div class="source-main">
        <div class="source-title">
          <Globe2 aria-hidden="true" /><strong>CSS custom properties</strong>
        </div>
        <p class="source-meta">developer.mozilla.org · External page</p>
      </div>
      <ExternalLink class="source-open" aria-hidden="true" />
    </a>
  </section>
</template>
