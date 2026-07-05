<script setup lang="ts">
import { X } from "@lucide/vue";

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
  <section class="console-section">
    <div class="console-section-head">
      <div>
        <h2 class="console-section-title">Providers</h2>
        <p class="console-section-note">
          Add credentials for official providers or define a custom endpoint.
        </p>
      </div>
    </div>

    <div class="grid max-w-[56.25rem] gap-7">
      <!-- 已保存的 provider：管理已有凭证和端点配置 -->
      <section class="console-panel overflow-hidden">
        <div class="console-panel-header">
          <div>
            <h3 class="console-panel-title">Saved providers</h3>
            <p class="console-panel-note">Credentials and endpoint settings.</p>
          </div>
        </div>

        <div class="grid gap-0">
          <!-- Google AI：官方 provider，已配置 API Key -->
          <article
            class="grid min-h-22 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-4 py-3.5"
          >
            <!-- 图标 -->
            <div
              class="grid size-10 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-raised)"
            >
              G
            </div>
            <!-- 名称 + 凭证类型 + 端点 URL -->
            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <h4 class="truncate text-sm font-semibold text-(--text-strong)">
                  Google AI
                </h4>
                <Badge
                  variant="outline"
                  class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
                >
                  API Key
                </Badge>
              </div>
              <p class="mt-1 truncate text-xs text-(--text-faint)">
                https://generativelanguage.googleapis.com
              </p>
            </div>
            <!-- 管理官方 provider 的 Dialog：仅可修改 API key 和启用状态 -->
            <Dialog>
              <DialogTrigger as-child>
                <Button
                  type="button"
                  aria-label="Manage Google AI provider"
                  variant="outline"
                  size="sm"
                  class="border-(--line-soft) bg-(--surface-panel-soft)"
                >
                  Manage
                </Button>
              </DialogTrigger>
              <DialogContent
                class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[31rem]"
              >
                <DialogHeader
                  class="border-b border-(--line-soft) px-5 py-4 text-left"
                >
                  <DialogTitle>Manage Google AI</DialogTitle>
                  <DialogDescription>
                    Update the provider credential and availability.
                  </DialogDescription>
                </DialogHeader>

                <div class="grid gap-4 px-5 py-5">
                  <!-- API key 输入（password 类型） -->
                  <div class="grid gap-2">
                    <Label for="google-ai-key">API key</Label>
                    <Input
                      id="google-ai-key"
                      type="password"
                      placeholder="Leave blank to keep existing key"
                    />
                    <p class="text-xs leading-5 text-(--text-faint)">
                      Official providers keep their catalog name and base URL.
                    </p>
                  </div>

                  <!-- 启用开关 -->
                  <div
                    class="flex items-center justify-between gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-3"
                  >
                    <div>
                      <p class="text-sm font-medium text-(--text-strong)">
                        Enable provider
                      </p>
                      <p class="mt-1 text-xs text-(--text-faint)">
                        Available for model selection after saving.
                      </p>
                    </div>
                    <Switch
                      :default-value="true"
                      aria-label="Enable Google AI provider"
                    />
                  </div>
                </div>

                <DialogFooter
                  class="border-t border-(--line-soft) px-5 py-4 sm:justify-end"
                >
                  <DialogClose as-child>
                    <Button
                      type="button"
                      aria-label="Cancel Google AI provider management"
                      variant="outline"
                      class="w-20"
                    >
                      Cancel
                    </Button>
                  </DialogClose>
                  <Button
                    type="button"
                    aria-label="Save Google AI provider"
                    class="w-20"
                  >
                    Save
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </article>

          <!-- Qoder gateway：自定义 provider，可修改名称/URL/API key/删除 -->
          <article
            class="grid min-h-22 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3.5"
          >
            <div
              class="grid size-10 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-raised)"
            >
              *
            </div>
            <!-- 名称 + 类型 + 端点 URL -->
            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <h4 class="truncate text-sm font-semibold text-(--text-strong)">
                  Qoder gateway
                </h4>
                <Badge
                  variant="outline"
                  class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
                >
                  Custom
                </Badge>
              </div>
              <p class="mt-1 truncate text-xs text-(--text-faint)">
                https://llm.internal.example.com/v1
              </p>
            </div>
            <!-- 管理自定义 provider 的 Dialog：可修改名称/URL/API key、删除 provider -->
            <Dialog>
              <DialogTrigger as-child>
                <Button
                  type="button"
                  aria-label="Manage Qoder gateway provider"
                  variant="outline"
                  size="sm"
                  class="border-(--line-soft) bg-(--surface-panel-soft)"
                >
                  Manage
                </Button>
              </DialogTrigger>
              <DialogContent
                class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[34rem]"
              >
                <DialogHeader
                  class="border-b border-(--line-soft) px-5 py-4 text-left"
                >
                  <DialogTitle>Manage provider</DialogTitle>
                  <DialogDescription>
                    Update custom provider settings and availability.
                  </DialogDescription>
                </DialogHeader>

                <div class="grid gap-4 px-5 py-5">
                  <!-- Provider 名称 -->
                  <div class="grid gap-2">
                    <Label for="manage-provider-name">Provider name</Label>
                    <Input
                      id="manage-provider-name"
                      default-value="Qoder gateway"
                    />
                  </div>

                  <!-- Base URL -->
                  <div class="grid gap-2">
                    <Label for="manage-provider-base-url">Base URL</Label>
                    <Input
                      id="manage-provider-base-url"
                      default-value="https://llm.internal.example.com/v1"
                    />
                  </div>

                  <!-- API key（password 类型，留空保留现有 key） -->
                  <div class="grid gap-2">
                    <Label for="manage-provider-api-key">API key</Label>
                    <Input
                      id="manage-provider-api-key"
                      type="password"
                      placeholder="Leave blank to keep existing key"
                    />
                  </div>

                  <!-- 启用开关 -->
                  <div
                    class="flex items-center justify-between gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-3"
                  >
                    <div>
                      <p class="text-sm font-medium text-(--text-strong)">
                        Enable provider
                      </p>
                      <p class="mt-1 text-xs text-(--text-faint)">
                        Custom providers require a base URL and API key.
                      </p>
                    </div>
                    <Switch
                      :default-value="true"
                      aria-label="Enable Qoder gateway provider"
                    />
                  </div>

                  <!-- 删除 provider 危险操作区 -->
                  <div
                    class="rounded-(--console-radius-md) border border-red-400/20 bg-red-400/10 p-3"
                  >
                    <p class="text-sm font-medium text-red-100">
                      Delete provider
                    </p>
                    <p class="mt-1 text-xs leading-5 text-red-100/65">
                      Removes this custom provider and its custom model
                      profiles.
                    </p>
                    <Button
                      type="button"
                      aria-label="Delete Qoder gateway provider"
                      variant="destructive"
                      size="sm"
                      class="mt-3"
                    >
                      Delete provider
                    </Button>
                  </div>
                </div>

                <DialogFooter
                  class="border-t border-(--line-soft) px-5 py-4 sm:justify-end"
                >
                  <DialogClose as-child>
                    <Button
                      type="button"
                      aria-label="Cancel custom provider management"
                      variant="outline"
                      class="w-20"
                    >
                      Cancel
                    </Button>
                  </DialogClose>
                  <Button
                    type="button"
                    aria-label="Save custom provider"
                    class="w-20"
                  >
                    Save
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </article>
        </div>
      </section>

      <!-- 可连接的 provider：官方目录 provider + 自定义 endpoint -->
      <section class="console-panel overflow-hidden">
        <div class="console-panel-header">
          <div>
            <h3 class="console-panel-title">Available providers</h3>
            <p class="console-panel-note">
              Connect a catalog provider or custom endpoint.
            </p>
          </div>
        </div>

        <div class="grid gap-0">
          <!-- OpenAI：官方 provider，输入 API key 即可连接 -->
          <article
            class="grid min-h-18 grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-4 py-3"
          >
            <div
              class="grid size-9 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-raised)"
            >
              O
            </div>
            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <h4 class="truncate text-sm font-semibold text-(--text-strong)">
                  OpenAI
                </h4>
                <Badge
                  variant="outline"
                  class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
                >
                  Official
                </Badge>
              </div>
              <p class="mt-1 truncate text-xs text-(--text-faint)">
                Official catalog provider
              </p>
            </div>
            <!-- 连接 Dialog：仅需输入 API key -->
            <Dialog>
              <DialogTrigger as-child>
                <Button
                  type="button"
                  aria-label="Connect OpenAI provider"
                  variant="outline"
                  size="sm"
                  class="border-(--line-soft) bg-(--surface-panel-soft)"
                >
                  Connect
                </Button>
              </DialogTrigger>
              <DialogContent
                class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[28rem]"
              >
                <DialogHeader
                  class="border-b border-(--line-soft) px-5 py-4 text-left"
                >
                  <DialogTitle>Connect OpenAI</DialogTitle>
                  <DialogDescription>
                    Add an API key to enable this provider.
                  </DialogDescription>
                </DialogHeader>
                <div class="grid gap-2 px-5 py-5">
                  <Label for="openai-api-key">API key</Label>
                  <Input
                    id="openai-api-key"
                    type="password"
                    placeholder="sk-..."
                  />
                </div>
                <DialogFooter
                  class="border-t border-(--line-soft) px-5 py-4 sm:justify-end"
                >
                  <DialogClose as-child>
                    <Button
                      type="button"
                      aria-label="Cancel OpenAI connection"
                      variant="outline"
                      class="w-20"
                    >
                      Cancel
                    </Button>
                  </DialogClose>
                  <Button
                    type="button"
                    aria-label="Connect OpenAI provider"
                    class="w-20"
                  >
                    Connect
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </article>

          <!-- Anthropic：官方 provider -->
          <article
            class="grid min-h-18 grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-4 py-3"
          >
            <div
              class="grid size-9 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-raised)"
            >
              A
            </div>
            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <h4 class="truncate text-sm font-semibold text-(--text-strong)">
                  Anthropic
                </h4>
                <Badge
                  variant="outline"
                  class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
                >
                  Official
                </Badge>
              </div>
              <p class="mt-1 truncate text-xs text-(--text-faint)">
                Official catalog provider
              </p>
            </div>
            <Dialog>
              <DialogTrigger as-child>
                <Button
                  type="button"
                  aria-label="Connect Anthropic provider"
                  variant="outline"
                  size="sm"
                  class="border-(--line-soft) bg-(--surface-panel-soft)"
                >
                  Connect
                </Button>
              </DialogTrigger>
              <DialogContent
                class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[28rem]"
              >
                <DialogHeader
                  class="border-b border-(--line-soft) px-5 py-4 text-left"
                >
                  <DialogTitle>Connect Anthropic</DialogTitle>
                  <DialogDescription>
                    Add an API key to enable this provider.
                  </DialogDescription>
                </DialogHeader>
                <div class="grid gap-2 px-5 py-5">
                  <Label for="anthropic-api-key">API key</Label>
                  <Input
                    id="anthropic-api-key"
                    type="password"
                    placeholder="sk-ant-..."
                  />
                </div>
                <DialogFooter
                  class="border-t border-(--line-soft) px-5 py-4 sm:justify-end"
                >
                  <DialogClose as-child>
                    <Button
                      type="button"
                      aria-label="Cancel Anthropic connection"
                      variant="outline"
                      class="w-20"
                    >
                      Cancel
                    </Button>
                  </DialogClose>
                  <Button
                    type="button"
                    aria-label="Connect Anthropic provider"
                    class="w-20"
                  >
                    Connect
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </article>

          <!-- 自定义 provider：需填写名称、Base URL、API key 和初始模型名 -->
          <article
            class="grid min-h-18 grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3"
          >
            <div
              class="grid size-9 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-raised)"
            >
              +
            </div>
            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <h4 class="truncate text-sm font-semibold text-(--text-strong)">
                  Custom provider
                </h4>
                <Badge
                  variant="outline"
                  class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
                >
                  Custom
                </Badge>
              </div>
              <p class="mt-1 truncate text-xs text-(--text-faint)">
                OpenAI-compatible endpoint
              </p>
            </div>
            <Dialog>
              <DialogTrigger as-child>
                <Button
                  type="button"
                  aria-label="Create custom provider"
                  variant="outline"
                  size="sm"
                  class="border-(--line-soft) bg-(--surface-panel-soft)"
                >
                  Connect
                </Button>
              </DialogTrigger>
              <DialogContent
                class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[36rem]"
              >
                <DialogHeader
                  class="border-b border-(--line-soft) px-5 py-4 text-left"
                >
                  <DialogTitle>Create custom provider</DialogTitle>
                  <DialogDescription>
                    Define the endpoint, credential, and initial model names.
                  </DialogDescription>
                </DialogHeader>

                <div class="grid gap-4 px-5 py-5">
                  <!-- Provider 名称 -->
                  <div class="grid gap-2">
                    <Label for="custom-provider-name">Provider name</Label>
                    <Input
                      id="custom-provider-name"
                      placeholder="Qoder gateway"
                    />
                  </div>

                  <!-- Base URL -->
                  <div class="grid gap-2">
                    <Label for="custom-provider-base-url">Base URL</Label>
                    <Input
                      id="custom-provider-base-url"
                      placeholder="https://api.example.com/v1"
                    />
                  </div>

                  <!-- API key -->
                  <div class="grid gap-2">
                    <Label for="custom-provider-key">API key</Label>
                    <Input
                      id="custom-provider-key"
                      type="password"
                      placeholder="sk-..."
                    />
                  </div>

                  <!-- 初始模型列表：支持动态添加/删除行 -->
                  <div class="grid gap-2">
                    <Label>Models</Label>
                    <div class="grid gap-2">
                      <div
                        class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2"
                      >
                        <Input default-value="qoder-coder" />
                        <Button
                          type="button"
                          aria-label="Remove qoder-coder model row"
                          variant="ghost"
                          size="icon-sm"
                        >
                          <X class="size-4" />
                        </Button>
                      </div>
                      <div
                        class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2"
                      >
                        <Input default-value="qoder-lite" />
                        <Button
                          type="button"
                          aria-label="Remove qoder-lite model row"
                          variant="ghost"
                          size="icon-sm"
                        >
                          <X class="size-4" />
                        </Button>
                      </div>
                    </div>
                    <Button
                      type="button"
                      aria-label="Add another custom provider model"
                      variant="ghost"
                      size="sm"
                      class="text-primary hover:text-primary h-auto w-fit border-0 bg-transparent p-0 text-[13px] font-semibold hover:bg-transparent"
                    >
                      + Add model
                    </Button>
                  </div>
                </div>

                <DialogFooter
                  class="border-t border-(--line-soft) px-5 py-4 sm:justify-end"
                >
                  <DialogClose as-child>
                    <Button
                      type="button"
                      aria-label="Cancel custom provider creation"
                      variant="outline"
                      class="w-20"
                    >
                      Cancel
                    </Button>
                  </DialogClose>
                  <Button
                    type="button"
                    aria-label="Create custom provider"
                    class="w-20"
                  >
                    Create
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>
