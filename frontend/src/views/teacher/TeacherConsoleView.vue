<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { apiClient, buildApiUrl } from '../../api/client'
import type {
  AttendanceRecordSummary,
  AttendanceStatus,
  ReviewDecision,
  StartSessionPayload,
  SubmissionQueueItem,
  SubmissionReviewPayload,
  TeacherConsoleResponse,
  TeacherDraft,
  TeacherSubmissionDetail,
} from '../../api/types'
import MigrationAdminPanel from '../../components/admin/MigrationAdminPanel.vue'
import MetricCard from '../../components/common/MetricCard.vue'
import { useSession } from '../../composables/useSession'
import PortalLayout from '../../layouts/PortalLayout.vue'

const { sessionState } = useSession()
const consoleData = ref<TeacherConsoleResponse | null>(null)
const selectedSubmission = ref<TeacherSubmissionDetail | null>(null)
const selectedSubmissionId = ref<number | null>(null)
const loadError = ref('')
const radarWarning = ref('')
const generating = ref(false)
const startingSession = ref(false)
const loadingSubmission = ref(false)
const reviewing = ref(false)
const generatingFeedbackDraft = ref(false)
const draftGoal = ref('为当前学案生成 3 条分层课堂活动建议')
const reviewForm = reactive<SubmissionReviewPayload>({
  decision: 'revision_requested',
  feedback: '',
  resolve_help_requests: true,
})
const selectedLaunchKey = ref('')
const source = ref<EventSource | null>(null)

const isAdminSession = computed(
  () => sessionState.value?.role === 'school_admin' || sessionState.value?.role === 'platform_admin',
)

const navItems = computed(() => [{ label: '课堂控制台', to: '/teacher/console' }])

const roleLabel = computed(() => (isAdminSession.value ? '教师管理员工作区' : '教师工作区'))
const subtitle = computed(() =>
  isAdminSession.value
    ? '管理员通过教师入口登录后，在同一页同时处理课堂任务和迁移治理任务。'
    : '开课、签到、求助响应、作业批改和 AI 副驾集中在同一工作台。',
)

const launchOptions = computed(() =>
  (consoleData.value?.launch_options ?? []).map((option) => ({
    ...option,
    key: `${option.classroom_id}:${option.course_id}`,
  })),
)

const pendingReviewCount = computed(
  () => consoleData.value?.submissions.filter((item) => item.status === 'submitted').length ?? 0,
)

const currentLaunchLabel = computed(() =>
  consoleData.value ? `${consoleData.value.class_name} · ${consoleData.value.lesson_title}` : '尚未加载课堂上下文',
)

const selectedSubmissionSummary = computed<SubmissionQueueItem | null>(() => {
  if (!consoleData.value || selectedSubmissionId.value === null) {
    return null
  }
  return consoleData.value.submissions.find((item) => item.id === selectedSubmissionId.value) ?? null
})

const reviewDecisionOptions: Array<{ value: ReviewDecision; label: string }> = [
  { value: 'approved', label: '通过' },
  { value: 'revision_requested', label: '修改后重交' },
  { value: 'rejected', label: '暂不通过' },
]

const reviewDecisionLabelMap: Record<ReviewDecision, string> = {
  approved: '已通过',
  revision_requested: '需要修改后重交',
  rejected: '暂不通过',
}

function reviewTagType(decision: ReviewDecision | null | undefined) {
  if (decision === 'approved') {
    return 'success'
  }
  if (decision === 'revision_requested') {
    return 'warning'
  }
  if (decision === 'rejected') {
    return 'danger'
  }
  return 'info'
}

function submissionTagType(submission: SubmissionQueueItem) {
  if (submission.status === 'reviewed') {
    return reviewTagType(submission.review_decision)
  }
  return submission.status === 'submitted' ? 'success' : 'info'
}

function submissionTagLabel(submission: SubmissionQueueItem) {
  if (submission.status === 'reviewed' && submission.review_decision) {
    return reviewDecisionLabelMap[submission.review_decision]
  }
  if (submission.status === 'submitted') {
    return '待批改'
  }
  return '草稿'
}

