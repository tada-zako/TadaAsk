<script setup lang="ts">
import { Trash2, TriangleAlert } from "@lucide/vue";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/components/ui/alert-dialog";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
</script>

<template>
  <!-- 项目危险区面板：删除项目等不可逆操作 -->
  <section class="console-section">
    <header class="grid gap-1 px-0.5">
      <h2 class="text-xl leading-[1.35] font-bold text-red-200">Danger zone</h2>
      <p class="text-xs leading-5 text-(--text-faint)">
        Irreversible project actions.
      </p>
    </header>

    <section
      class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-6 rounded-(--console-radius-lg) border border-red-400/25 bg-red-400/[0.035] px-5 py-4.5 max-[620px]:grid-cols-1"
    >
      <div class="grid gap-1">
        <h3 class="text-[13px] font-semibold text-(--text-strong)">
          Delete this project
        </h3>
        <p class="max-w-2xl text-xs leading-5 text-(--text-faint)">
          Permanently deletes project settings, widgets, project conversations,
          and source bindings. Shared sources remain available.
        </p>
      </div>

      <AlertDialog>
        <AlertDialogTrigger as-child>
          <Button
            type="button"
            aria-label="Delete project"
            variant="outline"
            class="border-red-400/30 bg-red-400/8 text-red-200 hover:bg-red-400/12 hover:text-red-100 max-[620px]:w-full"
          >
            <Trash2 class="size-3.5" />
            Delete project
          </Button>
        </AlertDialogTrigger>

        <AlertDialogContent
          class="gap-0 overflow-hidden border-(--line-strong) bg-[#0d0e10] p-0 shadow-[0_28px_100px_rgba(0,0,0,0.68)] sm:max-w-[31.25rem]"
        >
          <AlertDialogHeader
            class="border-b border-(--line-soft) px-5 py-4 text-left"
          >
            <AlertDialogTitle
              class="flex items-center gap-3 text-base font-semibold text-(--text-strong)"
            >
              <span
                class="grid size-8 place-items-center rounded-(--console-radius-md) border border-red-400/25 bg-red-400/8 text-red-300"
              >
                <Trash2 class="size-4" />
              </span>
              Delete Docs Assistant?
            </AlertDialogTitle>
            <AlertDialogDescription class="sr-only">
              Confirm permanent deletion of the Docs Assistant project.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div class="grid gap-4 p-5">
            <div
              class="grid gap-2 rounded-(--console-radius-md) border border-red-400/20 bg-red-400/8 p-3"
            >
              <strong class="flex items-center gap-2 text-[13px] text-red-100">
                <TriangleAlert class="size-4" />
                This action cannot be undone.
              </strong>
              <p class="text-xs leading-5 text-red-100/70">
                Project settings, deployed widgets, project conversations, and
                source bindings will be deleted. Shared sources will not be
                removed.
              </p>
            </div>

            <div class="grid gap-2">
              <Label
                for="delete-project-confirmation"
                class="text-[13px] font-normal text-(--text-body)"
              >
                Type
                <strong class="font-semibold text-(--text-strong)"
                  >"Docs Assistant"</strong
                >
                to confirm
              </Label>
              <Input
                id="delete-project-confirmation"
                default-value="Docs Assistant"
                class="h-10 border-(--line) bg-black/20 text-[13px] shadow-none"
              />
            </div>
          </div>

          <AlertDialogFooter
            class="border-t border-(--line-soft) bg-black/15 px-5 py-3.5"
          >
            <AlertDialogCancel
              type="button"
              aria-label="Cancel project deletion"
              class="border-(--line) bg-transparent"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              type="button"
              aria-label="Confirm project deletion"
              class="bg-red-500 text-white hover:bg-red-500/90"
            >
              <Trash2 class="size-3.5" />
              Delete project
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  </section>
</template>
