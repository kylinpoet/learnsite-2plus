<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { apiClient } from '../../api/client'
import type { StudentAssignmentsResponse } from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'

const data = ref<StudentAssignmentsResponse | null>(null)
const loading = ref(true)
const error = ref('')

const interactiveCount = computed(
  () => data.value?.activities.filter((activity) => activity.activity_type === 'interactive_page').length ?? 0,
)

async function loadAssignments() {
  loading.value = true
  try {
    const response = await apiClient.get<StudentAssignmentsResponse>('/student/assignments')
    data.value = response.data
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载作业模块。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadAssignments()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="8" animated />

  <div v-else-if="data" class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card surface-card--accent" style="padding: 24px;">
        <div class="hero-task">
          <div class="section-kicker">Assignment Overview</div>
          <h2 class="hero-task__title">{{ data.assignment_title }}</h2>
          <p class="muted">{{ data.assignment_prompt }}</p>
          <div class="hero-task__meta">
            <span class="status-pill">{{ data.lesson_title }}</span>
            <span class="status-pill">提交状态：{{ data.submission.status }}</span>
            <span class="status-pill">版本 v{{ data.submission.version }}</span>
          </div>
          <div class="inline-actions">
            <RouterLink to="/student/assignments/workbench">
              <el-button type="primary">进入书面提交页</el-button>
            </RouterLink>
          </div>
        </div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Activities</div>
        <h2 class="section-heading">本课活动结构</h2>
        <p class="muted">课程和活动已经拆开，先在这里看整体，再按活动进入详情。</p>
      </div>
    </section>

    <section class="metric-grid">
      <MetricCard label="课程活动数" :value="String(data.activities.length)" hint="课程内活动已支持排序" :primary="true" />
      <MetricCard label="交互活动数" :value="String(interactiveCount)" hint="可上传 HTML/ZIP 任务" />
      <MetricCard label="提交历史" :value="String(data.submission_history.length)" hint="书面提交与反馈记录" />
    </section>

    <section class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Activity List</div>
      <h2 class="section-heading">活动列表</h2>
      <div v-if="data.activities.length > 0" class="detail-list">
        <div v-for="activity in data.activities" :key="activity.id" class="detail-item" style="display: grid; gap: 10px;">
          <div class="inline-actions" style="justify-content: space-between;">
            <div class="inline-actions" style="justify-content: flex-start;">
              <div class="status-pill">活动 {{ activity.position }}</div>
              <el-tag :type="activity.activity_type === 'interactive_page' ? 'warning' : 'success'">
                {{ activity.activity_type === 'interactive_page' ? '交互网页' : '富文本活动' }}
              </el-tag>
              <strong>{{ activity.title }}</strong>
            </div>
            <span class="muted" v-if="activity.last_submitted_at">最近提交 {{ activity.last_submitted_at }}</span>
          </div>
          <div class="muted">{{ activity.summary || '进入详情页查看完整活动说明。' }}</div>
          <div class="inline-actions">
            <RouterLink :to="`/student/assignments/activity/${activity.id}`">
              <el-button plain>查看活动详情</el-button>
            </RouterLink>
            <el-tag v-if="activity.latest_submission" type="success">
              已有 {{ activity.submission_count }} 条活动提交
            </el-tag>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">当前课程还没有配置活动。</div>
    </section>
  </div>
</template>
