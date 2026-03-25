<script setup lang="ts">
defineProps<{
  label: string
  value: string
  hint: string
  primary?: boolean
}>()
</script>

<template>
  <div class="metric-card" :class="{ 'is-primary': primary }">
    <div class="metric-label">{{ label }}</div>
    <div class="metric-value">{{ value }}</div>
    <div class="metric-hint">{{ hint }}</div>
  </div>
</template>
