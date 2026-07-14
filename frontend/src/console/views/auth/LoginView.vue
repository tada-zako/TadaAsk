<script setup lang="ts">
// TODO: 当前登录页面只是极简实现，用于后续测试服务
// 后续需要重构完整业务逻辑以及 UI 设计
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowRight, LockKeyhole, ShieldCheck } from "@lucide/vue";

import { useAuthStore } from "@/console/stores/auth";
import { resolveSafeAuthRedirect } from "@/console/lib/auth-redirect";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

// 准备参数
const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const username = ref("");
const password = ref("");

// 计算是否可以提交表单
const canSubmit = computed(
  () =>
    username.value.trim().length > 0 &&
    password.value.length > 0 &&
    !authStore.isLoading,
);

async function handleLogin(): Promise<void> {
  if (!canSubmit.value) {
    return;
  }

  // 登录请求
  const loggedIn = await authStore.login(username.value.trim(), password.value);

  if (!loggedIn) {
    return;
  }

  // 支持从受保护页面跳转到 login 后，
  // 登录成功再回到原目标路径
  const redirectTo = resolveSafeAuthRedirect(router, route.query.redirect);

  await router.replace(redirectTo);
}
</script>

<template>
  <!-- 极简登录页面 -->
  <main
    class="dark bg-background text-foreground grid min-h-screen place-items-center overflow-hidden px-5 py-8 scheme-dark"
  >
    <!-- 渐变背景装饰 -->
    <div
      class="absolute inset-0 bg-[radial-gradient(circle_at_50%_-12%,rgba(36,211,196,0.18),transparent_24rem),linear-gradient(180deg,#09090a_0%,#050505_52rem)]"
    />

    <!-- 登录表单 -->
    <section
      class="border-border/80 bg-panel/88 relative grid w-full max-w-112 gap-7 rounded-(--radius-panel) border px-7 py-8 shadow-[0_24px_80px_rgba(0,0,0,0.5)] backdrop-blur max-[520px]:px-5"
    >
      <header class="grid gap-5">
        <div class="flex items-center justify-between gap-4">
          <div
            class="border-line-strong bg-surface-raised grid size-11 place-items-center rounded-(--radius-control) border text-cyan-200"
          >
            <ShieldCheck class="size-5" />
          </div>
          <span
            class="border-line bg-surface-muted text-text-subtle rounded-full border px-3 py-1 text-[0.68rem] font-semibold tracking-[0.16em] uppercase"
          >
            Admin
          </span>
        </div>
        <div class="grid gap-2">
          <h1 class="text-3xl font-semibold tracking-normal">
            TadaAsk Console
          </h1>
          <p class="text-text-muted max-w-sm text-sm leading-6">
            Sign in to manage projects, sources, widgets, and admin scoped RAG
            conversations.
          </p>
        </div>
      </header>

      <form class="grid gap-5" @submit.prevent="handleLogin">
        <div class="grid gap-2">
          <Label for="admin-username">Username</Label>
          <Input
            id="admin-username"
            v-model="username"
            autocomplete="username"
            class="h-11"
            placeholder="admin"
          />
        </div>

        <div class="grid gap-2">
          <Label for="admin-password">Password</Label>
          <Input
            id="admin-password"
            v-model="password"
            autocomplete="current-password"
            class="h-11"
            placeholder="Password"
            type="password"
          />
        </div>

        <p
          v-if="authStore.errorMessage"
          class="border-destructive/30 bg-destructive/10 text-destructive rounded-(--radius-control) border px-3 py-2 text-sm"
        >
          {{ authStore.errorMessage }}
        </p>

        <Button
          type="submit"
          aria-label="Sign in to admin console"
          class="h-11 justify-between"
          :disabled="!canSubmit"
        >
          <span class="inline-flex items-center gap-2">
            <LockKeyhole class="size-4" />
            Sign in
          </span>
          <ArrowRight class="size-4" />
        </Button>
      </form>
    </section>
  </main>
</template>