function historyEntryLabel(entry: TeacherSubmissionDetail['history'][number]) {
  if (entry.entry_type === 'reviewed') {
    return reviewDecisionLabelMap[entry.decision ?? 'revision_requested']
  }
  if (entry.entry_type === 'submitted') {
    return '正式提交'
  }
  return `草稿 v${entry.version ?? ''}`.trim()
}

function syncLaunchSelection() {
  if (!launchOptions.value.length) {
    return
  }
  if (!launchOptions.value.some((option) => option.key === selectedLaunchKey.value)) {
    selectedLaunchKey.value = launchOptions.value[0].key
  }
}

async function syncSelectedSubmission(preferredId?: number) {
  const submissions = consoleData.value?.submissions ?? []
  if (!submissions.length) {
    selectedSubmission.value = null
    selectedSubmissionId.value = null
    return
  }

  const targetId =
    preferredId ??
    (selectedSubmissionId.value && submissions.some((item) => item.id === selectedSubmissionId.value)
      ? selectedSubmissionId.value
      : (submissions.find((item) => item.help_requested && item.status !== 'draft') ??
          submissions.find((item) => item.status === 'submitted') ??
          submissions[0]
        ).id)

  if (targetId !== null) {
    await loadSubmissionDetail(targetId)
  }
}

function fillReviewForm(detail: TeacherSubmissionDetail) {
  reviewForm.decision = detail.review_decision ?? 'revision_requested'
  reviewForm.feedback = detail.teacher_feedback ?? ''
  reviewForm.resolve_help_requests = true
}

async function loadConsole() {
  try {
    const { data } = await apiClient.get<TeacherConsoleResponse>('/teacher/console')
    consoleData.value = data
    loadError.value = ''
    syncLaunchSelection()
    await syncSelectedSubmission()
  } catch (requestError) {
    loadError.value = '教师控制台加载失败，请确认后端服务已经启动。'
    console.error(requestError)
  }
}

async function loadSubmissionDetail(submissionId: number) {
  loadingSubmission.value = true
  selectedSubmissionId.value = submissionId
  try {
    const { data } = await apiClient.get<TeacherSubmissionDetail>(`/teacher/submissions/${submissionId}`)
    selectedSubmission.value = data
    fillReviewForm(data)
  } catch (requestError) {
    ElMessage.error('加载作品详情失败')
    console.error(requestError)
  } finally {
    loadingSubmission.value = false
  }
}

function connectRadar() {
  const token = sessionState.value?.token
  if (!token) {
    return
  }

  source.value?.close()
  source.value = new EventSource(`${buildApiUrl('/teacher/radar/stream')}?token=${encodeURIComponent(token)}`)
  source.value.onmessage = (event) => {
    if (!consoleData.value) {
      return
    }
    consoleData.value.radar = JSON.parse(event.data) as TeacherConsoleResponse['radar']
    radarWarning.value = ''
  }
  source.value.onerror = () => {
    radarWarning.value = '课堂实时雷达连接中断，请稍后重试。'
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
    await syncSelectedSubmission()
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
    ElMessage.success('AI 课堂建议草稿已生成')
  } catch (requestError) {
    ElMessage.error('AI 草稿生成失败')
    console.error(requestError)
  } finally {
    generating.value = false
  }
}

async function generateFeedbackDraft() {
  if (!selectedSubmission.value) {
    return
  }

  generatingFeedbackDraft.value = true
  try {
    const { data } = await apiClient.post<{ draft: TeacherDraft }>(
      `/teacher/submissions/${selectedSubmission.value.id}/feedback-draft`,
    )
    reviewForm.feedback = data.draft.content
    consoleData.value?.ai_drafts.unshift(data.draft)
    ElMessage.success('批改反馈草稿已生成，并已填入右侧表单')
  } catch (requestError) {
    ElMessage.error('反馈草稿生成失败')
    console.error(requestError)
  } finally {
    generatingFeedbackDraft.value = false
  }
}

async function submitReview() {
  if (!selectedSubmission.value) {
    return
  }
  if (!reviewForm.feedback.trim()) {
    ElMessage.warning('请先填写反馈内容')
    return
  }

  reviewing.value = true
  try {
    const { data } = await apiClient.post<TeacherSubmissionDetail>(
      `/teacher/submissions/${selectedSubmission.value.id}/review`,
      reviewForm,
    )
    selectedSubmission.value = data
    fillReviewForm(data)
    await loadConsole()
    ElMessage.success('批改反馈已发布')
  } catch (requestError) {
    ElMessage.error('发布批改失败')
    console.error(requestError)
  } finally {
    reviewing.value = false
  }
}

