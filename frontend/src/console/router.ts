import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { resolveSafeAuthRedirect } from "./lib/auth-redirect";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      // 根路径跳转
      path: "/",
      redirect: "/project",
    },
    {
      // 登录页
      path: "/login",
      name: "login",
      component: () => import("./views/auth/LoginView.vue"),
      meta: { public: true },
    },
    {
      // 布局框架
      path: "/",
      component: () => import("./layouts/ConsoleShell.vue"),
      meta: { requiresAuth: true },
      children: [
        {
          path: "project",
          name: "project-landing",
          component: () => import("./views/project/ProjectView.vue"),
        },
        {
          path: "project/:projectUid",
          name: "project-overview",
          component: () => import("./views/project/ProjectView.vue"),
        },
        {
          // 预留页面
          path: "project/:projectUid/ask",
          name: "project-ask",
          component: () => import("./views/project/ProjectReservedView.vue"),
        },
        {
          // 项目设置页
          path: "project/:projectUid/settings",
          name: "project-settings",
          component: () => import("./views/project/ProjectSettingsView.vue"),
        },
        {
          path: "chat",
          name: "chat",
          component: () => import("./views/chat/ChatView.vue"),
          // fullBleed: 使用全屏无边距布局，由页面自行管理滚动
          meta: { fullBleed: true },
        },
        {
          path: "sources",
          name: "sources",
          component: () => import("./views/sources/SourcesView.vue"),
        },
        {
          path: "provider-model",
          name: "provider-model",
          component: () =>
            import("./views/provider-model/ProviderModelView.vue"),
        },
        {
          path: "sources/:sourceUid/items",
          name: "source-items",
          component: () => import("./views/sources/SourceItemsView.vue"),
        },
      ],
    },
  ],
});

/**
 * console 侧全局路由守卫
 */
router.beforeEach(async (to) => {
  const authStore = useAuthStore();
  await authStore.initializeAuth();

  if (to.meta.public && authStore.isAuthenticated) {
    return resolveSafeAuthRedirect(router, to.query.redirect);
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    // 保护页面要求未登录用户跳转到登录页
    return {
      path: "/login",
      query: { redirect: to.fullPath },
    };
  }
});

export default router;
