<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { apiClient, buildApiUrl } from '../../api/client'
import type {
  AttendanceRecordSummary,
  AttendanceStatus,
  StartSessionPayload,
  TeacherConsoleResponse,
  TeacherDraft,
} from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'
import { useSession } from '../../composables/useSession'
import PortalLayout from '../../layouts/PortalLayout.vue'

const { sessionState } = useSession()
const consoleData = ref<TeacherConsoleResponse | null>(null)
const loadError = ref('')
const radarWarning = ref('')
const generating = ref(false)
const startingSession = ref(false)
const draftGoal = ref('为当前学案生成 3 条分层课堂活动建议')
const selectedLaunchKey = ref('')
let source: EventSource | undefined

const isAdminSession = computed(
  () =>
    sessionState.value?.role === 'school_admin' ||
    sessionState.value?.role === 'platform_admin',
)

const navItems = computed(() =>
  isAdminSession.value
    ? [
        { label: '课堂控制台', to: '/teacher/console' },
        { label: '治理总览', to: '/admin/overview' },
      ]
    : [{ label: '课堂控制台', to: '/teacher/console' }],
)

const roleLabel = computed(() => (isAdminSession.value ? '教师管理员工作区' : '教师工作区'))
const subtitle = computed(() =>
  isAdminSession.value
    ? '管理员通过同一入口登录，并以教师控制台作为默认落点。'
    : '开课、签到、作品提交和 AI 副驾集中在同一工作台。',
)

const launchOptions = computed(() =>
  (consoleData.value?.launch_options ?? []).map((option) => ({
    ...option,
    key: `${option.classroom_id}:${option.course_id}`,
  })),
)

const currentLaunchLabel = computed(() =>
  consoleData.value
    ? `${consoleData.value.class_name} · ${consoleData.value.lesson_title}`
    : '尚未加载课堂上下文',
)

function syncLaunchSelection() {
  if (!selectedLaunchKey.value && launchOptions.value.length > 0) {
    selectedLaunchKey.value = launchOptions.value[0].key
  }
}

async function loadConsole() {
  try {
    const { data } = await apiClient.get<TeacherConsoleResponse>('/teacher/console')
    consoleData.value = data
    loadError.value = ''
    syncLaunchSelection()
  } catch (requestError) {
    loadError.value = '教师控制台加载失败，请确认后端服务已启动。'
    console.error(requestError)
  }
}

function connectRadar() {
  const token = sessionState.value?.token
  if (!token) {
    return
  }

  source = new EventSource(`${buildApiUrl('/teacher/radar/stream')}?token=${encodeURIComponent(token)}`)
  source.onmessage = (event) => {
    if (!consoleData.value) {
      return
    }

    consoleData.value.radar = JSON.parse(event.data) as TeacherConsoleResponse['radar']
    radarWarning.value = ''
  }
  source.onerror = () => {
    radarWarning.value = '课堂实时雷达连接断开，请稍后重试。'
  }
}

async function startSession() {
  if (!selectedLaunchKey.value) {
    ElMessage.warning('请先选择要开课的班级和课程')
    return
  }

  const [classroomIdText, courseIdText] = selectedLaunchKey.value.split(':')
  const payload: StartSessionPayload = {
    classroom_id: Number(classroomIdText),
    course_id: Number(courseIdText),
  }

  startingSession.value = true
  try {
    const { data } = await apiClient.post<TeacherConsoleResponse>('/teacher/session/start', payload)
    consoleData.value = data
    syncLaunchSelection()
    ElMessage.success('新课次已开始，签到记录已初始化')
  } catch (requestError) {
    ElMessage.error('开课失败')
    console.error(requestError)
  } finally {
    startingSession.value = false
  }
}

async function markAttendance(record: AttendanceRecordSummary, status: AttendanceStatus) {
  try {
    await apiClient.post(`/teacher/attendance/${record.id}/mark`, {
      status,
      note: status === 'late' ? '教师手动标记迟到' : undefined,
    })
    ElMessage.success(`已更新 ${record.student_name} 的签到状态`)
    await loadConsole()
  } catch (requestError) {
    ElMessage.error('签到更新失败')
    console.error(requestError)
  }
}

async function generateDraft() {
  generating.value = true
  try {
    const { data } = await apiClient.post<{ draft: TeacherDraft }>('/teacher/ai/drafts', {
      goal: draftGoal.value,
    })
    consoleData.value?.ai_drafts.unshift(data.draft)
    ElMessage.success('AI 草稿已生成，仍需教师确认后使用')
  } catch (requestError) {
    ElMessage.error('AI 草稿生成失败')
    console.error(requestError)
  } finally {
    generating.value = false
  }
}

onMounted(async () => {
  await loadConsole()
  connectRadar()
})

onBeforeUnmount(() => {
  source?.close()
})
</script>