onMounted(async () => {
  await loadConsole()
  connectRadar()
})

onBeforeUnmount(() => {
  source.value?.close()
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
        <MetricCard label="在线状态" :value="`${consoleData.radar.online} / ${consoleData.radar.expected}`" hint="当前课堂在线人数" :primary="true" />
        <MetricCard label="待响应求助" :value="String(consoleData.radar.help_requests)" hint="需要老师优先关注的学生" />
        <MetricCard label="待批改作品" :value="String(pendingReviewCount)" hint="已提交但尚未发布反馈的作品" />
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
              <div class="muted">长时间停滞</div>
              <strong>{{ consoleData.radar.idle }}</strong>
              <div class="muted">可能卡在某个课堂步骤中的学生</div>
            </div>
            <div class="radar-card">
              <div class="muted">未进入任务</div>
              <strong>{{ consoleData.radar.not_started }}</strong>
              <div class="muted">还没有开始作品的学生</div>
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
          <div class="section-kicker">Help Requests</div>
          <h2 class="section-heading">课堂求助队列</h2>
          <div v-if="consoleData.help_requests.length > 0" class="detail-list">
            <div v-for="request in consoleData.help_requests" :key="request.id" class="detail-item" style="display: grid; gap: 10px;">
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-tag :type="request.status === 'open' ? 'warning' : 'info'">{{ request.status }}</el-tag>
                <strong>{{ request.student_name }} · {{ request.student_username }}</strong>
              </div>
              <div>{{ request.message }}</div>
              <div class="muted">{{ request.created_at }}</div>
            </div>
          </div>
          <div v-else class="empty-state">当前没有新的课堂求助。</div>
        </div>
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Submissions</div>
          <h2 class="section-heading">作品提交队列</h2>
          <div class="list-panel" v-if="consoleData.submissions.length > 0">
            <div
              v-for="submission in consoleData.submissions"
              :key="submission.id"
              class="detail-item"
              style="display: grid; gap: 10px; cursor: pointer;"
              :style="selectedSubmissionId === submission.id ? 'outline: 2px solid var(--accent-strong);' : ''"
              @click="loadSubmissionDetail(submission.id)"
            >
              <div class="list-row__main">
                <strong>{{ submission.student_name }} · {{ submission.title }}</strong>
                <span class="muted">
                  版本 v{{ submission.version }}
                  <span v-if="submission.draft_saved_at"> · 草稿 {{ submission.draft_saved_at }}</span>
                  <span v-if="submission.submitted_at"> · 提交 {{ submission.submitted_at }}</span>
                  <span v-if="submission.reviewed_at"> · 批改 {{ submission.reviewed_at }}</span>
                </span>
              </div>
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-tag :type="submissionTagType(submission)">{{ submissionTagLabel(submission) }}</el-tag>
                <el-tag v-if="submission.help_requested" type="warning">有求助</el-tag>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">当前还没有学生作品。</div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Review Workspace</div>
          <h2 class="section-heading">批改工作位</h2>

          <el-skeleton v-if="loadingSubmission" :rows="6" animated />
          <div v-else-if="selectedSubmission" class="stack">
            <div class="inline-actions" style="justify-content: space-between;">
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-tag :type="selectedSubmissionSummary ? submissionTagType(selectedSubmissionSummary) : 'info'">
                  {{ selectedSubmissionSummary ? submissionTagLabel(selectedSubmissionSummary) : '作品详情' }}
                </el-tag>
                <el-tag v-if="selectedSubmission.help_requested" type="warning">该学生当前有求助</el-tag>
              </div>
              <div class="muted">{{ selectedSubmission.student_name }} · {{ selectedSubmission.student_username }}</div>
            </div>

            <div class="detail-item" style="display: grid; gap: 10px;">
              <strong>{{ selectedSubmission.title }}</strong>
              <div>{{ selectedSubmission.content }}</div>
            </div>

            <div v-if="selectedSubmission.help_messages.length > 0" class="detail-list">
              <div class="section-kicker">Related Help</div>
              <div
                v-for="message in selectedSubmission.help_messages"
                :key="message.id"
                class="detail-item"
                style="display: grid; gap: 6px;"
              >
                <div class="inline-actions" style="justify-content: flex-start;">
                  <el-tag :type="message.status === 'open' ? 'warning' : 'info'">{{ message.status }}</el-tag>
                  <span class="muted">{{ message.created_at }}</span>
                </div>
                <div>{{ message.message }}</div>
              </div>
            </div>

            <el-form label-position="top">
              <el-form-item label="批改结论">
                <el-select v-model="reviewForm.decision" class="full-width">
                  <el-option v-for="option in reviewDecisionOptions" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
              </el-form-item>

              <el-form-item label="反馈内容">
                <el-input
                  v-model="reviewForm.feedback"
                  type="textarea"
                  :rows="7"
                  maxlength="2000"
                  show-word-limit
                  placeholder="输入要发给学生的反馈内容"
                />
              </el-form-item>

              <el-form-item>
                <el-checkbox v-model="reviewForm.resolve_help_requests">发布反馈后自动关闭该学生的课堂求助</el-checkbox>
              </el-form-item>

              <div class="inline-actions">
                <el-button type="primary" plain :loading="generatingFeedbackDraft" :disabled="selectedSubmission.status === 'draft'" @click="generateFeedbackDraft">
                  生成反馈草稿
                </el-button>
                <el-button type="primary" :loading="reviewing" :disabled="selectedSubmission.status === 'draft'" @click="submitReview">
                  发布批改结果
                </el-button>
              </div>
            </el-form>

            <div class="page-grid page-grid--two">
              <div class="detail-list">
                <div class="section-kicker">History</div>
                <div
                  v-for="entry in selectedSubmission.history"
                  :key="`${entry.entry_type}-${entry.id}`"
                  class="detail-item"
                  style="display: grid; gap: 8px;"
                >
                  <div class="inline-actions" style="justify-content: flex-start;">
                    <el-tag :type="entry.entry_type === 'reviewed' ? reviewTagType(entry.decision) : entry.entry_type === 'submitted' ? 'success' : 'info'">
                      {{ historyEntryLabel(entry) }}
                    </el-tag>
                    <span class="muted">{{ entry.actor_name }}</span>
                  </div>
                  <div>{{ entry.summary }}</div>
                  <div class="muted">{{ entry.occurred_at }}</div>
                </div>
              </div>

              <div class="detail-list">
                <div class="section-kicker">Review Log</div>
                <div v-if="selectedSubmission.reviews.length > 0">
                  <div
                    v-for="review in selectedSubmission.reviews"
                    :key="review.id"
                    class="detail-item"
                    style="display: grid; gap: 8px;"
                  >
                    <div class="inline-actions" style="justify-content: flex-start;">
                      <el-tag :type="reviewTagType(review.decision)">{{ reviewDecisionLabelMap[review.decision] }}</el-tag>
                      <span class="muted">{{ review.reviewer_name }} · {{ review.created_at }}</span>
                    </div>
                    <div>{{ review.feedback }}</div>
                  </div>
                </div>
                <div v-else class="empty-state">这份作品还没有批改记录。</div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            先从左侧选择一份作品，右侧会展示全文、求助信息、提交历史和批改表单。
          </div>
        </div>
      </section>

      <section class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Teacher AI Copilot</div>
        <h2 class="section-heading">教师 AI 副驾</h2>
        <p class="muted">所有 AI 输出都处于草稿态，需要教师审阅、编辑、确认后再进入正式流程。</p>
        <div class="page-grid page-grid--two" style="margin-top: 18px;">
          <div class="stack">
            <el-input
              v-model="draftGoal"
              type="textarea"
              :rows="5"
              placeholder="描述你希望 AI 生成的课堂建议或教学草稿"
            />
            <el-button type="primary" :loading="generating" @click="generateDraft">
              生成 AI 课堂草稿
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

      <MigrationAdminPanel v-if="isAdminSession" />
    </div>

    <el-skeleton v-else :rows="8" animated />
  </PortalLayout>
</template>
