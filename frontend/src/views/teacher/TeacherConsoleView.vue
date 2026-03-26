<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { apiClient, buildApiUrl, downloadApiFile } from '../../api/client'
import type {
  AttendanceRecordSummary,
  AttendanceStatus,
  ResourceAudience,
  ReviewDecision,
  StartSessionPayload,
  SubmissionQueueItem,
  TeacherCourseSavePayload,
  TeacherResourceSummary,
  TeacherResourceStatusPayload,
  TeacherCourseSummary,
  SubmissionReviewPayload,
  TeacherConsoleResponse,
  TeacherDraft,
  TeacherDraftUpdatePayload,
  TeacherReflectionSummary,
  TeacherReflectionDraftResponse,
  TeacherReflectionPayload,
  TeacherStudentRosterEntry,
  TeacherSubmissionDetail,
} from '../../api/types'
import GovernanceOpsPanel from '../../components/admin/GovernanceOpsPanel.vue'
import MigrationAdminPanel from '../../components/admin/MigrationAdminPanel.vue'
import SchoolIdentityPanel from '../../components/admin/SchoolIdentityPanel.vue'
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
const generatingReflectionDraft = ref(false)
const savingReflection = ref(false)
const savingLesson = ref(false)
const savingDraftId = ref<number | null>(null)
const acceptingDraftId = ref<number | null>(null)
const rejectingDraftId = ref<number | null>(null)
const publishingLessonId = ref<number | null>(null)
const unpublishingLessonId = ref<number | null>(null)
const uploadingResource = ref(false)
const togglingResourceId = ref<number | null>(null)
const draftGoal = ref('为当前学案生成 3 条分层课堂活动建议')
const reviewForm = reactive<SubmissionReviewPayload>({
  decision: 'revision_requested',
  feedback: '',
  resolve_help_requests: true,
})
const lessonForm = reactive<TeacherCourseSavePayload>({
  course_id: null,
  title: '',
  stage_label: '',
  overview: '',
  assignment_title: '',
  assignment_prompt: '',
  publish_now: false,
})
const reflectionForm = reactive<TeacherReflectionPayload>({
  strengths: '',
  risks: '',
  next_actions: '',
  student_support_plan: '',
})
const selectedLaunchKey = ref('')
const selectedLessonId = ref<number | null>(null)
const selectedResourceFile = ref<File | null>(null)
const resourceFileInput = ref<HTMLInputElement | null>(null)
const studentRosterQuery = ref('')
const studentRosterFilter = ref<'all' | 'attention' | 'help' | 'submitted' | 'missing'>('all')
const teacherResourceQuery = ref('')
const teacherResourceAudienceFilter = ref<'any' | ResourceAudience>('any')
const teacherResourceStatusFilter = ref<'all' | 'active' | 'inactive'>('all')
const teacherResourceCategoryFilter = ref<'any' | number>('any')
const resourceForm = reactive<{
  title: string
  description: string
  audience: ResourceAudience
  category_id: number | null
  classroom_id: number | null
}>({
  title: '',
  description: '',
  audience: 'student',
  category_id: null,
  classroom_id: null,
})
const draftEditors = reactive<Record<number, TeacherDraftUpdatePayload>>({})
let radarAbortController: AbortController | null = null
let radarReconnectTimer: ReturnType<typeof window.setTimeout> | undefined

const isAdminSession = computed(
  () => sessionState.value?.role === 'school_admin' || sessionState.value?.role === 'platform_admin',
)

const navItems = computed(() => [{ label: '课堂控制台', to: '/teacher/console' }])
const hasActiveSession = computed(
  () => Boolean(consoleData.value?.session_id) && consoleData.value?.session_status !== 'idle',
)
const mustChooseResourceClassroom = computed(() => !isAdminSession.value)

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

const analyticsHighlights = computed(() => consoleData.value?.analytics.highlights ?? [])
const attentionStudents = computed(() => consoleData.value?.analytics.attention_students ?? [])
const lessonPlans = computed(() => consoleData.value?.lesson_plans ?? [])
const managedClassrooms = computed(() => consoleData.value?.managed_classrooms ?? [])
const resourceItems = computed(() => consoleData.value?.resources ?? [])
const resourceCategories = computed(() => consoleData.value?.resource_categories ?? [])
const activeResourceCategories = computed(() => resourceCategories.value.filter((category) => category.active))
const filteredResourceItems = computed(() => {
  const keyword = teacherResourceQuery.value.trim().toLowerCase()
  return resourceItems.value.filter((resource) => {
    const matchesKeyword =
      !keyword ||
      resource.title.toLowerCase().includes(keyword) ||
      resource.original_filename.toLowerCase().includes(keyword) ||
      (resource.description ?? '').toLowerCase().includes(keyword) ||
      (resource.classroom_name ?? '').toLowerCase().includes(keyword) ||
      resource.uploaded_by_name.toLowerCase().includes(keyword)

    if (!matchesKeyword) {
      return false
    }

    if (teacherResourceAudienceFilter.value !== 'any' && resource.audience !== teacherResourceAudienceFilter.value) {
      return false
    }

    if (teacherResourceCategoryFilter.value !== 'any' && resource.category_id !== teacherResourceCategoryFilter.value) {
      return false
    }

    if (teacherResourceStatusFilter.value === 'active') {
      return resource.active
    }
    if (teacherResourceStatusFilter.value === 'inactive') {
      return !resource.active
    }

    return true
  })
})
const studentRosterItems = computed(() => consoleData.value?.student_roster ?? [])
const filteredStudentRoster = computed(() => {
  const keyword = studentRosterQuery.value.trim().toLowerCase()
  return studentRosterItems.value.filter((item) => {
    const matchesKeyword =
      !keyword ||
      item.student_name.toLowerCase().includes(keyword) ||
      item.student_username.toLowerCase().includes(keyword) ||
      item.classroom_name.toLowerCase().includes(keyword)

    if (!matchesKeyword) {
      return false
    }

    if (studentRosterFilter.value === 'attention') {
      return Boolean(item.attention_reason)
    }
    if (studentRosterFilter.value === 'help') {
      return item.help_requested
    }
    if (studentRosterFilter.value === 'submitted') {
      return item.submission_status === 'submitted'
    }
    if (studentRosterFilter.value === 'missing') {
      return !item.submission_status || item.submission_status === 'draft'
    }
    return true
  })
})
const selectedLessonSummary = computed<TeacherCourseSummary | null>(() => {
  if (!selectedLessonId.value) {
    return null
  }
  return lessonPlans.value.find((lesson) => lesson.id === selectedLessonId.value) ?? null
})

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

