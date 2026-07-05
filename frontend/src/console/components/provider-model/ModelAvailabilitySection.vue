<script setup lang="ts">
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
</script>

<template>
  <section class="grid max-w-[56.25rem] gap-7">
    <!-- 官方 provider 模型列表 -->
    <section class="grid gap-3">
      <div class="grid gap-1 px-0.5">
        <h2 class="text-[17px] font-semibold text-(--text-strong)">
          Official provider models
        </h2>
        <p class="text-xs leading-5 text-(--text-faint)">
          Catalog models are read-only except for availability.
        </p>
      </div>

      <div class="grid gap-3.5">
        <!-- Google AI provider 卡片：header(图标/名称/状态) + 模型项列表 -->
        <article
          class="overflow-hidden rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel)"
        >
          <!-- provider header -->
          <div
            class="grid min-h-22 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-4 border-b border-(--line-soft) px-5 py-4"
          >
            <!-- provider 图标 -->
            <div
              class="grid size-10 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel)"
            >
              G
            </div>
            <div class="min-w-0">
              <h4 class="truncate text-lg font-bold text-(--text-strong)">
                Google AI
              </h4>
              <p class="mt-1 text-xs text-(--text-faint)">
                Official provider · API key saved
              </p>
            </div>
            <Badge
              variant="outline"
              class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
            >
              Official
            </Badge>
          </div>

          <!-- 该 provider 下的模型项列表 -->
          <div class="grid gap-2 p-3">
            <!-- gemini-2.5-flash：已启用 -->
            <article
              class="grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-2.5"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <h5 class="truncate text-sm font-medium text-(--text-strong)">
                    gemini-2.5-flash
                  </h5>
                </div>
                <p class="mt-1 truncate text-xs text-(--text-faint)">
                  Stream and structured output supported
                </p>
              </div>
              <Switch
                :default-value="true"
                aria-label="Enable gemini-2.5-flash model"
              />
            </article>

            <!-- gemini-2.5-pro：已禁用 -->
            <article
              class="grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-2.5"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <h5 class="truncate text-sm font-medium text-(--text-strong)">
                    gemini-2.5-pro
                  </h5>
                </div>
                <p class="mt-1 truncate text-xs text-(--text-faint)">
                  Available for higher quality responses
                </p>
              </div>
              <Switch
                :default-value="false"
                aria-label="Enable gemini-2.5-pro model"
              />
            </article>
          </div>
        </article>

        <!-- OpenAI provider 卡片 -->
        <article
          class="overflow-hidden rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel)"
        >
          <div
            class="grid min-h-22 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-4 border-b border-(--line-soft) px-5 py-4"
          >
            <div
              class="grid size-10 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel)"
            >
              O
            </div>
            <div class="min-w-0">
              <h4 class="truncate text-lg font-bold text-(--text-strong)">
                OpenAI
              </h4>
              <p class="mt-1 text-xs text-(--text-faint)">
                Official provider · API key saved
              </p>
            </div>
            <Badge
              variant="outline"
              class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
            >
              Official
            </Badge>
          </div>

          <div class="grid gap-2 p-3">
            <!-- gpt-4.1-mini：已启用 -->
            <article
              class="grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-2.5"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <h5 class="truncate text-sm font-medium text-(--text-strong)">
                    gpt-4.1-mini
                  </h5>
                </div>
                <p class="mt-1 truncate text-xs text-(--text-faint)">
                  Enabled for everyday project RAG testing
                </p>
              </div>
              <Switch
                :default-value="true"
                aria-label="Enable gpt-4.1-mini model"
              />
            </article>
            <!-- gpt-4.1：已禁用 -->
            <article
              class="grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-2.5"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <h5 class="truncate text-sm font-medium text-(--text-strong)">
                    gpt-4.1
                  </h5>
                </div>
                <p class="mt-1 truncate text-xs text-(--text-faint)">
                  Keep disabled until needed by a project
                </p>
              </div>
              <Switch
                :default-value="false"
                aria-label="Enable gpt-4.1 model"
              />
            </article>
          </div>
        </article>
      </div>
    </section>

    <!-- 自定义 provider 模型：支持编辑参数、删除、新增模型 -->
    <section class="grid gap-3">
      <div class="grid gap-1 px-0.5">
        <h2 class="text-[17px] font-semibold text-(--text-strong)">
          Custom provider models
        </h2>
        <p class="text-xs leading-5 text-(--text-faint)">
          Custom providers can add and edit model profiles.
        </p>
      </div>

      <div class="grid gap-3.5">
        <!-- Qoder gateway 自定义 provider 卡片 -->
        <article
          class="overflow-hidden rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel)"
        >
          <div
            class="grid min-h-22 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-4 border-b border-(--line-soft) px-5 py-4"
          >
            <div
              class="grid size-10 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel)"
            >
              *
            </div>
            <div class="min-w-0">
              <h4 class="truncate text-lg font-bold text-(--text-strong)">
                Qoder gateway
              </h4>
              <p class="mt-1 text-xs text-(--text-faint)">
                Custom provider · OpenAI-compatible endpoint
              </p>
            </div>
            <Badge
              variant="outline"
              class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
            >
              Custom
            </Badge>
          </div>

          <!-- 自定义模型项列表 -->
          <div class="grid gap-2 p-3">
            <!-- qoder-coder：已启用，hover 时显示 Edit 按钮 -->
            <article
              class="group grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-2.5"
            >
              <div class="min-w-0">
                <div class="flex min-w-0 items-center gap-2">
                  <h5 class="truncate text-sm font-medium text-(--text-strong)">
                    qoder-coder
                  </h5>
                  <!-- 编辑自定义模型 Dialog -->
                  <Dialog>
                    <DialogTrigger as-child>
                      <Button
                        type="button"
                        aria-label="Edit qoder-coder model"
                        variant="ghost"
                        size="sm"
                        class="text-primary hover:bg-primary/10 hover:text-primary h-7 px-2 text-xs font-semibold opacity-0 transition group-focus-within:opacity-100 group-hover:opacity-100"
                      >
                        Edit
                      </Button>
                    </DialogTrigger>
                    <DialogContent
                      class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[38.75rem]"
                    >
                      <DialogHeader
                        class="border-b border-(--line-soft) px-5 py-4 text-left"
                      >
                        <DialogTitle>Edit custom model</DialogTitle>
                        <DialogDescription>
                          Update the model name, token limits, and availability.
                        </DialogDescription>
                      </DialogHeader>

                      <div class="grid gap-4 px-5 py-5">
                        <!-- 模型名称 -->
                        <div class="grid gap-2">
                          <Label for="edit-custom-model-name">Model</Label>
                          <Input
                            id="edit-custom-model-name"
                            default-value="qoder-coder"
                          />
                        </div>

                        <!-- Token 限制：context window + max output -->
                        <div
                          class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1"
                        >
                          <div class="grid gap-2">
                            <Label for="edit-custom-context">
                              Context window tokens
                            </Label>
                            <Input
                              id="edit-custom-context"
                              type="number"
                              default-value="131072"
                            />
                          </div>
                          <div class="grid gap-2">
                            <Label for="edit-custom-output">
                              Max output tokens
                            </Label>
                            <Input
                              id="edit-custom-output"
                              type="number"
                              default-value="8192"
                            />
                          </div>
                        </div>

                        <!-- 启用开关 -->
                        <div
                          class="flex items-center justify-between gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-3"
                        >
                          <div>
                            <p class="text-sm font-medium text-(--text-strong)">
                              Enabled
                            </p>
                            <p class="mt-1 text-xs text-(--text-faint)">
                              Make this model available in selection flows.
                            </p>
                          </div>
                          <Switch
                            :default-value="true"
                            aria-label="Enable qoder-coder model"
                          />
                        </div>

                        <!-- 删除模型危险操作区 -->
                        <div
                          class="rounded-(--console-radius-md) border border-red-400/20 bg-red-400/10 p-3"
                        >
                          <Button
                            type="button"
                            aria-label="Delete qoder-coder model"
                            variant="destructive"
                            size="sm"
                          >
                            Delete model
                          </Button>
                        </div>
                      </div>

                      <DialogFooter
                        class="border-t border-(--line-soft) px-5 py-4 sm:justify-between"
                      >
                        <DialogClose as-child>
                          <Button
                            type="button"
                            aria-label="Cancel custom model edit"
                            variant="outline"
                          >
                            Cancel
                          </Button>
                        </DialogClose>
                        <Button type="button" aria-label="Save custom model">
                          Save model
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
                <!-- 模型 token 信息 -->
                <p class="mt-1 truncate text-xs text-(--text-faint)">
                  131,072 context tokens / 8,192 output tokens
                </p>
              </div>
              <Switch
                :default-value="true"
                aria-label="Enable qoder-coder model from list"
              />
            </article>

            <!-- qoder-lite：已禁用，context 使用 provider 默认值 -->
            <article
              class="group grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-md) border border-white/[0.045] bg-black/35 px-3.5 py-2.5"
            >
              <div class="min-w-0">
                <div class="flex min-w-0 items-center gap-2">
                  <h5 class="truncate text-sm font-medium text-(--text-strong)">
                    qoder-lite
                  </h5>
                  <Button
                    type="button"
                    aria-label="Edit qoder-lite model"
                    variant="ghost"
                    size="sm"
                    class="text-primary hover:bg-primary/10 hover:text-primary h-7 px-2 text-xs font-semibold opacity-0 transition group-focus-within:opacity-100 group-hover:opacity-100"
                  >
                    Edit
                  </Button>
                </div>
                <p class="mt-1 truncate text-xs text-(--text-faint)">
                  Context uses provider defaults
                </p>
              </div>
              <Switch
                :default-value="false"
                aria-label="Enable qoder-lite model from list"
              />
            </article>

            <!-- 新增自定义模型 Dialog -->
            <Dialog>
              <DialogTrigger as-child>
                <button
                  type="button"
                  aria-label="Add custom model to Qoder gateway"
                  class="hover:text-primary flex min-h-13 w-full items-center justify-center rounded-(--console-radius-md) border border-(--line) bg-white/[0.018] px-3 py-2.5 text-[13px] font-semibold text-(--text-muted) transition hover:bg-(--surface-hover)"
                >
                  + Add model
                </button>
              </DialogTrigger>
              <DialogContent
                class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[38.75rem]"
              >
                <DialogHeader
                  class="border-b border-(--line-soft) px-5 py-4 text-left"
                >
                  <DialogTitle>Add custom model</DialogTitle>
                  <DialogDescription>
                    Set the model name, token limits, and initial availability.
                  </DialogDescription>
                </DialogHeader>

                <div class="grid gap-4 px-5 py-5">
                  <!-- 模型名称 -->
                  <div class="grid gap-2">
                    <Label for="add-custom-model-name">Model</Label>
                    <Input
                      id="add-custom-model-name"
                      placeholder="qoder-reasoning"
                    />
                  </div>

                  <!-- Token 限制 -->
                  <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
                    <div class="grid gap-2">
                      <Label for="add-custom-context">
                        Context window tokens
                      </Label>
                      <Input
                        id="add-custom-context"
                        type="number"
                        default-value="131072"
                      />
                    </div>
                    <div class="grid gap-2">
                      <Label for="add-custom-output">Max output tokens</Label>
                      <Input
                        id="add-custom-output"
                        type="number"
                        default-value="8192"
                      />
                    </div>
                  </div>

                  <!-- 启用开关 -->
                  <div
                    class="flex items-center justify-between gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-3"
                  >
                    <div>
                      <p class="text-sm font-medium text-(--text-strong)">
                        Enabled
                      </p>
                      <p class="mt-1 text-xs text-(--text-faint)">
                        Make this model available after creation.
                      </p>
                    </div>
                    <Switch
                      :default-value="true"
                      aria-label="Enable new custom model"
                    />
                  </div>
                </div>

                <DialogFooter
                  class="border-t border-(--line-soft) px-5 py-4 sm:justify-end"
                >
                  <DialogClose as-child>
                    <Button
                      type="button"
                      aria-label="Cancel custom model creation"
                      variant="outline"
                    >
                      Cancel
                    </Button>
                  </DialogClose>
                  <Button type="button" aria-label="Create custom model">
                    Create model
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>
