<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { apiClient } from '../../api/client'
import type { StudentDashboardResponse } from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'

const data = ref<StudentDashboardResponse | null>(null)
const loading = ref(true)
const error = ref('')

async function loadDashboard() {
  loading.value = true
  try {
    const response = await apiClient.get<StudentDashboardResponse>('/student/dashboard')
    data.value = response.data
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载学习总览，请确认学生端服务可用。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadDashboard()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />

  <el-skeleton v-else-if="loading" :rows="8" animated />

  <div v-else-if="data" class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card surface-card--accent" style="padding: 24px;">
        <div class="hero-task">
          <div class="section-kicker">Current Lesson</div>
          <h2 class="hero-task__title">{{ data.lesson_title }}</h2>
          <p class="muted">{{ data.progress_summary }}</p>
          <div class="hero-task__meta">
            <span class="status-pill">{{ data.class_name }}</span>
            <span class="status-pill">课堂阶段：{{ data.lesson_stage }}</span>
            <span class="status-pill">签到状态：{{ data.attendance_status }}</span>
          </div>
          <div class="inline-actions">
            <RouterLink to="/student/attendance">
              <el-button type="primary">去签到页</el-button>
            </RouterLink>
            <RouterLink to="/student/assignments">
              <el-button plain>查看作业模块</el-button>
            </RouterLink>
          </div>
        </div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Next Step</div>
        <h2 class="section-heading">本节待办</h2>
        <div class="list-panel">
          <div v-for="item in data.todo_items" :key="item.title" class="list-row">
            <div class="list-row__main">
              <strong>{{ item.title }}</strong>
              <span class="muted">按模块拆分后，这里只保留摘要提醒。</span>
            </div>
            <el-tag :type="item.status === 'done' ? 'success' : item.status === 'active' ? 'warning' : 'info'">
              {{ item.status }}
            </el-tag>
          </div>
        </div>
      </div>
    </section>

    <section class="metric-grid">
      <MetricCard label="课堂进度" :value="`${data.progress_percent}%`" hint="来自实时学习进度" :primary="true" />
      <MetricCard label="课堂状态" :value="data.session_status" hint="当前课堂会话状态" />
      <MetricCard label="求助状态" :value="data.help_open ? '已发起求助' : '暂无求助'" hint="需要时可去作业页举手" />
    </section>

    <section class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Highlights</div>
      <h2 class="section-heading">课堂提醒</h2>
      <div class="detail-list">
        <div v-for="highlight in data.highlights" :key="highlight" class="detail-item">
          <div>{{ highlight }}</div>
        </div>
      </div>
    </section>
  </div>
</template>
