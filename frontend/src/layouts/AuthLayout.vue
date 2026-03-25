<script setup lang="ts">
import { RouterLink } from 'vue-router'
import ThemeStyleSwitch from '../components/common/ThemeStyleSwitch.vue'

defineProps<{
  eyebrow: string
  title: string
  description: string
  highlights: string[]
  roleLinks: Array<{ label: string; to: string }>
}>()
</script>

<template>
  <div class="auth-shell">
    <section class="surface-card auth-hero surface-card--accent">
      <div class="auth-topbar">
        <div class="auth-brand">
          <div class="auth-brand-mark">2+</div>
          <div>
            <div style="font-size: 18px; font-weight: 900;">LearnSite 2+</div>
            <div class="muted">信息科技学生学习综合门户平台</div>
          </div>
        </div>
        <ThemeStyleSwitch />
      </div>

      <div class="auth-hero-copy">
        <div class="auth-eyebrow">{{ eyebrow }}</div>
        <h1 class="auth-title">{{ title }}</h1>
        <p class="auth-description">{{ description }}</p>
        <div class="auth-highlight-list">
          <div v-for="highlight in highlights" :key="highlight" class="auth-highlight">
            {{ highlight }}
          </div>
        </div>
      </div>

      <div class="auth-link-list">
        <RouterLink v-for="link in roleLinks" :key="link.to" :to="link.to" class="auth-link">
          {{ link.label }}
        </RouterLink>
      </div>
    </section>

    <section class="surface-card auth-form-card surface-card--hero">
      <slot />
    </section>
  </div>
</template>
