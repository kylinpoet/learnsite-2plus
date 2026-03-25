<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { apiClient } from '../../api/client'
import type {
  StudentHomeResponse,
  StudentSubmissionSummary,
  SubmissionActionResponse,
  SubmissionUpsertPayload,
} from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'
import { useSession } from '../../composables/useSession'
import PortalLayout from '../../layouts/PortalLayout.vue'

const { sessionState } = useSession()
const home = ref<StudentHomeResponse | null>(null)
const loading = ref(true)
const savingDraft = ref(false)
const submitting = ref(false)
const error = ref('')
let heartbeatTimer: ReturnType<typeof window.setInterval> | undefined

const navItems = [{ label: '当前课堂', to: '/student/home' }]
const submissionForm = reactive<SubmissionUpsertPayload>({
  title: '',
  content: '',
})

function syncSubmissionForm(submission: StudentSubmissionSummary) {
  submissionForm.title = submission.title
  submissionForm.content = submission.content
}

async function loadHome() {
  loading.value = true
  try {
    const { data } = await apiClient.get<StudentHomeResponse>('/student/home')
    home.value = data
    syncSubmissionForm(data.submission)
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
    await apiClient.post('/student/heartbeat', {
      task_progress: home.value?.progress_percent ?? 72,
    })
    if (announce) {
      ElMessage.success('课堂状态已刷新')
    }
  } catch (requestError) {
    console.error(requestError)
  }
}

async function askForHelp() {
  try {
    await apiClient.post('/student/help-requests', {
      message: '老师，我需要帮助完成当前课堂作品。',
    })
    ElMessage.success('已向教师端发送求助')
    await loadHome()
  } catch (requestError) {
    ElMessage.error('发送求助失败')
    console.error(requestError)
  }
}

async function persistSubmission(mode: 'draft' | 'submit') {
  if (!submissionForm.title.trim() || !submissionForm.content.trim()) {
    ElMessage.warning('请先填写作品标题和内容')
    return
  }

  const target = mode === 'draft' ? savingDraft : submitting
  target.value = true
  try {
    const endpoint = mode === 'draft' ? '/student/submission/draft' : '/student/submission/submit'
    const { data } = await apiClient.post<SubmissionActionResponse>(endpoint, submissionForm)
    if (home.value) {
      home.value.submission = data.submission
      home.value.saved_at = data.submission.draft_saved_at ?? home.value.saved_at
      home.value.progress_percent = mode === 'submit' ? 100 : Math.max(home.value.progress_percent, 82)
      home.value.todo_items = home.value.todo_items.map((item) =>
        item.title.includes('正式提交')
          ? { ...item, status: mode === 'submit' ? 'done' : item.status }
          : item,
      )
    }
    ElMessage.success(mode === 'draft' ? '草稿已保存' : '作品已正式提交')
    await loadHome()
  } catch (requestError) {
    ElMessage.error(mode === 'draft' ? '保存草稿失败' : '正式提交失败')
    console.error(requestError)
  } finally {
    target.value = false
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
              <span class="status-pill">签到状态：{{ home.attendance_status }}</span>
              <span class="status-pill">
                {{ home.submission.submitted_at ? `已提交 ${home.submission.submitted_at}` : `草稿保存于 ${home.saved_at}` }}
              </span>
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
                <span class="muted">围绕本节课堂作品推进你的学习步骤</span>
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
        <MetricCard
          label="作品状态"
          :value="home.submission.status === 'submitted' ? '已正式提交' : '草稿编辑中'"
          hint="支持先保存草稿，再正式提交"
        />
        <MetricCard label="提交版本" :value="`v${home.submission.version}`" hint="每次保存都会产生新的草稿版本" />
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Assignment</div>
          <h2 class="section-heading">{{ home.assignment_title }}</h2>
          <p class="muted" style="margin-bottom: 18px;">{{ home.assignment_prompt }}</p>

          <el-form label-position="top">
            <el-form-item label="作品标题">
              <el-input
                v-model="submissionForm.title"
                maxlength="128"
                placeholder="例如：我的课堂图表作品"
                :disabled="!home.submission.can_edit"
              />
            </el-form-item>

            <el-form-item label="作品内容">
              <el-input
                v-model="submissionForm.content"
                type="textarea"
                :rows="10"
                maxlength="5000"
                show-word-limit
                placeholder="填写你的数据观察、图表说明和课堂结论"
                :disabled="!home.submission.can_edit"
              />
            </el-form-item>

            <div class="inline-actions">
              <el-button type="primary" plain :loading="savingDraft" :disabled="!home.submission.can_edit" @click="persistSubmission('draft')">
                保存草稿
              </el-button>
              <el-button type="primary" :loading="submitting" :disabled="!home.submission.can_edit" @click="persistSubmission('submit')">
                正式提交
              </el-button>
            </div>
          </el-form>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Highlights</div>
          <h2 class="section-heading">本节课重点提醒</h2>
          <div class="detail-list">
            <div v-for="highlight in home.highlights" :key="highlight" class="detail-item">
              <div>{{ highlight }}</div>
            </div>
          </div>

          <div class="empty-state" style="margin-top: 18px;">
            当前提交状态：{{ home.submission.status }}<br />
            {{ home.submission.submitted_at ? `提交时间：${home.submission.submitted_at}` : '尚未正式提交，可继续编辑。' }}
          </div>
        </div>
      </section>
    </div>

    <el-skeleton v-else :rows="8" animated />
  </PortalLayout>
</template>