<template>
  <PortalLayout
    :role-label="roleLabel"
    title="课堂控制台"
    :subtitle="subtitle"
    :school-name="consoleData?.school_name ?? sessionState?.school_name ?? '加载中...'"
    :user-name="consoleData?.teacher_name ?? sessionState?.display_name ?? '教师'"
    :nav-items="navItems"
  >
    <el-alert v-if="loadError && !consoleData" :closable="false" type="warning" :title="loadError" />
    <el-alert v-if="radarWarning" :closable="false" type="warning" :title="radarWarning" />

    <div v-else-if="consoleData" class="stack">
      <section class="metric-grid">
        <MetricCard label="出勤状态" :value="`${consoleData.radar.online} / ${consoleData.radar.expected}`" hint="当前课堂在线人数" :primary="true" />
        <MetricCard label="未进入任务" :value="String(consoleData.radar.not_started)" hint="需要教师重点关注" />
        <MetricCard label="作品提交" :value="String(consoleData.submissions.filter((item) => item.status !== 'draft').length)" hint="当前已正式提交作品数" />
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Session Control</div>
          <h2 class="section-heading">开课台</h2>
          <p class="muted" style="margin-bottom: 16px;">当前课堂：{{ currentLaunchLabel }}</p>
          <el-form label-position="top">
            <el-form-item label="选择要开始的班级 / 课程">
              <el-select v-model="selectedLaunchKey" class="full-width" placeholder="请选择班级和课程">
                <el-option
                  v-for="option in launchOptions"
                  :key="option.key"
                  :label="`${option.classroom_name} · ${option.course_title}`"
                  :value="option.key"
                />
              </el-select>
            </el-form-item>
            <el-button type="primary" :loading="startingSession" @click="startSession">
              开始新课次
            </el-button>
          </el-form>

          <div class="empty-state" style="margin-top: 18px;">
            当前任务：{{ consoleData.assignment_title }}<br />
            课堂状态：{{ consoleData.session_status }}
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Live Radar</div>
          <h2 class="section-heading">{{ consoleData.class_name }} · {{ consoleData.lesson_title }}</h2>
          <div class="radar-grid">
            <div class="radar-card">
              <div class="muted">未签到 / 离线</div>
              <strong>{{ consoleData.radar.absent }}</strong>
              <div class="muted">持续超时未上报心跳的学生</div>
            </div>
            <div class="radar-card">
              <div class="muted">长时间停留</div>
              <strong>{{ consoleData.radar.idle }}</strong>
              <div class="muted">可能卡在某个课堂步骤中</div>
            </div>
            <div class="radar-card">
              <div class="muted">未进入任务</div>
              <strong>{{ consoleData.radar.not_started }}</strong>
              <div class="muted">尚未开始课堂作品的学生</div>
            </div>
            <div class="radar-card">
              <div class="muted">举手求助</div>
              <strong>{{ consoleData.radar.help_requests }}</strong>
              <div class="muted">等待教师优先响应的求助数</div>
            </div>
          </div>
        </div>
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Attendance</div>
          <h2 class="section-heading">签到记录</h2>
          <div class="list-panel">
            <div v-for="record in consoleData.attendance_records" :key="record.id" class="detail-item" style="display: grid; gap: 10px;">
              <div class="list-row__main">
                <strong>{{ record.student_name }} · {{ record.student_username }}</strong>
                <span class="muted">
                  当前状态：{{ record.status }}
                  <span v-if="record.marked_at"> · 标记于 {{ record.marked_at }}</span>
                  <span v-if="record.last_seen_at"> · 最近心跳 {{ record.last_seen_at }}</span>
                </span>
              </div>
              <div class="inline-actions">
                <el-button size="small" @click="markAttendance(record, 'present')">签到</el-button>
                <el-button size="small" plain @click="markAttendance(record, 'late')">迟到</el-button>
                <el-button size="small" type="danger" plain @click="markAttendance(record, 'absent')">缺席</el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Submissions</div>
          <h2 class="section-heading">作品提交队列</h2>
          <div class="list-panel" v-if="consoleData.submissions.length > 0">
            <div v-for="submission in consoleData.submissions" :key="submission.id" class="list-row">
              <div class="list-row__main">
                <strong>{{ submission.student_name }} · {{ submission.title }}</strong>
                <span class="muted">
                  版本 v{{ submission.version }}
                  <span v-if="submission.draft_saved_at"> · 草稿 {{ submission.draft_saved_at }}</span>
                  <span v-if="submission.submitted_at"> · 提交 {{ submission.submitted_at }}</span>
                </span>
              </div>
              <el-tag :type="submission.status === 'submitted' ? 'success' : 'info'">
                {{ submission.status }}
              </el-tag>
            </div>
          </div>
          <div v-else class="empty-state">当前还没有学生提交作品。</div>
        </div>
      </section>

      <section class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Teacher AI Copilot</div>
        <h2 class="section-heading">教师 AI 副驾</h2>
        <p class="muted">所有 AI 输出都处于草稿态，需要教师审阅、编辑、确认后才能进入正式流程。</p>
        <div class="page-grid page-grid--two" style="margin-top: 18px;">
          <div class="stack">
            <el-input
              v-model="draftGoal"
              type="textarea"
              :rows="5"
              placeholder="描述你希望 AI 生成的课堂建议或反馈草稿"
            />
            <el-button type="primary" :loading="generating" @click="generateDraft">
              生成 AI 草稿
            </el-button>
          </div>

          <div class="stack">
            <div
              v-for="draft in consoleData.ai_drafts"
              :key="draft.id"
              class="detail-item"
              style="display: grid; gap: 10px;"
            >
              <div class="status-pill">{{ draft.draft_type }}</div>
              <strong>{{ draft.title }}</strong>
              <div class="muted">{{ draft.content }}</div>
              <div class="mono muted">{{ draft.created_at }} · {{ draft.status }}</div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <el-skeleton v-else :rows="8" animated />
  </PortalLayout>
</template>