const studentRosterFilters: Array<{ value: 'all' | 'attention' | 'help' | 'submitted' | 'missing'; label: string }> = [
  { value: 'all', label: 'All Students' },
  { value: 'attention', label: 'Needs Attention' },
  { value: 'help', label: 'Help Queue' },
  { value: 'submitted', label: 'Pending Review' },
  { value: 'missing', label: 'Incomplete' },
]

const teacherResourceAudienceFilters: Array<{ value: 'any' | ResourceAudience; label: string }> = [
  { value: 'any', label: 'All Audiences' },
  { value: 'student', label: 'Student' },
  { value: 'teacher', label: 'Teacher' },
  { value: 'all', label: 'Teacher + Student' },
]

const teacherResourceStatusFilters: Array<{ value: 'all' | 'active' | 'inactive'; label: string }> = [
  { value: 'all', label: 'All Statuses' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]

const reviewDecisionLabelMap: Record<ReviewDecision, string> = {
  approved: '已通过',
  revision_requested: '需要修改后重交',
  rejected: '暂不通过',
}

const resourceAudienceLabelMap: Record<ResourceAudience, string> = {
  student: '学生可见',
  teacher: '教师可见',
  all: '师生可见',
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

function resourceAudienceTagType(audience: ResourceAudience) {
  if (audience === 'student') {
    return 'success'
  }
  if (audience === 'teacher') {
    return 'warning'
  }
  return 'primary'
}

function resourceCategoryLabel(resource: TeacherResourceSummary) {
  if (resource.category_name?.trim()) {
    return resource.category_name
  }
  if (resource.category_id) {
    return resourceCategories.value.find((category) => category.id === resource.category_id)?.name ?? '未分类'
  }
  return '未分类'
}

function studentRosterPresenceTagType(entry: TeacherStudentRosterEntry) {
  if (entry.help_requested) {
    return 'warning'
  }
  if (entry.presence_status === 'active') {
    return 'success'
  }
  if (entry.presence_status === 'idle') {
    return 'warning'
  }
  if (entry.presence_status === 'offline') {
    return 'danger'
  }
  return 'info'
}

function studentRosterSubmissionTagType(entry: TeacherStudentRosterEntry) {
  if (entry.submission_status === 'reviewed') {
    return reviewTagType(entry.review_decision)
  }
  if (entry.submission_status === 'submitted') {
    return 'success'
  }
  return 'info'
}

function studentRosterSubmissionLabel(entry: TeacherStudentRosterEntry) {
  if (entry.submission_status === 'reviewed' && entry.review_decision) {
    return reviewDecisionLabelMap[entry.review_decision]
  }
  if (entry.submission_status === 'submitted') {
    return '寰呮壒鏀?'
  }
  if (entry.submission_status === 'draft') {
    return '鑽夌涓?'
  }
  return '鏈紑濮?'
}

function resetResourceForm() {
  resourceForm.title = ''
  resourceForm.description = ''
  resourceForm.audience = 'student'
  resourceForm.category_id = activeResourceCategories.value[0]?.id ?? null
  resourceForm.classroom_id = mustChooseResourceClassroom.value ? (managedClassrooms.value[0]?.id ?? null) : null
  selectedResourceFile.value = null
  if (resourceFileInput.value) {
    resourceFileInput.value.value = ''
  }
}

function syncResourceCategory() {
  if (!activeResourceCategories.value.length) {
    resourceForm.category_id = null
    return
  }
  const exists = activeResourceCategories.value.some((category) => category.id === resourceForm.category_id)
  if (!exists) {
    resourceForm.category_id = activeResourceCategories.value[0].id
  }
  if (
    teacherResourceCategoryFilter.value !== 'any' &&
    !resourceCategories.value.some((category) => category.id === teacherResourceCategoryFilter.value)
  ) {
    teacherResourceCategoryFilter.value = 'any'
  }
}

function syncResourceClassroom() {
  if (!managedClassrooms.value.length) {
    resourceForm.classroom_id = null
    return
  }
  if (mustChooseResourceClassroom.value) {
    const exists = managedClassrooms.value.some((classroom) => classroom.id === resourceForm.classroom_id)
    if (!exists) {
      resourceForm.classroom_id = managedClassrooms.value[0].id
    }
  } else if (
    resourceForm.classroom_id !== null &&
    !managedClassrooms.value.some((classroom) => classroom.id === resourceForm.classroom_id)
  ) {
    resourceForm.classroom_id = null
  }
}

function captureResourceFile(event: Event) {
  const target = event.target as HTMLInputElement
  selectedResourceFile.value = target.files?.[0] ?? null
}

async function downloadTeacherResource(resource: TeacherResourceSummary) {
  try {
    await downloadApiFile(`/teacher/resources/${resource.id}/download`, resource.original_filename)
  } catch (requestError) {
    ElMessage.error('资源下载失败')
    console.error(requestError)
  }
}

function openStudentSubmission(entry: TeacherStudentRosterEntry) {
  if (!entry.submission_id) {
    return
  }
  void loadSubmissionDetail(entry.submission_id)
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

function resetLessonForm() {
  lessonForm.course_id = null
  lessonForm.title = ''
  lessonForm.stage_label = ''
  lessonForm.overview = ''
  lessonForm.assignment_title = ''
  lessonForm.assignment_prompt = ''
  lessonForm.publish_now = false
}

function startNewLesson() {
  selectedLessonId.value = null
  resetLessonForm()
}

function fillLessonForm(lesson: TeacherCourseSummary) {
  lessonForm.course_id = lesson.id
  lessonForm.title = lesson.title
  lessonForm.stage_label = lesson.stage_label
  lessonForm.overview = lesson.overview ?? ''
  lessonForm.assignment_title = lesson.assignment_title
  lessonForm.assignment_prompt = lesson.assignment_prompt
  lessonForm.publish_now = lesson.is_published
}

function syncReflectionForm() {
  reflectionForm.strengths = consoleData.value?.reflection.strengths ?? ''
  reflectionForm.risks = consoleData.value?.reflection.risks ?? ''
  reflectionForm.next_actions = consoleData.value?.reflection.next_actions ?? ''
  reflectionForm.student_support_plan = consoleData.value?.reflection.student_support_plan ?? ''
}

function syncDraftEditors() {
  const activeIds = new Set((consoleData.value?.ai_drafts ?? []).map((draft) => draft.id))
  for (const key of Object.keys(draftEditors)) {
    const numericId = Number(key)
    if (!activeIds.has(numericId)) {
      delete draftEditors[numericId]
    }
  }

  for (const draft of consoleData.value?.ai_drafts ?? []) {
    if (!draftEditors[draft.id]) {
      draftEditors[draft.id] = {
        title: draft.title,
        content: draft.content,
      }
    } else if (draft.status !== 'draft') {
      draftEditors[draft.id].title = draft.title
      draftEditors[draft.id].content = draft.content
    }
  }
}

function applyDraftUpdate(draft: TeacherDraft) {
  if (!consoleData.value) {
    return
  }
  const existingIndex = consoleData.value.ai_drafts.findIndex((item) => item.id === draft.id)
  if (existingIndex === -1) {
    consoleData.value.ai_drafts.unshift(draft)
  } else {
    consoleData.value.ai_drafts.splice(existingIndex, 1, draft)
  }
  draftEditors[draft.id] = {
    title: draft.title,
    content: draft.content,
  }
}

function draftStatusTagType(status: TeacherDraft['status']) {
  if (status === 'accepted') {
    return 'success'
  }
  if (status === 'rejected') {
    return 'danger'
  }
  return 'info'
}

function draftStatusLabel(status: TeacherDraft['status']) {
  if (status === 'accepted') {
    return '已采纳'
  }
  if (status === 'rejected') {
    return '已驳回'
  }
  return '草稿待审'
}

function syncSelectedLesson(preferredId?: number) {
  if (!lessonPlans.value.length) {
    selectedLessonId.value = null
    resetLessonForm()
    return
  }

  const nextId =
    preferredId ??
    (selectedLessonId.value && lessonPlans.value.some((lesson) => lesson.id === selectedLessonId.value)
      ? selectedLessonId.value
      : lessonPlans.value[0].id)
  selectedLessonId.value = nextId
  const target = lessonPlans.value.find((lesson) => lesson.id === nextId)
  if (target) {
    fillLessonForm(target)
  }
}

async function loadConsole() {
  try {
    const { data } = await apiClient.get<TeacherConsoleResponse>('/teacher/console')
    consoleData.value = data
    loadError.value = ''
    syncReflectionForm()
    syncDraftEditors()
    syncResourceCategory()
    syncResourceClassroom()
    syncSelectedLesson()
    syncLaunchSelection()
    await syncSelectedSubmission()
  } catch (requestError) {
    loadError.value = '教师控制台加载失败，请确认后端服务已经启动。'
    console.error(requestError)
  }
}

function selectLesson(lesson: TeacherCourseSummary) {
  selectedLessonId.value = lesson.id
  fillLessonForm(lesson)
}

async function saveLesson(publishNow: boolean) {
  if (!lessonForm.title.trim() || !lessonForm.stage_label.trim() || !lessonForm.assignment_title.trim() || !lessonForm.assignment_prompt.trim()) {
    ElMessage.warning('请先填写学案标题、阶段、任务标题和任务说明')
    return
  }

  savingLesson.value = true
  try {
    const payload: TeacherCourseSavePayload = {
      ...lessonForm,
      publish_now: publishNow,
    }
    const { data } = await apiClient.post<TeacherCourseSummary>('/teacher/courses', payload)
    await loadConsole()
    syncSelectedLesson(data.id)
    ElMessage.success(publishNow ? '学案已保存并发布' : '学案草稿已保存')
  } catch (requestError) {
    ElMessage.error('保存学案失败')
    console.error(requestError)
  } finally {
    savingLesson.value = false
  }
}

async function changeLessonPublish(lesson: TeacherCourseSummary, publish: boolean) {
  if (!lesson.id) {
    return
  }

  if (publish) {
    publishingLessonId.value = lesson.id
  } else {
    unpublishingLessonId.value = lesson.id
  }
  try {
    const path = publish ? `/teacher/courses/${lesson.id}/publish` : `/teacher/courses/${lesson.id}/unpublish`
    const { data } = await apiClient.post<TeacherCourseSummary>(path)
    await loadConsole()
    syncSelectedLesson(data.id)
    ElMessage.success(publish ? '学案已发布' : '学案已撤回发布')
  } catch (requestError) {
    ElMessage.error(publish ? '发布学案失败' : '撤回发布失败')
    console.error(requestError)
  } finally {
    publishingLessonId.value = null
    unpublishingLessonId.value = null
  }
}

async function uploadResource() {
  if (!selectedResourceFile.value) {
    ElMessage.warning('请先选择要上传的资源文件')
    return
  }
  if (!resourceForm.title.trim()) {
    ElMessage.warning('请先填写资源标题')
    return
  }
  if (!resourceForm.category_id) {
    ElMessage.warning('请先选择资源分类')
    return
  }
  if (mustChooseResourceClassroom.value && !resourceForm.classroom_id) {
    ElMessage.warning('请先选择资源所属班级')
    return
  }

  const formData = new FormData()
  formData.append('title', resourceForm.title.trim())
  formData.append('audience', resourceForm.audience)
  formData.append('category_id', String(resourceForm.category_id))
  formData.append('description', resourceForm.description.trim())
  if (resourceForm.classroom_id !== null) {
    formData.append('classroom_id', String(resourceForm.classroom_id))
  }
  formData.append('upload', selectedResourceFile.value)

  uploadingResource.value = true
  try {
    await apiClient.post('/teacher/resources', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    await loadConsole()
    resetResourceForm()
    ElMessage.success('资源已上传到资源中心')
  } catch (requestError) {
    ElMessage.error('资源上传失败')
    console.error(requestError)
  } finally {
    uploadingResource.value = false
  }
}

async function toggleResourceStatus(resource: TeacherResourceSummary, active: boolean) {
  const payload: TeacherResourceStatusPayload = { active }
  togglingResourceId.value = resource.id
  try {
    await apiClient.post(`/teacher/resources/${resource.id}/status`, payload)
    await loadConsole()
    ElMessage.success(active ? '资源已重新启用' : '资源已停用')
  } catch (requestError) {
    ElMessage.error(active ? '启用资源失败' : '停用资源失败')
    console.error(requestError)
  } finally {
    togglingResourceId.value = null
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

function stopRadar() {
  if (radarReconnectTimer) {
    window.clearTimeout(radarReconnectTimer)
    radarReconnectTimer = undefined
  }
  radarAbortController?.abort()
  radarAbortController = null
}

async function connectRadar() {
  const token = sessionState.value?.token
  if (!token || !consoleData.value?.session_id || consoleData.value.session_status === 'idle') {
    stopRadar()
    return
  }

  stopRadar()
  const controller = new AbortController()
  radarAbortController = controller

  try {
    const response = await fetch(buildApiUrl('/teacher/radar/stream'), {
      headers: {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      },
      signal: controller.signal,
    })

    if (!response.ok || !response.body) {
      throw new Error(`Radar stream request failed: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (!controller.signal.aborted) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      let boundaryIndex = buffer.indexOf('\n\n')
      while (boundaryIndex !== -1) {
        const chunk = buffer.slice(0, boundaryIndex)
        buffer = buffer.slice(boundaryIndex + 2)

        for (const line of chunk.split(/\r?\n/)) {
          if (!line.startsWith('data:')) {
            continue
          }
          if (!consoleData.value) {
            continue
          }
          consoleData.value.radar = JSON.parse(line.slice(5).trim()) as TeacherConsoleResponse['radar']
          radarWarning.value = ''
        }

        boundaryIndex = buffer.indexOf('\n\n')
      }
    }
  } catch (requestError) {
    if (controller.signal.aborted) {
      return
    }
    radarWarning.value = '课堂实时雷达连接中断，请稍后重试。'
    console.error(requestError)
  }

  if (!controller.signal.aborted && consoleData.value?.session_status !== 'idle') {
    radarReconnectTimer = window.setTimeout(() => {
      void connectRadar()
    }, 1500)
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
    syncReflectionForm()
    syncDraftEditors()
    syncResourceCategory()
    syncResourceClassroom()
    syncLaunchSelection()
    await syncSelectedSubmission()
    void connectRadar()
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
  if (!hasActiveSession.value) {
    ElMessage.warning('请先开始一节新课，再生成课堂 AI 草稿')
    return
  }
  if (!draftGoal.value.trim()) {
    ElMessage.warning('请先描述你希望 AI 生成什么样的课堂建议')
    return
  }
  generating.value = true
  try {
    const { data } = await apiClient.post<{ draft: TeacherDraft }>('/teacher/ai/drafts', {
      goal: draftGoal.value,
    })
    applyDraftUpdate(data.draft)
    ElMessage.success('AI 课堂建议草稿已生成')
  } catch (requestError) {
    ElMessage.error('AI 草稿生成失败')
    console.error(requestError)
  } finally {
    generating.value = false
  }
}

async function generateReflectionDraft() {
  if (!hasActiveSession.value) {
    ElMessage.warning('请先开始一节新课，再生成教学反思草稿')
    return
  }
  generatingReflectionDraft.value = true
  try {
    const { data } = await apiClient.post<TeacherReflectionDraftResponse>('/teacher/reflection/draft')
    applyDraftUpdate(data.draft)
    if (consoleData.value) {
      consoleData.value.reflection = data.reflection
    }
    syncReflectionForm()
    ElMessage.success('教学反思草稿已生成，并已填入右侧表单')
  } catch (requestError) {
    ElMessage.error('教学反思草稿生成失败')
    console.error(requestError)
  } finally {
    generatingReflectionDraft.value = false
  }
}

async function saveReflection() {
  if (!hasActiveSession.value) {
    ElMessage.warning('请先开始一节新课，再保存教学反思')
    return
  }
  savingReflection.value = true
  try {
    const currentDraft = consoleData.value?.reflection.ai_draft_content ?? null
    const { data } = await apiClient.post<TeacherReflectionSummary>('/teacher/reflection', reflectionForm)
    if (!data.ai_draft_content) {
      data.ai_draft_content = currentDraft
    }
    if (consoleData.value) {
      consoleData.value.reflection = data
    }
    syncReflectionForm()
    ElMessage.success('教学反思已保存')
  } catch (requestError) {
    ElMessage.error('保存教学反思失败')
    console.error(requestError)
  } finally {
    savingReflection.value = false
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
    applyDraftUpdate(data.draft)
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

async function saveDraftEdit(draft: TeacherDraft) {
  const editor = draftEditors[draft.id]
  if (!editor?.title.trim() || !editor.content.trim()) {
    ElMessage.warning('请先填写完整的 AI 草稿标题和内容')
    return
  }

  savingDraftId.value = draft.id
  try {
    const { data } = await apiClient.post<TeacherDraft>(`/teacher/ai/drafts/${draft.id}/save`, {
      title: editor.title.trim(),
      content: editor.content.trim(),
    })
    applyDraftUpdate(data)
    ElMessage.success('AI 草稿编辑已保存')
  } catch (requestError) {
    ElMessage.error('保存 AI 草稿失败')
    console.error(requestError)
  } finally {
    savingDraftId.value = null
  }
}

async function acceptDraft(draft: TeacherDraft) {
  const editor = draftEditors[draft.id]
  if (!editor?.title.trim() || !editor.content.trim()) {
    ElMessage.warning('请先填写完整的 AI 草稿标题和内容')
    return
  }

  acceptingDraftId.value = draft.id
  try {
    const { data } = await apiClient.post<TeacherDraft>(`/teacher/ai/drafts/${draft.id}/accept`, {
      title: editor.title.trim(),
      content: editor.content.trim(),
    })
    applyDraftUpdate(data)
    ElMessage.success('AI 草稿已采纳')
  } catch (requestError) {
    ElMessage.error('采纳 AI 草稿失败')
    console.error(requestError)
  } finally {
    acceptingDraftId.value = null
  }
}

async function rejectDraft(draft: TeacherDraft) {
  rejectingDraftId.value = draft.id
  try {
    const { data } = await apiClient.post<TeacherDraft>(`/teacher/ai/drafts/${draft.id}/reject`)
    applyDraftUpdate(data)
    ElMessage.success('AI 草稿已驳回')
  } catch (requestError) {
    ElMessage.error('驳回 AI 草稿失败')
    console.error(requestError)
  } finally {
    rejectingDraftId.value = null
  }
}

onMounted(async () => {
  await loadConsole()
  void connectRadar()
})

onBeforeUnmount(() => {
  stopRadar()
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
          <div class="section-kicker">Lesson Library</div>
          <h2 class="section-heading">学案备课 / 发布</h2>
          <p class="muted" style="margin-bottom: 16px;">先在这里整理课堂目标和任务说明，发布后的学案才会出现在开课选项里。</p>
          <div class="inline-actions" style="margin-bottom: 16px;">
            <el-button plain @click="startNewLesson">新建空白学案</el-button>
          </div>
          <div class="detail-list">
            <div
              v-for="lesson in lessonPlans"
              :key="lesson.id"
              class="detail-item"
              style="display: grid; gap: 8px; cursor: pointer;"
              :style="selectedLessonId === lesson.id ? 'outline: 2px solid var(--accent-strong);' : ''"
              @click="selectLesson(lesson)"
            >
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-tag :type="lesson.is_published ? 'success' : 'info'">{{ lesson.is_published ? '已发布' : '草稿' }}</el-tag>
                <strong>{{ lesson.title }}</strong>
              </div>
              <div class="muted">{{ lesson.stage_label }} · {{ lesson.assignment_title }}</div>
              <div v-if="lesson.overview" class="muted">{{ lesson.overview }}</div>
              <div v-if="lesson.published_at" class="mono muted">发布于 {{ lesson.published_at }}</div>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Lesson Editor</div>
          <h2 class="section-heading">{{ selectedLessonSummary ? '编辑当前学案' : '创建新学案' }}</h2>
          <el-form label-position="top">
            <el-form-item label="学案标题">
              <el-input v-model="lessonForm.title" placeholder="例如：人工智能技术基础" />
            </el-form-item>
            <el-form-item label="阶段 / 节次">
              <el-input v-model="lessonForm.stage_label" placeholder="例如：第 4 课 · 数据图表结论表达" />
            </el-form-item>
            <el-form-item label="学案概述">
              <el-input
                v-model="lessonForm.overview"
                type="textarea"
                :rows="3"
                maxlength="2000"
                show-word-limit
                placeholder="说明这节课的目标、任务结构和课堂推进重点"
              />
            </el-form-item>
            <el-form-item label="任务标题">
              <el-input v-model="lessonForm.assignment_title" placeholder="例如：课堂图表作品提交" />
            </el-form-item>
            <el-form-item label="任务说明">
              <el-input
                v-model="lessonForm.assignment_prompt"
                type="textarea"
                :rows="5"
                maxlength="5000"
                show-word-limit
                placeholder="告诉学生这节课要完成什么、提交什么、重点关注什么"
              />
            </el-form-item>
            <div class="inline-actions">
              <el-button type="primary" plain :loading="savingLesson" @click="saveLesson(false)">
                保存草稿
              </el-button>
              <el-button type="primary" :loading="savingLesson" @click="saveLesson(true)">
                保存并发布
              </el-button>
              <el-button
                v-if="selectedLessonSummary?.is_published"
                type="warning"
                plain
                :loading="unpublishingLessonId === selectedLessonSummary.id"
                @click="changeLessonPublish(selectedLessonSummary, false)"
              >
                撤回发布
              </el-button>
              <el-button
                v-else-if="selectedLessonSummary"
                type="success"
                plain
                :loading="publishingLessonId === selectedLessonSummary.id"
                @click="changeLessonPublish(selectedLessonSummary, true)"
              >
                单独发布
              </el-button>
            </div>
          </el-form>
        </div>
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
            <el-alert
              v-if="launchOptions.length === 0"
              type="warning"
              :closable="false"
              title="当前账号还没有分配可开课班级，或学校里还没有已发布学案。"
              style="margin-bottom: 12px;"
            />
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

      <section class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Student Roster</div>
        <h2 class="section-heading">瀛︾敓鑺卞悕鍐?</h2>
        <p class="muted" style="margin-bottom: 16px;">
          {{ consoleData.student_roster_scope }}
          <span v-if="consoleData.student_roster_live"> · Live attendance, heartbeat, help, and submission signals are included.</span>
          <span v-else> · When no class is active, this roster stays in directory mode.</span>
        </p>

        <div class="page-grid page-grid--two" style="margin-bottom: 16px;">
          <el-input
            v-model="studentRosterQuery"
            clearable
            placeholder="鎼滅储瀛︾敓濮撳悕銆佸鍙锋垨鐝骇"
          />
          <el-select v-model="studentRosterFilter" class="full-width">
            <el-option
              v-for="filter in studentRosterFilters"
              :key="filter.value"
              :label="filter.label"
              :value="filter.value"
            />
          </el-select>
        </div>

        <el-alert
          v-if="!consoleData.student_roster_live"
          type="info"
          :closable="false"
          title="褰撳墠鏄┖鎬佽姳鍚嶅唽锛屽紑璇惧悗浼氳嚜鍔ㄦ洿鏂版瘡鍚嶅鐢熺殑璇惧爞鐜板満鐘舵€併€?"
          style="margin-bottom: 16px;"
        />

        <div v-if="filteredStudentRoster.length > 0" class="detail-list">
          <div
            v-for="student in filteredStudentRoster"
            :key="student.student_id"
            class="detail-item"
            style="display: grid; gap: 10px;"
          >
            <div class="inline-actions" style="justify-content: space-between; gap: 12px;">
              <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
                <el-tag>{{ student.classroom_name }}</el-tag>
                <el-tag v-if="student.attendance_status" :type="student.attendance_status === 'present' ? 'success' : student.attendance_status === 'late' ? 'warning' : student.attendance_status === 'absent' ? 'danger' : 'info'">
                  {{ student.attendance_status }}
                </el-tag>
                <el-tag v-if="student.presence_status" :type="studentRosterPresenceTagType(student)">
                  {{ student.presence_status }}
                </el-tag>
                <el-tag v-if="student.help_requested" type="warning">Help</el-tag>
                <el-tag :type="studentRosterSubmissionTagType(student)">
                  {{ studentRosterSubmissionLabel(student) }}
                </el-tag>
                <strong>{{ student.student_name }} 路 {{ student.student_username }}</strong>
              </div>

              <el-button
                size="small"
                plain
                :disabled="!student.submission_id"
                @click="openStudentSubmission(student)"
              >
                鏌ョ湅浣滃搧
              </el-button>
            </div>

            <div class="muted">
              浠诲姟杩涘害 {{ student.progress_percent }}%
              <span v-if="student.last_seen_at"> 路 鏈€杩戝績璺?{{ student.last_seen_at }}</span>
            </div>

            <div v-if="student.attention_reason">{{ student.attention_reason }}</div>
          </div>
        </div>
        <div v-else class="empty-state">
          褰撳墠绛涢€夋潯浠朵笅娌℃湁鍖归厤鐨勫鐢熻褰曘€?
        </div>
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Class Analytics</div>
          <h2 class="section-heading">班级数据分析</h2>
          <p class="muted" style="margin-bottom: 18px;">把签到、进度、作品和批改状态压成一张课堂画像，帮助教师判断这节课下一步该盯哪里。</p>

          <section class="metric-grid" style="margin-bottom: 18px;">
            <MetricCard label="出勤率" :value="`${consoleData.analytics.attendance_rate}%`" hint="签到完成度（到课 + 迟到）" :primary="true" />
            <MetricCard label="平均进度" :value="`${consoleData.analytics.average_progress}%`" hint="按学生心跳上报的任务进度计算" />
            <MetricCard label="提交率" :value="`${consoleData.analytics.submission_rate}%`" hint="已提交或已批改的作品占比" />
            <MetricCard label="反馈覆盖率" :value="`${consoleData.analytics.reviewed_rate}%`" hint="已提交作品中完成反馈的比例" />
          </section>

          <div class="page-grid page-grid--two">
            <div class="detail-list">
              <div class="section-kicker">Highlights</div>
              <div v-for="line in analyticsHighlights" :key="line" class="detail-item">
                <div>{{ line }}</div>
              </div>
            </div>

            <div class="detail-list">
              <div class="section-kicker">Attention Queue</div>
              <div v-if="attentionStudents.length > 0">
                <div
                  v-for="student in attentionStudents"
                  :key="student.student_username"
                  class="detail-item"
                  style="display: grid; gap: 8px;"
                >
                  <div class="inline-actions" style="justify-content: flex-start;">
                    <el-tag type="warning">{{ student.presence_status }}</el-tag>
                    <strong>{{ student.student_name }} · {{ student.student_username }}</strong>
                  </div>
                  <div class="muted">当前进度 {{ student.progress_percent }}%</div>
                  <div>{{ student.reason }}</div>
                </div>
              </div>
              <div v-else class="empty-state">当前课堂没有额外的高优先级关注学生。</div>
            </div>
          </div>

          <div class="detail-list" style="margin-top: 18px;">
            <div class="section-kicker">Distribution</div>
            <div class="detail-item">
              <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
                <el-tag type="success">签到 {{ consoleData.analytics.present_count }}</el-tag>
                <el-tag>迟到 {{ consoleData.analytics.late_count }}</el-tag>
                <el-tag type="danger">缺席 {{ consoleData.analytics.absent_count }}</el-tag>
                <el-tag type="info">待确认 {{ consoleData.analytics.pending_count }}</el-tag>
                <el-tag>草稿 {{ consoleData.analytics.draft_count }}</el-tag>
                <el-tag type="success">待批改 {{ consoleData.analytics.submitted_count }}</el-tag>
                <el-tag type="warning">已批改 {{ consoleData.analytics.reviewed_count }}</el-tag>
                <el-tag type="success">通过 {{ consoleData.analytics.approved_count }}</el-tag>
                <el-tag type="warning">重交 {{ consoleData.analytics.revision_requested_count }}</el-tag>
                <el-tag type="danger">不通过 {{ consoleData.analytics.rejected_count }}</el-tag>
              </div>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Teaching Reflection</div>
          <h2 class="section-heading">教学反思</h2>
          <p class="muted" style="margin-bottom: 18px;">
            把课堂亮点、风险、下一步动作和学生支持计划沉淀下来。
            <span v-if="consoleData.reflection.updated_at"> 最近保存于 {{ consoleData.reflection.updated_at }}</span>
          </p>
          <el-alert
            v-if="!hasActiveSession"
            type="info"
            :closable="false"
            title="开始一节新课后，才能生成和保存本课次的教学反思。"
            style="margin-bottom: 16px;"
          />

          <el-form label-position="top">
            <el-form-item label="课堂亮点">
              <el-input
                v-model="reflectionForm.strengths"
                type="textarea"
                :rows="4"
                maxlength="2000"
                show-word-limit
                placeholder="记录这节课推进顺利、学生参与度高或教学设计有效的部分"
              />
            </el-form-item>

            <el-form-item label="课堂风险 / 问题">
              <el-input
                v-model="reflectionForm.risks"
                type="textarea"
                :rows="4"
                maxlength="2000"
                show-word-limit
                placeholder="记录本节课中卡住的步骤、学生普遍问题或课堂风险"
              />
            </el-form-item>

            <el-form-item label="下一步动作">
              <el-input
                v-model="reflectionForm.next_actions"
                type="textarea"
                :rows="4"
                maxlength="2000"
                show-word-limit
                placeholder="写下下一节课前、中、后的具体调整动作"
              />
            </el-form-item>

            <el-form-item label="学生支持计划">
              <el-input
                v-model="reflectionForm.student_support_plan"
                type="textarea"
                :rows="4"
                maxlength="2000"
                show-word-limit
                placeholder="记录需要重点支持的学生、跟进方式和同伴示范安排"
              />
            </el-form-item>

            <div class="inline-actions">
              <el-button type="primary" plain :loading="generatingReflectionDraft" :disabled="!hasActiveSession" @click="generateReflectionDraft">
                生成反思草稿
              </el-button>
              <el-button type="primary" :loading="savingReflection" :disabled="!hasActiveSession" @click="saveReflection">
                保存教学反思
              </el-button>
            </div>
          </el-form>

          <div v-if="consoleData.reflection.ai_draft_content" class="detail-list" style="margin-top: 18px;">
            <div class="section-kicker">Latest Draft</div>
            <div class="detail-item">
              <div class="muted">{{ consoleData.reflection.ai_draft_content }}</div>
            </div>
          </div>
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
        <el-alert
          v-if="!hasActiveSession"
          type="info"
          :closable="false"
          title="先开始一节新课，AI 才会基于当前课堂上下文生成草稿。"
          style="margin-top: 16px;"
        />
        <div class="page-grid page-grid--two" style="margin-top: 18px;">
          <div class="stack">
            <el-input
              v-model="draftGoal"
              type="textarea"
              :rows="5"
              placeholder="描述你希望 AI 生成的课堂建议或教学草稿"
            />
            <el-button type="primary" :loading="generating" :disabled="!hasActiveSession" @click="generateDraft">
              生成 AI 课堂草稿
            </el-button>
          </div>

          <div class="stack">
            <div v-if="consoleData.ai_drafts.length === 0" class="empty-state">
              当前课堂还没有 AI 草稿。你可以生成课堂建议、批改反馈或教学反思草稿。
            </div>
            <template v-else>
              <div
                v-for="draft in consoleData.ai_drafts"
                :key="draft.id"
                class="detail-item"
                style="display: grid; gap: 12px;"
              >
                <div class="inline-actions" style="justify-content: flex-start;">
                  <div class="status-pill">{{ draft.draft_type }}</div>
                  <el-tag :type="draftStatusTagType(draft.status)">{{ draftStatusLabel(draft.status) }}</el-tag>
                </div>
                <el-input
                  v-model="draftEditors[draft.id].title"
                  :disabled="draft.status !== 'draft'"
                  placeholder="AI 草稿标题"
                />
                <el-input
                  v-model="draftEditors[draft.id].content"
                  type="textarea"
                  :rows="5"
                  :disabled="draft.status !== 'draft'"
                  placeholder="AI 草稿内容"
                />
                <div class="inline-actions" style="justify-content: flex-start;">
                  <el-button
                    plain
                    :disabled="draft.status !== 'draft'"
                    :loading="savingDraftId === draft.id"
                    @click="saveDraftEdit(draft)"
                  >
                    保存编辑
                  </el-button>
                  <el-button
                    type="primary"
                    :disabled="draft.status !== 'draft'"
                    :loading="acceptingDraftId === draft.id"
                    @click="acceptDraft(draft)"
                  >
                    采纳草稿
                  </el-button>
                  <el-button
                    type="danger"
                    plain
                    :disabled="draft.status !== 'draft'"
                    :loading="rejectingDraftId === draft.id"
                    @click="rejectDraft(draft)"
                  >
                    驳回草稿
                  </el-button>
                </div>
                <div class="mono muted">
                  创建于 {{ draft.created_at }}
                  <template v-if="draft.updated_at"> · 最近更新 {{ draft.updated_at }}</template>
                </div>
              </div>
            </template>
          </div>
        </div>
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Resource Center</div>
          <h2 class="section-heading">资源中心</h2>
          <p class="muted" style="margin-bottom: 16px;">
            先上传课堂模板、课前阅读或教师备课资料，学生端会按学校与班级自动筛选展示。
          </p>
          <el-alert
            v-if="activeResourceCategories.length === 0"
            type="warning"
            :closable="false"
            title="当前学校还没有启用中的资源分类，请先在管理员治理面板里启用至少一个资源分类。"
            style="margin-bottom: 16px;"
          />

          <el-form label-position="top">
            <el-form-item label="资源标题">
              <el-input v-model="resourceForm.title" placeholder="例如：数据采集观察模板" />
            </el-form-item>
            <div class="page-grid page-grid--two">
              <el-form-item label="可见范围">
                <el-select v-model="resourceForm.audience" class="full-width">
                  <el-option label="学生可见" value="student" />
                  <el-option label="教师可见" value="teacher" />
                  <el-option label="师生可见" value="all" />
                </el-select>
              </el-form-item>
              <el-form-item label="资源分类">
                <el-select
                  v-model="resourceForm.category_id"
                  class="full-width"
                  placeholder="请选择资源分类"
                  :disabled="activeResourceCategories.length === 0"
                >
                  <el-option
                    v-for="category in activeResourceCategories"
                    :key="category.id"
                    :label="category.name"
                    :value="category.id"
                  />
                </el-select>
              </el-form-item>
            </div>
            <el-form-item label="所属班级">
              <el-select
                v-model="resourceForm.classroom_id"
                class="full-width"
                :placeholder="mustChooseResourceClassroom ? '请选择班级' : '可留空表示学校共享'"
                clearable
              >
                <el-option
                  v-for="classroom in managedClassrooms"
                  :key="classroom.id"
                  :label="`${classroom.grade_label} · ${classroom.name}`"
                  :value="classroom.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="资源说明">
              <el-input
                v-model="resourceForm.description"
                type="textarea"
                :rows="3"
                maxlength="1000"
                show-word-limit
                placeholder="简单说明资源用途、适用场景或建议使用方式"
              />
            </el-form-item>
            <el-form-item label="上传文件">
              <input ref="resourceFileInput" type="file" @change="captureResourceFile" />
            </el-form-item>
            <div class="muted" v-if="selectedResourceFile" style="margin-bottom: 12px;">
              已选择：{{ selectedResourceFile.name }}
            </div>
            <div class="inline-actions">
              <el-button plain @click="resetResourceForm">清空表单</el-button>
              <el-button
                type="primary"
                :loading="uploadingResource"
                :disabled="activeResourceCategories.length === 0"
                @click="uploadResource"
              >
                上传资源
              </el-button>
            </div>
          </el-form>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Resource Library</div>
          <h2 class="section-heading">已上传资源</h2>
          <div class="page-grid page-grid--two" style="margin-bottom: 16px;">
            <el-input
              v-model="teacherResourceQuery"
              clearable
              placeholder="搜索资源标题、文件名、班级或上传者"
            />
            <div class="page-grid page-grid--two">
              <el-select v-model="teacherResourceAudienceFilter" class="full-width">
                <el-option
                  v-for="filter in teacherResourceAudienceFilters"
                  :key="filter.value"
                  :label="filter.label"
                  :value="filter.value"
                />
              </el-select>
              <el-select v-model="teacherResourceCategoryFilter" class="full-width">
                <el-option label="全部分类" value="any" />
                <el-option
                  v-for="category in resourceCategories"
                  :key="category.id"
                  :label="`${category.name}${category.active ? '' : '（已停用）'}`"
                  :value="category.id"
                />
              </el-select>
              <el-select v-model="teacherResourceStatusFilter" class="full-width">
                <el-option
                  v-for="filter in teacherResourceStatusFilters"
                  :key="filter.value"
                  :label="filter.label"
                  :value="filter.value"
                />
              </el-select>
            </div>
          </div>

          <div v-if="filteredResourceItems.length > 0" class="detail-list">
            <div
              v-for="resource in filteredResourceItems"
              :key="resource.id"
              class="detail-item"
              style="display: grid; gap: 10px;"
            >
              <div class="inline-actions" style="justify-content: space-between;">
                <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
                  <el-tag :type="resourceAudienceTagType(resource.audience)">
                    {{ resourceAudienceLabelMap[resource.audience] }}
                  </el-tag>
                  <el-tag type="warning">{{ resourceCategoryLabel(resource) }}</el-tag>
                  <el-tag :type="resource.active ? 'success' : 'info'">
                    {{ resource.active ? '启用中' : '已停用' }}
                  </el-tag>
                  <strong>{{ resource.title }}</strong>
                </div>
                <span class="muted">{{ resource.original_filename }}</span>
              </div>
              <div class="muted">
                {{ resource.classroom_name ? `班级：${resource.classroom_name}` : '学校共享资源' }} · {{ resource.file_size_label }} ·
                上传者 {{ resource.uploaded_by_name }} · {{ resource.uploaded_at }} · Downloads {{ resource.download_count }}
              </div>
              <div v-if="resource.description">{{ resource.description }}</div>
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-button size="small" plain @click="downloadTeacherResource(resource)">下载</el-button>
                <el-button
                  v-if="resource.can_manage"
                  size="small"
                  :type="resource.active ? 'warning' : 'success'"
                  plain
                  :loading="togglingResourceId === resource.id"
                  @click="toggleResourceStatus(resource, !resource.active)"
                >
                  {{ resource.active ? '停用' : '重新启用' }}
                </el-button>
              </div>
            </div>
          </div>
          <div v-else-if="resourceItems.length > 0" class="empty-state">
            当前筛选条件下没有匹配的资源。
          </div>
          <div v-else class="empty-state">
            当前还没有资源，先上传课堂模板、讲义或示例文件。
          </div>
        </div>
      </section>

      <SchoolIdentityPanel v-if="isAdminSession" />
      <GovernanceOpsPanel v-if="isAdminSession" />
      <MigrationAdminPanel v-if="isAdminSession" />
    </div>

    <el-skeleton v-else :rows="8" animated />
  </PortalLayout>
</template>

