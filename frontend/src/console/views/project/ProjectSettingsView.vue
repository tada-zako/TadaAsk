<script setup lang="ts">
import ProjectDangerZonePanel from "@/console/components/project/ProjectDangerZonePanel.vue";
import ProjectGeneralSettingsPanel from "@/console/components/project/ProjectGeneralSettingsPanel.vue";
import ProjectVisitorSettingsPanel from "@/console/components/project/ProjectVisitorSettingsPanel.vue";
</script>

<template>
  <!-- 项目设置页：组合通用设置、访客助手、危险区三个面板 -->
  <section class="console-page max-w-[56.25rem]">
    <header class="console-page-head">
      <p class="console-kicker">Docs Assistant</p>
      <h1
        class="text-[clamp(1.95rem,2.7vw,2.25rem)] leading-[1.12] font-bold text-(--text-strong)"
      >
        Project settings
      </h1>
      <p class="console-page-subtitle max-w-[43.75rem]">
        Manage project identity and configure how the visitor assistant
        responds, retrieves knowledge, and uses its default model.
      </p>
    </header>

    <ProjectGeneralSettingsPanel />
    <ProjectVisitorSettingsPanel />
    <ProjectDangerZonePanel />
  </section>
</template>
