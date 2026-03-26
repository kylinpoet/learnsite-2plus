<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '../../api/client'
import type { StartSessionPayload, TeacherDashboardResponse } from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'

const router = useRouter()
const data = ref<TeacherDashboardResponse | null>(null)
const loading = ref(true)
const error = ref('')
const startingSession = ref(false)
const selectedLaunchKey = ref('')

const launchOptions = computed(() =>
  (data.value?.launch_options ?? []).map((option) => ({
    ...option,
    key: `${option.classroom_id}:${option.course_id}`,
  })),
)

async function loadDashboard() {
  loading.value = true
  try {
    const response = await apiClient.get<TeacherDashboardResponse>('/teacher/dashboard')
    data.value = response.data
    if (!launchOptions.value.some((option) => option.key === selectedLaunchKey.value)) {
      selectedLaunchKey.value = launchOptions.value[0]?.key ?? ''
    }
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载教师总览。'
  } finally {
    loading.value = false
  }
}

async function startSession() {
  const selected = launchOptions.value.find((option) => option.key === selectedLaunchKey.value)
  if (!selected) {
    ElMessage.warning('请先选择一个班级和课程')
    return
  }

  startingSession.value = true
  try {
    const payload: StartSessionPayload = {
      classroom_id: selected.classroom_id,
      course_id: selected.course_id,
    }
    const response = await apiClient.post('/teacher/session/start', payload)
    ElMessage.success('已开始新课堂')
    await loadDashboard()
    const sessionId = response.data.session_id as number | undefined
    if (sessionId) {
      await router.push(`/teacher/attendance/sessions/${sessionId}`)
    }
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('开课失败')
  } finally {
    startingSession.value = false
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
          <div class="section-kicker">Live Classroom</div>
          <h2 class="hero-task__title">{{ data.lesson_title }}</h2>
          <p class="muted">总览页只保留课堂概况、风险和发课入口，具体操作分流到签到与作业子页。</p>
          <div class="hero-task__meta">
            <span class="status-pill">{{ data.class_name }}</span>
            <span class="status-pill">会话状态：{{ data.session_status }}</span>
            <span class="status-pill">作业：{{ data.assignment_title }}</span>
          </div>
        </div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Launch Session</div>
        <h2 class="section-heading">开课入口</h2>
        <el-select v-model="selectedLaunchKey" class="full-width" placeholder="选择班级与课程">
          <el-option
            v-for="option in launchOptions"
            :key="option.key"
            :label="`${option.classroom_name} · ${option.course_title}`"
            :value="option.key"
          />
        </el-select>
        <div class="inline-actions" style="margin-top: 18px;">
          <el-button type="primary" :loading="startingSession" @click="startSession">开始新课堂</el-button>
        </div>
      </div>
    </section>

    <section class="metric-grid">
      <MetricCard label="在线人数" :value="`${data.radar.online}/${data.radar.expected}`" hint="课堂实时雷达" :primary="true" />
      <MetricCard label="出勤率" :value="`${data.analytics.attendance_rate}%`" hint="签到页查看详细名单" />
      <MetricCard label="提交率" :value="`${data.analytics.submission_rate}%`" hint="作业页查看提交详情" />
    </section>

    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Focus Students</div>
        <h2 class="section-heading">需要关注的学生</h2>
        <div v-if="data.analytics.attention_students.length > 0" class="detail-list">
          <div
            v-for="student in data.analytics.attention_students"
            :key="student.student_username"
            class="detail-item"
            style="display: grid; gap: 8px;"
          >
            <strong>{{ student.student_name }} · {{ student.student_username }}</strong>
            <div class="muted">进度 {{ student.progress_percent }}% · {{ student.presence_status }}</div>
            <div>{{ student.reason }}</div>
          </div>
        </div>
        <div v-else class="empty-state">当前没有高优先级风险学生。</div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Workbench</div>
        <h2 class="section-heading">工作台摘要</h2>
        <div class="detail-list">
          <div v-for="step in data.workbench_steps" :key="step.title" class="detail-item">
            <div class="list-row__main">
              <strong>{{ step.title }}</strong>
              <span class="muted">详细处理请进入对应子页面。</span>
            </div>
            <el-tag :type="step.status === 'done' ? 'success' : step.status === 'active' ? 'warning' : 'info'">
              {{ step.status }}
            </el-tag>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
