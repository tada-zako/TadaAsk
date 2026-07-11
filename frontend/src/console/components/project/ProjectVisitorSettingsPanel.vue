<script setup lang="ts">
import { ref } from "vue";
import { ChevronRight, CircleAlert, X } from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/components/ui/collapsible";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/shared/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { Switch } from "@/shared/components/ui/switch";
import { Textarea } from "@/shared/components/ui/textarea";

interface VisitorModelOption {
  initial: string;
  modelName: string;
  providerName: string;
}

// 仅用于本轮静态 UI 演示；后续业务接入时由 project settings 数据替换。
const selectedDefaultModel = ref<VisitorModelOption | null>({
  initial: "O",
  modelName: "gpt-4.1-mini",
  providerName: "OpenAI",
});

function selectDefaultModel(option: VisitorModelOption): void {
  selectedDefaultModel.value = option;
}

function clearDefaultModel(): void {
  selectedDefaultModel.value = null;
}
</script>

<template>
  <!-- 访客助手设置面板：模型与提示词、知识检索、高级参数 -->
  <section class="console-section">
    <header class="grid gap-1 px-0.5">
      <h2 class="text-xl leading-[1.35] font-bold text-(--text-strong)">
        Visitor assistant
      </h2>
      <p class="text-xs leading-5 text-(--text-faint)">
        Default response and retrieval behavior for visitor chat.
      </p>
    </header>

    <section
      class="console-panel overflow-hidden [&_[data-slot=label]]:text-[12.5px] [&_[data-slot=label]]:font-semibold [&_[data-slot=label]]:text-(--text-body)"
    >
      <!-- 模型与提示词配置 -->
      <section>
        <header class="px-5 pt-5">
          <h3 class="text-base leading-[1.4] font-bold text-(--text-strong)">
            Model and instructions
          </h3>
        </header>

        <div class="grid gap-5 p-5 pt-4">
          <div
            class="grid gap-2.5 rounded-(--console-radius-lg) border p-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]"
          >
            <div class="flex items-center justify-between gap-3">
              <Label class="text-[12.5px] font-semibold text-(--text-body)"
                >Default provider and model</Label
              >
              <span
                class="text-primary/80 text-[10px] font-semibold tracking-[0.08em] uppercase"
              >
                Visitor runtime
              </span>
            </div>

            <div class="group/model relative">
              <DropdownMenu>
                <DropdownMenuTrigger as-child>
                  <button
                    type="button"
                    :aria-label="
                      selectedDefaultModel
                        ? 'Change default visitor provider and model'
                        : 'Select default visitor provider and model'
                    "
                    class="hover:border-primary/40 focus-visible:border-primary/50 focus-visible:ring-primary/15 flex min-h-14 w-full items-center gap-3 rounded-(--console-radius-md) border bg-(--surface-raised) px-2.5 py-2 pr-12 text-left shadow-[0_8px_24px_rgba(0,0,0,0.16)] transition-colors hover:bg-(--surface-hover) focus-visible:ring-3 focus-visible:outline-none"
                    :class="
                      selectedDefaultModel
                        ? 'border-primary/25'
                        : 'border-primary/30 border-dashed'
                    "
                  >
                    <span
                      class="text-primary grid size-9 shrink-0 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-black/20 text-sm font-bold"
                    >
                      {{ selectedDefaultModel?.initial ?? "+" }}
                    </span>
                    <span class="grid min-w-0 flex-1 gap-0.5">
                      <strong
                        class="truncate text-sm font-semibold text-(--text-strong)"
                      >
                        {{
                          selectedDefaultModel?.modelName ??
                          "No default model configured"
                        }}
                      </strong>
                      <span class="truncate text-xs text-(--text-faint)">
                        {{
                          selectedDefaultModel
                            ? `${selectedDefaultModel.providerName} · enabled model`
                            : "Select a provider and model for visitor chat"
                        }}
                      </span>
                    </span>
                  </button>
                </DropdownMenuTrigger>

                <DropdownMenuContent
                  align="start"
                  class="max-h-82 w-[var(--reka-dropdown-menu-trigger-width)] min-w-72 [scrollbar-width:none] overflow-y-auto rounded-(--console-radius-lg) border-(--line) bg-(--surface-shell) p-1.5 [&::-webkit-scrollbar]:hidden"
                >
                  <DropdownMenuLabel
                    class="px-2 pt-1.5 pb-1 text-[11px] font-semibold text-(--text-faint) uppercase"
                  >
                    OpenAI
                  </DropdownMenuLabel>
                  <DropdownMenuItem
                    class="min-h-9 rounded-(--console-radius-md) px-2.5 text-[13px] text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
                    :class="
                      selectedDefaultModel?.modelName === 'gpt-4.1-mini'
                        ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                        : ''
                    "
                    @select="
                      selectDefaultModel({
                        initial: 'O',
                        modelName: 'gpt-4.1-mini',
                        providerName: 'OpenAI',
                      })
                    "
                  >
                    gpt-4.1-mini
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    class="min-h-9 rounded-(--console-radius-md) px-2.5 text-[13px] text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
                    :class="
                      selectedDefaultModel?.modelName === 'gpt-4.1'
                        ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                        : ''
                    "
                    @select="
                      selectDefaultModel({
                        initial: 'O',
                        modelName: 'gpt-4.1',
                        providerName: 'OpenAI',
                      })
                    "
                  >
                    gpt-4.1
                  </DropdownMenuItem>

                  <DropdownMenuLabel
                    class="px-2 pt-2.5 pb-1 text-[11px] font-semibold text-(--text-faint) uppercase"
                  >
                    Anthropic
                  </DropdownMenuLabel>
                  <DropdownMenuItem
                    class="min-h-9 rounded-(--console-radius-md) px-2.5 text-[13px] text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
                    :class="
                      selectedDefaultModel?.modelName === 'claude-sonnet-4'
                        ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                        : ''
                    "
                    @select="
                      selectDefaultModel({
                        initial: 'A',
                        modelName: 'claude-sonnet-4',
                        providerName: 'Anthropic',
                      })
                    "
                  >
                    claude-sonnet-4
                  </DropdownMenuItem>

                  <DropdownMenuLabel
                    class="px-2 pt-2.5 pb-1 text-[11px] font-semibold text-(--text-faint) uppercase"
                  >
                    9Router Vertex
                  </DropdownMenuLabel>
                  <DropdownMenuItem
                    class="min-h-9 rounded-(--console-radius-md) px-2.5 text-[13px] text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
                    :class="
                      selectedDefaultModel?.modelName === 'vx/gemini-3.5-flash'
                        ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                        : ''
                    "
                    @select="
                      selectDefaultModel({
                        initial: '9',
                        modelName: 'vx/gemini-3.5-flash',
                        providerName: '9Router Vertex',
                      })
                    "
                  >
                    vx/gemini-3.5-flash
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    class="min-h-9 rounded-(--console-radius-md) px-2.5 text-[13px] text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
                    :class="
                      selectedDefaultModel?.modelName ===
                      'vx/gemini-3.1-pro-preview'
                        ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                        : ''
                    "
                    @select="
                      selectDefaultModel({
                        initial: '9',
                        modelName: 'vx/gemini-3.1-pro-preview',
                        providerName: '9Router Vertex',
                      })
                    "
                  >
                    vx/gemini-3.1-pro-preview
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              <!-- Chevron 与清除按钮共用同一图标槽，hover 时直接切换。 -->
              <span
                class="pointer-events-none absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center"
                :class="selectedDefaultModel ? 'group-hover/model:hidden' : ''"
              >
                <ChevronRight class="size-4 rotate-90 text-(--text-faint)" />
              </span>

              <button
                v-if="selectedDefaultModel"
                type="button"
                aria-label="Clear default visitor provider and model"
                class="absolute top-1/2 right-2 hidden size-8 -translate-y-1/2 place-items-center rounded-(--console-radius-md) text-(--text-faint) group-hover/model:grid hover:bg-red-400/10 hover:text-red-300 focus-visible:bg-red-400/10 focus-visible:text-red-300 focus-visible:outline-none"
                @click.stop.prevent="clearDefaultModel"
              >
                <X class="size-4" />
              </button>
            </div>

            <p class="text-xs leading-5 text-(--text-faint)">
              Select an enabled model. Clear the selection to leave visitor chat
              unconfigured.
              <span class="text-primary font-semibold">Manage models</span>
            </p>
          </div>

          <div
            class="grid grid-cols-[minmax(0,1fr)_11.5rem] items-center gap-5 max-[620px]:grid-cols-1 max-[620px]:gap-2"
          >
            <div class="grid gap-1">
              <Label class="text-[13px] font-semibold">Thinking level</Label>
              <p class="text-xs leading-5 text-(--text-faint)">
                Choose whether the model uses additional reasoning before
                responding.
              </p>
            </div>
            <Select default-value="off">
              <SelectTrigger
                aria-label="Select thinking level"
                class="h-10 w-full border-(--line) bg-black/20 shadow-none"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="off">Off</SelectItem>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="high">High</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="grid gap-2">
            <Label
              for="visitor-system-instructions"
              class="text-[13px] font-semibold"
            >
              System instructions
            </Label>
            <Textarea
              id="visitor-system-instructions"
              default-value="Keep answers concise, ground claims in linked sources, and say when the documentation does not contain enough information."
              class="min-h-29 border-(--line) bg-black/20 text-[13px] leading-6 shadow-none"
            />
            <p class="text-xs leading-5 text-(--text-faint)">
              Added after TadaAsk's default safety and grounding instructions.
            </p>
          </div>
        </div>
      </section>

      <!-- Visitor RAG 配置 -->
      <section class="border-t border-(--line-soft)">
        <header class="px-5 pt-5">
          <h3 class="text-base leading-[1.4] font-bold text-(--text-strong)">
            Knowledge retrieval
          </h3>
        </header>

        <div class="grid gap-5 p-5 pt-4">
          <div class="flex items-center justify-between gap-6">
            <div class="grid gap-1">
              <Label class="text-[13px] font-semibold"
                >Use knowledge base</Label
              >
              <p class="text-xs leading-5 text-(--text-faint)">
                Retrieve context from linked public sources before generating an
                answer.
              </p>
            </div>
            <Switch
              :default-value="true"
              aria-label="Enable knowledge base for visitor answers"
            />
          </div>

          <fieldset class="grid gap-2.5">
            <legend class="text-[13px] font-semibold text-(--text-strong)">
              Search mode
            </legend>
            <p class="-mt-1 text-xs leading-5 text-(--text-faint)">
              Controls how much retrieval work is done before answering.
            </p>

            <RadioGroup default-value="adaptive" class="gap-2">
              <Label
                for="search-mode-fast"
                class="has-[[data-state=checked]]:border-primary/40 has-[[data-state=checked]]:bg-primary/[0.075] grid min-h-17 cursor-default grid-cols-[minmax(0,1fr)_1rem] items-center gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-black/10 px-3.5 py-3 transition-colors"
              >
                <RadioGroupItem
                  id="search-mode-fast"
                  value="fast"
                  class="peer col-start-2 row-start-1 border-(--line-strong) bg-transparent shadow-none"
                />
                <span class="col-start-1 row-start-1 grid gap-1">
                  <strong
                    class="mode-title peer-data-[state=checked]:text-primary text-[13px] font-semibold text-(--text-strong)"
                  >
                    Fast
                  </strong>
                  <span
                    class="text-xs leading-5 font-normal text-(--text-faint)"
                  >
                    Use the original query with direct full-text and vector
                    retrieval.
                  </span>
                </span>
              </Label>

              <Label
                for="search-mode-adaptive"
                class="has-[[data-state=checked]]:border-primary/40 has-[[data-state=checked]]:bg-primary/[0.075] grid min-h-17 cursor-default grid-cols-[minmax(0,1fr)_1rem] items-center gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-black/10 px-3.5 py-3 transition-colors"
              >
                <RadioGroupItem
                  id="search-mode-adaptive"
                  value="adaptive"
                  class="peer col-start-2 row-start-1 border-(--line-strong) bg-transparent shadow-none"
                />
                <span class="col-start-1 row-start-1 grid gap-1">
                  <strong
                    class="peer-data-[state=checked]:text-primary text-[13px] font-semibold text-(--text-strong)"
                  >
                    Adaptive
                  </strong>
                  <span
                    class="text-xs leading-5 font-normal text-(--text-faint)"
                  >
                    Expand the query only when the first candidate set needs
                    improvement.
                  </span>
                </span>
              </Label>

              <Label
                for="search-mode-full"
                class="has-[[data-state=checked]]:border-primary/40 has-[[data-state=checked]]:bg-primary/[0.075] grid min-h-17 cursor-default grid-cols-[minmax(0,1fr)_1rem] items-center gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-black/10 px-3.5 py-3 transition-colors"
              >
                <RadioGroupItem
                  id="search-mode-full"
                  value="full"
                  class="peer col-start-2 row-start-1 border-(--line-strong) bg-transparent shadow-none"
                />
                <span class="col-start-1 row-start-1 grid gap-1">
                  <strong
                    class="peer-data-[state=checked]:text-primary text-[13px] font-semibold text-(--text-strong)"
                  >
                    Full
                  </strong>
                  <span
                    class="text-xs leading-5 font-normal text-(--text-faint)"
                  >
                    Always expand the query before ranking retrieved candidates.
                  </span>
                </span>
              </Label>
            </RadioGroup>
          </fieldset>

          <div class="flex items-center justify-between gap-6">
            <div class="grid gap-1">
              <Label
                for="visitor-results-limit"
                class="text-[13px] font-semibold"
              >
                Results to include
              </Label>
              <p class="text-xs leading-5 text-(--text-faint)">
                Final source chunks supplied to the model.
              </p>
            </div>
            <Input
              id="visitor-results-limit"
              type="number"
              default-value="8"
              class="h-10 w-27 [appearance:textfield] border-(--line) bg-black/20 text-right text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
            />
          </div>

          <div class="flex items-center justify-between gap-6">
            <div class="grid gap-1">
              <Label class="text-[13px] font-semibold"
                >Rerank retrieved results</Label
              >
              <p class="text-xs leading-5 text-(--text-faint)">
                Improve final ordering before context is sent to the model.
              </p>
            </div>
            <Switch
              :default-value="true"
              aria-label="Enable reranking for retrieved results"
            />
          </div>

          <div class="flex items-center justify-between gap-6">
            <div class="grid gap-1">
              <Label class="text-[13px] font-semibold"
                >Rewrite follow-up questions</Label
              >
              <p class="text-xs leading-5 text-(--text-faint)">
                Convert contextual follow-ups into standalone search queries.
              </p>
            </div>
            <Switch
              :default-value="false"
              aria-label="Rewrite follow-up questions for retrieval"
            />
          </div>

          <div
            class="grid grid-cols-[1rem_minmax(0,1fr)] gap-2 rounded-(--console-radius-md) border border-yellow-300/20 bg-yellow-300/[0.065] px-3 py-2.5 text-xs leading-5 text-yellow-100/85"
          >
            <CircleAlert class="mt-0.5 size-3.5" />
            <span>
              Retrieval requires at least one linked public source with
              completed content.
            </span>
          </div>
        </div>
      </section>

      <!-- 高级设置与上方配置保持同一 h3 层级。 -->
      <Collapsible class="group border-t border-(--line-soft)">
        <CollapsibleTrigger
          type="button"
          aria-label="Toggle advanced visitor settings"
          class="grid w-full grid-cols-[minmax(0,1fr)_auto_1.25rem] items-center gap-3 px-5 py-4.5 text-left"
        >
          <strong
            class="text-base leading-[1.4] font-bold text-(--text-strong)"
          >
            Advanced settings
          </strong>
          <span class="text-[11px] text-(--text-faint)">Optional tuning</span>
          <ChevronRight
            class="size-4 text-(--text-faint) transition-transform duration-150 group-data-[state=open]:rotate-90"
          />
        </CollapsibleTrigger>

        <CollapsibleContent
          class="data-[state=open]:animate-in data-[state=open]:fade-in-0 px-5 pb-5"
        >
          <div class="grid gap-6">
            <section class="grid gap-3.5">
              <header>
                <h4
                  class="text-[11px] font-bold tracking-[0.09em] text-(--text-muted) uppercase"
                >
                  Response generation
                </h4>
              </header>

              <div class="grid grid-cols-2 gap-4 max-[620px]:grid-cols-1">
                <div class="grid gap-2">
                  <Label
                    for="visitor-max-tokens"
                    class="text-[13px] font-semibold"
                  >
                    Max output tokens
                  </Label>
                  <Input
                    id="visitor-max-tokens"
                    type="number"
                    default-value="1536"
                    class="h-10 [appearance:textfield] border-(--line) bg-black/20 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Maximum response length.
                  </p>
                </div>

                <div class="grid gap-2">
                  <Label
                    for="visitor-timeout"
                    class="text-[13px] font-semibold"
                  >
                    Request timeout
                  </Label>
                  <div class="relative">
                    <Input
                      id="visitor-timeout"
                      type="number"
                      default-value="45"
                      class="h-10 [appearance:textfield] border-(--line) bg-black/20 pr-16 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                    />
                    <span
                      class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-[11px] text-(--text-faint)"
                    >
                      seconds
                    </span>
                  </div>
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Maximum model request duration.
                  </p>
                </div>

                <div class="grid gap-2">
                  <Label
                    for="visitor-temperature"
                    class="text-[13px] font-semibold"
                  >
                    Temperature
                  </Label>
                  <Input
                    id="visitor-temperature"
                    type="number"
                    default-value="0.3"
                    step="0.1"
                    class="h-10 [appearance:textfield] border-(--line) bg-black/20 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Lower values keep answers focused.
                  </p>
                </div>

                <div class="grid gap-2">
                  <Label for="visitor-top-p" class="text-[13px] font-semibold">
                    Top P
                  </Label>
                  <Input
                    id="visitor-top-p"
                    type="number"
                    default-value="0.9"
                    step="0.1"
                    class="h-10 [appearance:textfield] border-(--line) bg-black/20 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Usually adjust this or temperature, not both.
                  </p>
                </div>
              </div>
            </section>

            <section class="grid gap-3.5 border-t border-(--line-soft) pt-5">
              <header>
                <h4
                  class="text-[11px] font-bold tracking-[0.09em] text-(--text-muted) uppercase"
                >
                  Retrieval candidates
                </h4>
              </header>

              <div class="grid grid-cols-2 gap-4 max-[620px]:grid-cols-1">
                <div class="grid gap-2">
                  <Label
                    for="visitor-fts-candidates"
                    class="text-[13px] font-semibold"
                  >
                    Full-text candidates
                  </Label>
                  <Input
                    id="visitor-fts-candidates"
                    type="number"
                    default-value="30"
                    class="h-10 [appearance:textfield] border-(--line) bg-black/20 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Candidates recalled from full-text search.
                  </p>
                </div>

                <div class="grid gap-2">
                  <Label
                    for="visitor-vector-candidates"
                    class="text-[13px] font-semibold"
                  >
                    Vector candidates
                  </Label>
                  <Input
                    id="visitor-vector-candidates"
                    type="number"
                    default-value="20"
                    class="h-10 [appearance:textfield] border-(--line) bg-black/20 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Candidates recalled from vector search.
                  </p>
                </div>

                <div class="grid gap-2">
                  <Label
                    for="visitor-rerank-candidates"
                    class="text-[13px] font-semibold"
                  >
                    Rerank candidates
                  </Label>
                  <Input
                    id="visitor-rerank-candidates"
                    type="number"
                    default-value="12"
                    class="h-10 [appearance:textfield] border-(--line) bg-black/20 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Candidates sent through reranking.
                  </p>
                </div>

                <div class="grid gap-2">
                  <Label
                    for="visitor-alternative-queries"
                    class="text-[13px] font-semibold"
                  >
                    Alternative queries
                  </Label>
                  <Input
                    id="visitor-alternative-queries"
                    type="number"
                    default-value="2"
                    class="h-10 [appearance:textfield] border-(--line) bg-black/20 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Maximum query variations, from 0 to 10.
                  </p>
                </div>

                <div class="grid gap-2">
                  <Label
                    for="visitor-max-keywords"
                    class="text-[13px] font-semibold"
                  >
                    Maximum keywords
                  </Label>
                  <Input
                    id="visitor-max-keywords"
                    type="number"
                    default-value="5"
                    class="h-10 [appearance:textfield] border-(--line) bg-black/20 text-[13px] shadow-none [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <p class="text-xs leading-5 text-(--text-faint)">
                    Keywords extracted for expansion, from 0 to 20.
                  </p>
                </div>
              </div>
            </section>
          </div>
        </CollapsibleContent>
      </Collapsible>

      <footer
        class="flex min-h-15 items-center justify-between gap-4 border-t border-(--line-soft) bg-black/10 px-4 py-3 pl-5 max-[560px]:flex-col max-[560px]:items-stretch"
      >
        <span class="flex items-center gap-2 text-xs text-(--text-faint)">
          <span class="size-1.5 rounded-full bg-(--text-disabled)"></span>
          Visitor settings are up to date
        </span>
        <Button
          type="button"
          aria-label="Save visitor settings"
          class="max-[560px]:w-full"
        >
          Save visitor settings
        </Button>
      </footer>
    </section>
  </section>
</template>
