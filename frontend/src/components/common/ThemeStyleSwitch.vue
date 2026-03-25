<script setup lang="ts">
import { computed } from 'vue'
import { themeOptions, useTheme } from '../../composables/useTheme'

const { activeTheme, applyTheme, cycleTheme } = useTheme()
const activeThemeName = computed(
  () => themeOptions.find((theme) => theme.id === activeTheme.value)?.name ?? 'Classroom Workshop',
)
</script>

<template>
  <div class="theme-switcher">
    <button
      v-for="theme in themeOptions"
      :key="theme.id"
      type="button"
      class="theme-button"
      :class="{ 'is-active': activeTheme === theme.id }"
      @click="applyTheme(theme.id)"
    >
      {{ theme.name }}
    </button>
    <button type="button" class="theme-button" @click="cycleTheme">
      轮换风格 · {{ activeThemeName }}
    </button>
  </div>
</template>
