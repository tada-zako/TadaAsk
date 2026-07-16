<script setup lang="ts">
import { ArrowLeft } from "@lucide/vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/console/stores/auth";
import { Button } from "@/shared/components/ui/button";

const { t } = useI18n();
const router = useRouter();
const authStore = useAuthStore();

function returnToSafePage(): void {
  void router.replace({
    name: authStore.isAuthenticated ? "project-landing" : "login",
  });
}
</script>

<template>
  <main
    class="relative grid min-h-dvh place-items-center overflow-hidden bg-(--surface-base) px-6 py-12"
  >
    <section
      class="relative grid min-h-120 w-full max-w-4xl place-items-center rounded-(--console-radius-xl) border border-dashed border-white/[0.14] bg-(--surface-panel-soft) px-8 py-14 shadow-[0_24px_72px_rgba(0,0,0,0.3)]"
    >
      <div class="grid justify-items-center gap-14 text-center">
        <h1
          class="text-[clamp(5rem,15vw,7.5rem)] leading-none font-semibold tracking-[-0.045em] text-(--text-strong)"
        >
          404
        </h1>
        <div class="flex flex-col items-center gap-5">
          <span class="text-sm leading-6 text-(--text-muted)">
            {{ t("notFound.description") }}
          </span>
          <Button
            type="button"
            :aria-label="t('notFound.returnAria')"
            class="h-10 w-fit gap-2 rounded-(--console-radius-md) px-5"
            @click="returnToSafePage"
          >
            <ArrowLeft class="size-4" />
            {{
              authStore.isAuthenticated
                ? t("notFound.returnConsole")
                : t("notFound.returnLogin")
            }}
          </Button>
        </div>
      </div>
    </section>
  </main>
</template>
