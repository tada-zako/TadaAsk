<template>
  <!-- 控制台顶部导航栏 -->
  <header
    class="sticky top-0 z-30 grid min-h-[var(--console-header-height)] grid-cols-[1fr_auto_1fr] items-center border-b border-[var(--line-soft)] bg-background/80 px-7 backdrop-blur-lg max-[760px]:grid-cols-1 max-[760px]:gap-3 max-[760px]:px-4 max-[760px]:py-3"
  >
    <div></div>
    <!-- 面包屑导航 -->
    <div
      class="justify-self-center text-xs text-[var(--text-faint)] max-[760px]:justify-self-start"
    >
      Console /
      <strong class="font-semibold text-[var(--text-body)]">Project</strong>
    </div>
    <!-- 用户信息 -->
    <div
      class="flex items-center justify-end gap-2 text-xs text-[var(--text-muted)] max-[760px]:justify-start"
    >
      <span>admin</span>
      <div
        class="grid size-7 place-items-center rounded-full border border-[var(--line-soft)] bg-[var(--surface-panel)] text-xs font-semibold text-[var(--text-body)]"
      >
        A
      </div>
    </div>
  </header>
</template>
