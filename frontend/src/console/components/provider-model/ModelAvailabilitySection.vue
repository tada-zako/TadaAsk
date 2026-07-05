<script setup lang="ts">
import CustomModelDialog from "./CustomModelDialog.vue";
import type {
  CreateCustomModelInput,
  ModelProviderGroupViewModel,
  UpdateCustomModelInput,
} from "@/console/services/provider-model";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Switch } from "@/shared/components/ui/switch";

defineProps<{
  customModelGroups: ModelProviderGroupViewModel[];
  isLoading?: boolean;
  isMutating?: boolean;
  officialModelGroups: ModelProviderGroupViewModel[];
}>();

const emit = defineEmits<{
  (
    event: "createModel",
    providerUid: string,
    input: CreateCustomModelInput,
  ): void;
  (event: "deleteModel", providerUid: string, modelUid: string): void;
  (
    event: "toggleModel",
    providerUid: string,
    modelUid: string,
    isEnabled: boolean,
  ): void;
  (
    event: "updateModel",
    providerUid: string,
    modelUid: string,
    input: UpdateCustomModelInput,
  ): void;
}>();
</script>

<template>
  <section class="grid max-w-[56.25rem] gap-7">
    <!-- 官方 provider 模型：仅可切换启用/禁用 -->
    <section class="grid gap-3">
      <div class="grid gap-1 px-0.5">
        <h2 class="text-[17px] font-semibold text-(--text-strong)">
          Official provider models
        </h2>
        <p class="text-xs leading-5 text-(--text-faint)">
          Catalog models are read-only except for availability.
        </p>
      </div>

      <!-- 加载中 -->
      <div v-if="isLoading" class="px-0.5 py-4 text-sm text-(--text-muted)">
        Loading provider models...
      </div>
      <!-- 空状态：尚未连接官方 provider -->
      <div
        v-else-if="!officialModelGroups.length"
        class="rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel) px-4 py-5 text-sm text-(--text-muted)"
      >
        Connect an official provider before managing its catalog models.
      </div>
      <!-- provider 卡片列表：v-for 遍历 officialModelGroups -->
      <div v-else class="grid gap-3.5">
        <article
          v-for="group in officialModelGroups"
          :key="group.providerUid"
          class="overflow-hidden rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel)"
        >
          <div
            class="grid min-h-22 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-4 border-b border-(--line-soft) px-5 py-4"
          >
            <div
              class="grid size-10 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel)"
            >
              {{ group.initial }}
            </div>
            <div class="min-w-0">
              <h4 class="truncate text-lg font-bold text-(--text-strong)">
                {{ group.providerDisplayName }}
              </h4>
              <p class="mt-1 text-xs text-(--text-faint)">
                {{ group.description }}
              </p>
            </div>
            <Badge
              variant="outline"
              class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
            >
              {{ group.badgeLabel }}
            </Badge>
          </div>

          <!-- 模型项列表：v-for 遍历 group.models，Switch 切换启用 -->
          <div class="grid gap-2 p-3">
            <article
              v-for="model in group.models"
              :key="model.uid"
              class="grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-2.5"
            >
              <div class="min-w-0">
                <h5 class="truncate text-sm font-medium text-(--text-strong)">
                  {{ model.model }}
                </h5>
                <p class="mt-1 truncate text-xs text-(--text-faint)">
                  {{ model.description }}
                </p>
              </div>
              <Switch
                :model-value="model.isEnabled"
                :aria-label="`Enable ${model.model} model`"
                :disabled="isMutating"
                @update:model-value="
                  emit(
                    'toggleModel',
                    group.providerUid,
                    model.uid,
                    Boolean($event),
                  )
                "
              />
            </article>
            <!-- 该 provider 下无模型时的空状态 -->
            <div
              v-if="!group.models.length"
              class="rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-4 text-sm text-(--text-muted)"
            >
              No catalog models found for this provider.
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- 自定义 provider 模型：支持新建/编辑/删除/切换 -->
    <section class="grid gap-3">
      <div class="grid gap-1 px-0.5">
        <h2 class="text-[17px] font-semibold text-(--text-strong)">
          Custom provider models
        </h2>
        <p class="text-xs leading-5 text-(--text-faint)">
          Custom providers can add and edit model profiles.
        </p>
      </div>

      <!-- 加载中 -->
      <div v-if="isLoading" class="px-0.5 py-4 text-sm text-(--text-muted)">
        Loading custom provider models...
      </div>
      <!-- 空状态：尚未创建自定义 provider -->
      <div
        v-else-if="!customModelGroups.length"
        class="rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel) px-4 py-5 text-sm text-(--text-muted)"
      >
        Create a custom provider before adding custom model profiles.
      </div>
      <div v-else class="grid gap-3.5">
        <article
          v-for="group in customModelGroups"
          :key="group.providerUid"
          class="overflow-hidden rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel)"
        >
          <div
            class="grid min-h-22 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-4 border-b border-(--line-soft) px-5 py-4"
          >
            <div
              class="grid size-10 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel)"
            >
              {{ group.initial }}
            </div>
            <div class="min-w-0">
              <h4 class="truncate text-lg font-bold text-(--text-strong)">
                {{ group.providerDisplayName }}
              </h4>
              <p class="mt-1 text-xs text-(--text-faint)">
                {{ group.description }}
              </p>
            </div>
            <Badge
              variant="outline"
              class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
            >
              {{ group.badgeLabel }}
            </Badge>
          </div>

          <!-- 自定义模型项：v-for 遍历，hover 显示 Edit 按钮，含 Switch 切换 -->
          <div class="grid gap-2 p-3">
            <article
              v-for="model in group.models"
              :key="model.uid"
              class="group grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-2.5"
            >
              <div class="min-w-0">
                <div class="flex min-w-0 items-center gap-2">
                  <h5 class="truncate text-sm font-medium text-(--text-strong)">
                    {{ model.model }}
                  </h5>
                  <!-- 编辑 Dialog：通过 slot 传入 trigger 按钮 -->
                  <CustomModelDialog
                    mode="edit"
                    :is-mutating="isMutating"
                    :model="model"
                    :provider-display-name="group.providerDisplayName"
                    :provider-uid="group.providerUid"
                    @delete-model="
                      (providerUid, modelUid) =>
                        emit('deleteModel', providerUid, modelUid)
                    "
                    @update-model="
                      (providerUid, modelUid, input) =>
                        emit('updateModel', providerUid, modelUid, input)
                    "
                  >
                    <Button
                      type="button"
                      :aria-label="`Edit ${model.model} model`"
                      variant="ghost"
                      size="sm"
                      class="text-primary hover:bg-primary/10 hover:text-primary h-7 px-2 text-xs font-semibold opacity-0 transition group-focus-within:opacity-100 group-hover:opacity-100"
                    >
                      Edit
                    </Button>
                  </CustomModelDialog>
                </div>
                <p class="mt-1 truncate text-xs text-(--text-faint)">
                  {{ model.description }}
                </p>
              </div>
              <!-- 启用/禁用开关 -->
              <Switch
                :model-value="model.isEnabled"
                :aria-label="`Enable ${model.model} model from list`"
                :disabled="isMutating"
                @update:model-value="
                  emit(
                    'toggleModel',
                    group.providerUid,
                    model.uid,
                    Boolean($event),
                  )
                "
              />
            </article>

            <!-- 新增模型按钮：由 CustomModelDialog(mode="create") 包裹 -->
            <CustomModelDialog
              mode="create"
              :is-mutating="isMutating"
              :provider-display-name="group.providerDisplayName"
              :provider-uid="group.providerUid"
              @create-model="
                (providerUid, input) => emit('createModel', providerUid, input)
              "
            >
              <button
                type="button"
                :aria-label="`Add custom model to ${group.providerDisplayName}`"
                class="hover:text-primary flex min-h-13 w-full items-center justify-center rounded-(--console-radius-md) border border-(--line) bg-white/[0.018] px-3 py-2.5 text-[13px] font-semibold text-(--text-muted) transition hover:bg-(--surface-hover)"
              >
                + Add model
              </button>
            </CustomModelDialog>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>
