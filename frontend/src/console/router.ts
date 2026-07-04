import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";

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
          // 预留页面
          path: "project/:projectUid/settings",
          name: "project-settings",
          component: () => import("./views/project/ProjectReservedView.vue"),
        },
        {
          path: "chat",
          name: "chat",
          component: () => import("./views/chat/ChatView.vue"),
        },
        {
          path: "sources",
          name: "sources",
          component: () => import("./views/sources/SourcesView.vue"),
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
router.beforeEach((to) => {
  const authStore = useAuthStore();

  // 路由层只判断是否存在本地 token；token 过期由 client 401 处理。
  if (to.meta.public && authStore.isAuthenticated) {
    // 已登录用户默认跳转到项目页
    return "/project";
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
