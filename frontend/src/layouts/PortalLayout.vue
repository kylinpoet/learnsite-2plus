<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import ThemeStyleSwitch from '../components/common/ThemeStyleSwitch.vue'
import { useSession } from '../composables/useSession'

const props = defineProps<{
  roleLabel: string
  title: string
  subtitle: string
  schoolName: string
  userName: string
  navItems: Array<{ label: string; to: string }>
}>()

const router = useRouter()
const { sessionState, clearSession } = useSession()

const logoutPath = computed(() => {
  if (sessionState.value?.role === 'student') {
    return '/'
  }
  return '/teacher/login'
})

function logout() {
  clearSession()
  router.push(logoutPath.value)
}
</script>

<template>
  <div class="portal-shell">
    <aside class="surface-card portal-nav">
      <div class="portal-brand">
        <div class="portal-brand-badge">2+</div>
        <div>
          <div style="font-size: 18px; font-weight: 900;">LearnSite 2+</div>
          <div class="muted">{{ roleLabel }}</div>
        </div>
      </div>

      <div class="stack">
        <div class="status-pill">{{ schoolName }}</div>
        <div>
          <div style="font-weight: 800;">{{ userName }}</div>
          <div class="muted">已进入多学校门户工作区</div>
        </div>
      </div>

      <nav class="portal-links">
        <RouterLink v-for="item in props.navItems" :key="item.to" :to="item.to" class="portal-link">
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="muted" style="font-size: 13px;">
        当前版本优先打通学生学习、教师上课、学校管理三条主线，后续继续扩展更多教学模块。
      </div>
    </aside>

    <main class="surface-card portal-main">
      <header class="portal-header">
        <div class="portal-header-copy">
          <div class="status-pill">{{ roleLabel }}</div>
          <h1 class="portal-title">{{ title }}</h1>
          <p class="portal-subtitle">{{ subtitle }}</p>
        </div>

        <div class="portal-actions">
          <ThemeStyleSwitch />
          <el-button type="primary" plain @click="logout">退出当前身份</el-button>
        </div>
      </header>

      <slot />
    </main>
  </div>
</template>
