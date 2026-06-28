<script setup lang="ts">
import { Button } from "@/shared/components/ui/button";
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <div
      class="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6"
    >
      <p class="text-sm font-medium text-muted-foreground">TadaAsk Console</p>
      <h1 class="mt-3 text-4xl font-semibold tracking-tight">
        Frontend shell is ready.
      </h1>
    </div>
    <Button variant="outline"> Button </Button>
  </main>
</template>

<style scoped></style>
