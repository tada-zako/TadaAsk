<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { Ellipsis, Plus } from "@lucide/vue";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";

const { t } = useI18n();
</script>

<template>
  <!-- 全局数据源管理视图 -->
  <section class="grid gap-5">
    <!-- 页面头部 -->
    <header class="flex items-start justify-between gap-4">
      <div class="grid gap-2">
        <h1 class="text-4xl font-bold tracking-normal max-[760px]:text-3xl">
          {{ t("sources.title") }}
        </h1>
        <p class="text-muted-foreground max-w-3xl text-sm leading-6">
          {{ t("sources.description") }}
        </p>
      </div>
      <Button type="button" :aria-label="t('sources.createSource')">
        <Plus class="size-4" />
        {{ t("sources.createSource") }}
      </Button>
    </header>

    <!-- 数据源列表表格 -->
    <section class="border-border bg-card/80 overflow-hidden rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Source</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Linked projects</TableHead>
            <TableHead>Visibility</TableHead>
            <TableHead>Status</TableHead>
            <TableHead class="w-16 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <!-- 数据源：PDF 文档 -->
          <TableRow>
            <TableCell>
              <strong class="text-foreground font-semibold"
                >Product docs PDF</strong
              >
            </TableCell>
            <TableCell>File</TableCell>
            <TableCell>Docs Assistant</TableCell>
            <TableCell>
              <Badge
                class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
                >Public</Badge
              >
            </TableCell>
            <TableCell>
              <Badge
                class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
                >Indexed</Badge
              >
            </TableCell>
            <TableCell class="text-right">
              <DropdownMenu>
                <DropdownMenuTrigger as-child>
                  <Button
                    type="button"
                    aria-label="Product docs source menu"
                    variant="outline"
                    size="icon-sm"
                  >
                    <Ellipsis class="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem>Manage</DropdownMenuItem>
                  <DropdownMenuItem>Re-index</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
          <!-- 数据源：网页爬取 -->
          <TableRow>
            <TableCell>
              <strong class="text-foreground font-semibold"
                >Main website pages</strong
              >
            </TableCell>
            <TableCell>Web crawl</TableCell>
            <TableCell>Docs Assistant</TableCell>
            <TableCell>
              <Badge
                class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
                >Public</Badge
              >
            </TableCell>
            <TableCell>
              <Badge
                class="border-yellow-300/25 bg-yellow-300/10 text-yellow-100"
                >Processing</Badge
              >
            </TableCell>
            <TableCell class="text-right">
              <DropdownMenu>
                <DropdownMenuTrigger as-child>
                  <Button
                    type="button"
                    aria-label="Main website source menu"
                    variant="outline"
                    size="icon-sm"
                  >
                    <Ellipsis class="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem>Manage</DropdownMenuItem>
                  <DropdownMenuItem>Review items</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  </section>
</template>
