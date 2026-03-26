<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { apiClient } from '../api/client'
import type { MessageResponse } from '../api/types'
import ThemeStyleSwitch from '../components/common/ThemeStyleSwitch.vue'
import { useSession } from '../composables/useSession'

type NavItem = {
  label: string
  to: string
  caption?: string
}

type NavSection = {
  title?: string
  items: NavItem[]
}

const props = withDefaults(
  defineProps<{
    roleLabel: string
    title: string
    subtitle: string
    schoolName: string
    userName: string
    navItems?: NavItem[]
    topNavItems?: NavItem[]
    sideNavSections?: NavSection[]
    headerPills?: string[]
  }>(),
  {
    navItems: () => [],
    topNavItems: () => [],
    sideNavSections: () => [],
    headerPills: () => [],
  },
)

const router = useRouter()
const { sessionState, clearSession } = useSession()

const logoutPath = computed(() => {
  if (sessionState.value?.role === 'student') {
    return '/'
  }
  return '/teacher/login'
})

const resolvedTopNavItems = computed(() =>
  props.topNavItems.length > 0 ? props.topNavItems : props.navItems,
)

const resolvedSideNavSections = computed(() => {
  if (props.sideNavSections.length > 0) {
    return props.sideNavSections
  }
  if (resolvedTopNavItems.value.length > 0) {
    return [{ title: 'Navigation', items: resolvedTopNavItems.value }]
  }
  return []
})

async function logout() {
  const targetPath = logoutPath.value

  try {
    await apiClient.post<MessageResponse>('/auth/logout')
  } catch (error) {
    console.warn('Remote logout failed, clearing local session anyway.', error)
  } finally {
    clearSession()
    await router.push(targetPath)
    ElMessage.success('Signed out successfully')
  }
}
</script>

<template>
  <div class="portal-shell portal-shell--stacked">
    <header class="surface-card portal-topbar">
      <div class="portal-brand">
        <div class="portal-brand-badge">2+</div>
        <div class="portal-brand-copy">
          <div class="portal-brand-title">LearnSite 2+</div>
          <div class="muted">{{ roleLabel }}</div>
        </div>
      </div>

      <nav v-if="resolvedTopNavItems.length > 0" class="portal-topnav">
        <RouterLink
          v-for="item in resolvedTopNavItems"
          :key="item.to"
          :to="item.to"
          class="portal-topnav-link"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="portal-topbar-actions">
        <ThemeStyleSwitch />
        <el-button type="primary" plain @click="logout">退出当前身份</el-button>
      </div>
    </header>

    <aside class="surface-card portal-sidebar">
      <div class="stack">
        <div class="status-pill">{{ schoolName }}</div>
        <div>
          <div class="portal-sidebar-title">{{ userName }}</div>
          <div class="muted">多学校学习门户已切换到当前工作区</div>
        </div>
      </div>

      <div class="portal-sidebar-sections">
        <section
          v-for="section in resolvedSideNavSections"
          :key="section.title ?? section.items.map((item) => item.to).join('|')"
          class="portal-sidebar-section"
        >
          <div v-if="section.title" class="section-kicker">{{ section.title }}</div>
          <nav class="portal-sidebar-links">
            <RouterLink
              v-for="item in section.items"
              :key="item.to"
              :to="item.to"
              class="portal-sidebar-link"
            >
              <span>{{ item.label }}</span>
              <small v-if="item.caption" class="muted">{{ item.caption }}</small>
            </RouterLink>
          </nav>
        </section>
      </div>
    </aside>

    <main class="surface-card portal-main">
      <header class="portal-page-header">
        <div class="portal-header-copy">
          <div class="portal-header-pills">
            <div class="status-pill">{{ roleLabel }}</div>
            <div v-for="pill in headerPills" :key="pill" class="status-pill">{{ pill }}</div>
          </div>
          <h1 class="portal-title">{{ title }}</h1>
          <p class="portal-subtitle">{{ subtitle }}</p>
        </div>
        <slot name="page-actions" />
      </header>

      <div class="portal-content">
        <slot />
      </div>
    </main>
  </div>
</template>
