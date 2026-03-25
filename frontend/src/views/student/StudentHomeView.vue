<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { apiClient } from '../../api/client'
import type { StudentHomeResponse } from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'
import { useSession } from '../../composables/useSession'
import PortalLayout from '../../layouts/PortalLayout.vue'

const { sessionState } = useSession()
const home = ref<StudentHomeResponse | null>(null)
const loading = ref(true)
const error = ref('')
let heartbeatTimer: ReturnType<typeof window.setInterval> | undefined

const navItems = [{ label: '当前课堂', to: '/student/home' }]

async function loadHome() {
  loading.value = true
  try {
    const { data } = await apiClient.get<StudentHomeResponse>('/student/home')
    home.value = data
    error.value = ''
  } catch (requestError) {
    error.value = '学生首页加载失败，请确认后端服务已启动。'
    console.error(requestError)
  } finally {
    loading.value = false
  }
}

async function sendHeartbeat(announce = true) {
  try {
    await apiClient.post('/student/heartbeat', {})
    if (announce) {
      ElMessage.success('课堂心跳已上报')
    }
  } catch (requestError) {
    console.error(requestError)
  }
}

async function askForHelp() {
  try {
    await apiClient.post('/student/help-requests', {
      message: '老师，我需要帮助完成当前任务。',
    })
    ElMessage.success('已向教师端发送求助')
    await loadHome()
  } catch (requestError) {
    ElMessage.error('发送求助失败')
    console.error(requestError)
  }
}

onMounted(async () => {
  await loadHome()
  await sendHeartbeat(false)
  heartbeatTimer = window.setInterval(() => {
    void sendHeartbeat(false)
  }, 25000)
})

onBeforeUnmount(() => {
  if (heartbeatTimer) {
    window.clearInterval(heartbeatTimer)
  }
})
</script>

<template>
  <PortalLayout
    role-label="学生工作区"
    title="当前课堂"
    :subtitle="home?.lesson_stage ?? '围绕本节课任务组织学生视图'"
    :school-name="home?.school_name ?? sessionState?.school_name ?? '加载中...'"
    :user-name="home?.student_name ?? sessionState?.display_name ?? '学生'"
    :nav-items="navItems"
  >
    <el-alert v-if="error" :closable="false" type="warning" :title="error" />

    <div v-else-if="home" class="stack">
      <section class="page-grid page-grid--two">
        <div class="surface-card surface-card--accent" style="padding: 24px;">
          <div class="hero-task">
            <div class="section-kicker">Lesson Stage</div>
            <h2 class="hero-task__title">{{ home.lesson_title }}</h2>
            <p class="muted">{{ home.progress_summary }}</p>
            <div class="hero-task__meta">
              <span class="status-pill">{{ home.class_name }}</span>
              <span class="status-pill">草稿保存于 {{ home.saved_at }}</span>
              <span class="status-pill">{{ home.help_open ? '已发起求助' : '可随时请求帮助' }}</span>
            </div>
            <div class="inline-actions">
              <el-button type="primary" @click="sendHeartbeat()">刷新课堂状态</el-button>
              <el-button plain @click="askForHelp()">向老师举手求助</el-button>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Today</div>
          <h2 class="section-heading">今日待办</h2>
          <div class="list-panel">
            <div v-for="item in home.todo_items" :key="item.title" class="list-row">
              <div class="list-row__main">
                <strong>{{ item.title }}</strong>
                <span class="muted">围绕本节课堂任务推进你的学习步骤</span>
              </div>
              <el-tag :type="item.status === 'done' ? 'success' : item.status === 'active' ? 'warning' : 'info'">
                {{ item.status }}
              </el-tag>
            </div>
          </div>
        </div>
      </section>

      <section class="metric-grid">
        <MetricCard label="学习进度" :value="`${home.progress_percent}%`" hint="课堂进度实时同步" :primary="true" />
        <MetricCard label="作品状态" value="草稿已保存" hint="支持继续编辑后再正式提交" />
        <MetricCard label="班级氛围" value="课堂进行中" hint="老师可通过课堂雷达查看状态" />
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Highlights</div>
          <h2 class="section-heading">本节课重点提醒</h2>
          <div class="detail-list">
            <div v-for="highlight in home.highlights" :key="highlight" class="detail-item">
              <div>{{ highlight }}</div>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Progress</div>
          <h2 class="section-heading">我的课堂进展</h2>
          <el-progress :percentage="home.progress_percent" :stroke-width="18" />
          <div class="empty-state" style="margin-top: 18px;">
            学生端首屏优先显示“当前任务、今日待办、我的进度”，避免回到旧式门户目录布局。
          </div>
        </div>
      </section>
    </div>

    <el-skeleton v-else :rows="8" animated />
  </PortalLayout>
</template>
