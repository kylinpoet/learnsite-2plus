<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { apiClient } from '../../api/client'
import type { TeacherSubmissionsResponse } from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'

const data = ref<TeacherSubmissionsResponse | null>(null)
const loading = ref(true)
const error = ref('')

const pendingCount = computed(
  () => data.value?.submissions.filter((item) => item.status === 'submitted').length ?? 0,
)

async function loadSubmissions() {
  loading.value = true
  try {
    const response = await apiClient.get<TeacherSubmissionsResponse>('/teacher/submissions')
    data.value = response.data
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载作业总览。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadSubmissions()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="8" animated />

  <div v-else-if="data" class="stack">
    <section class="metric-grid">
      <MetricCard label="待批改" :value="String(pendingCount)" hint="进入作品详情执行批改" :primary="true" />
      <MetricCard label="已提交" :value="String(data.analytics.submitted_count)" hint="包含等待批改作品" />
      <MetricCard label="已批改" :value="String(data.analytics.reviewed_count)" hint="进入详情查看历史" />
    </section>

    <section class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Submission Queue</div>
      <h2 class="section-heading">作品队列</h2>
      <div v-if="data.submissions.length > 0" class="detail-list">
        <div v-for="submission in data.submissions" :key="submission.id" class="detail-item" style="display: grid; gap: 10px;">
          <div class="inline-actions" style="justify-content: space-between;">
            <div class="list-row__main">
              <strong>{{ submission.student_name }} · {{ submission.title }}</strong>
              <span class="muted">v{{ submission.version }} · {{ submission.student_username }}</span>
            </div>
            <el-tag :type="submission.status === 'submitted' ? 'success' : submission.status === 'reviewed' ? 'warning' : 'info'">
              {{ submission.status }}
            </el-tag>
          </div>
          <div class="inline-actions">
            <RouterLink :to="`/teacher/submissions/${submission.id}`">
              <el-button type="primary" plain>进入批改详情</el-button>
            </RouterLink>
            <el-tag v-if="submission.help_requested" type="warning">学生有求助</el-tag>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">当前还没有学生提交作品。</div>
    </section>
  </div>
</template>
