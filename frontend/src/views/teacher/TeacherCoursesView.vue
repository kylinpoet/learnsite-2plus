<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiClient, buildApiUrl } from '../../api/client'
import type {
  CourseActivitySummary,
  TeacherCourseActivitySavePayload,
  TeacherCourseCollectionResponse,
  TeacherCourseDetailResponse,
  TeacherCourseSavePayload,
} from '../../api/types'
import RichTextEditor from '../../components/editor/RichTextEditor.vue'

const route = useRoute()
const router = useRouter()

const collection = ref<TeacherCourseCollectionResponse | null>(null)
const detail = ref<TeacherCourseDetailResponse | null>(null)
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const publishing = ref(false)
const unpublishing = ref(false)
const uploadingActivityId = ref<number | null>(null)
const selectedFiles = reactive<Record<string, File | null>>({})

const selectedCourseId = computed(() => {
  if (typeof route.params.courseId === 'string') {
    return Number(route.params.courseId)
  }
  return collection.value?.selected_course?.course.id ?? null
})

const courseForm = reactive<TeacherCourseSavePayload>({
  course_id: null,
  title: '',
  stage_label: '',
  overview: '',
  assignment_title: '',
  assignment_prompt: '',
  activities: [],
  publish_now: false,
})

function normalizeActivity(activity?: Partial<CourseActivitySummary>): TeacherCourseActivitySavePayload {
  return {
    id: activity?.id ?? null,
    title: activity?.title ?? '',
    activity_type: activity?.activity_type ?? 'rich_text',
    summary: activity?.summary ?? '',
    instructions_html: activity?.instructions_html ?? '<p></p>',
  }
}

function syncFormFromDetail() {
  const selected = detail.value
  if (!selected) {
    courseForm.course_id = null
    courseForm.title = ''
    courseForm.stage_label = ''
    courseForm.overview = ''
    courseForm.assignment_title = ''
    courseForm.assignment_prompt = ''
    courseForm.publish_now = false
    courseForm.activities = []
    return
  }

  courseForm.course_id = selected.course.id
  courseForm.title = selected.course.title
  courseForm.stage_label = selected.course.stage_label
  courseForm.overview = selected.course.overview ?? ''
  courseForm.assignment_title = selected.course.assignment_title
  courseForm.assignment_prompt = selected.course.assignment_prompt
  courseForm.publish_now = selected.course.is_published
  courseForm.activities = selected.activities.map((activity) => normalizeActivity(activity))
}

function createNewCourse() {
  detail.value = null
  syncFormFromDetail()
  courseForm.activities = [normalizeActivity()]
  void router.push('/teacher/courses')
}

async function loadCourseDetail(courseId: number | null) {
  if (!courseId) {
    detail.value = collection.value?.selected_course ?? null
    syncFormFromDetail()
    return
  }

  const response = await apiClient.get<TeacherCourseDetailResponse>(`/teacher/courses/${courseId}`)
  detail.value = response.data
  syncFormFromDetail()
}

async function loadCourses() {
  loading.value = true
  try {
    const response = await apiClient.get<TeacherCourseCollectionResponse>('/teacher/courses')
    collection.value = response.data
    await loadCourseDetail(selectedCourseId.value)
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载课程发布模块。'
  } finally {
    loading.value = false
  }
}

function selectCourse(courseId: number) {
  void router.push(`/teacher/courses/${courseId}`)
}

function addActivity(type: TeacherCourseActivitySavePayload['activity_type']) {
  courseForm.activities = [
    ...(courseForm.activities ?? []),
    normalizeActivity({
      activity_type: type,
      summary: type === 'interactive_page' ? '上传交互网页后，学生可以直接运行任务并提交 JSON 数据。' : '',
    }),
  ]
}

function moveActivity(index: number, offset: number) {
  const activities = [...(courseForm.activities ?? [])]
  const nextIndex = index + offset
  if (nextIndex < 0 || nextIndex >= activities.length) {
    return
  }
  const [item] = activities.splice(index, 1)
  activities.splice(nextIndex, 0, item)
  courseForm.activities = activities
}

function removeActivity(index: number) {
  const activities = [...(courseForm.activities ?? [])]
  activities.splice(index, 1)
  courseForm.activities = activities
}

async function saveCourse(publishNow: boolean) {
  if (!courseForm.title.trim() || !courseForm.stage_label.trim() || !courseForm.assignment_title.trim() || !courseForm.assignment_prompt.trim()) {
    ElMessage.warning('请先填写课程标题、阶段和书面作业信息')
    return
  }
  if ((courseForm.activities ?? []).length === 0) {
    ElMessage.warning('至少需要保留一个课程活动')
    return
  }

  const loadingRef = publishNow ? publishing : saving
  loadingRef.value = true
  try {
    const payload: TeacherCourseSavePayload = {
      ...courseForm,
      publish_now: publishNow,
      overview: courseForm.overview?.trim() || null,
      activities: (courseForm.activities ?? []).map((activity) => ({
        id: activity.id ?? null,
        title: activity.title.trim(),
        activity_type: activity.activity_type,
        summary: activity.summary?.trim() || null,
        instructions_html: activity.instructions_html || '<p></p>',
      })),
    }

    const response = await apiClient.post('/teacher/courses', payload)
    const nextId = response.data.id as number | undefined
    ElMessage.success(publishNow ? '课程已保存并发布' : '课程草稿已保存')
    await loadCourses()
    if (nextId) {
      await router.push(`/teacher/courses/${nextId}`)
    }
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('课程保存失败')
  } finally {
    loadingRef.value = false
  }
}

async function togglePublish() {
  if (!detail.value) {
    return
  }

  const targetId = detail.value.course.id
  try {
    if (detail.value.course.is_published) {
      unpublishing.value = true
      await apiClient.post(`/teacher/courses/${targetId}/unpublish`)
      ElMessage.success('课程已撤回发布')
    } else {
      publishing.value = true
      await apiClient.post(`/teacher/courses/${targetId}/publish`)
      ElMessage.success('课程已发布')
    }
    await loadCourses()
    await router.push(`/teacher/courses/${targetId}`)
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('课程发布状态更新失败')
  } finally {
    publishing.value = false
    unpublishing.value = false
  }
}

function rememberFile(event: Event, activityKey: string) {
  const input = event.target as HTMLInputElement
  selectedFiles[activityKey] = input.files?.[0] ?? null
}

async function uploadInteractivePackage(activityIndex: number) {
  const activity = courseForm.activities?.[activityIndex]
  if (!activity?.id) {
    ElMessage.warning('请先保存课程，让活动获得编号后再上传交互网页')
    return
  }
  const fileKey = String(activity.id)
  const file = selectedFiles[fileKey]
  if (!file) {
    ElMessage.warning('请先选择一个 HTML 或 ZIP 文件')
    return
  }

  uploadingActivityId.value = activity.id
  try {
    const formData = new FormData()
    formData.append('upload', file)
    await apiClient.post(`/teacher/activities/${activity.id}/interactive-upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success('交互网页活动已上传')
    await loadCourses()
    if (selectedCourseId.value) {
      await router.push(`/teacher/courses/${selectedCourseId.value}`)
    }
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('交互网页上传失败')
  } finally {
    uploadingActivityId.value = null
  }
}

function detailActivityById(activityId: number | null | undefined) {
  return detail.value?.activities.find((activity) => activity.id === activityId) ?? null
}

function interactiveLink(activityId: number | null | undefined) {
  const target = detailActivityById(activityId)
  if (!target?.interactive_launch_url) {
    return ''
  }
  return buildApiUrl(target.interactive_launch_url.replace(/^\/api/, ''))
}

watch(selectedCourseId, (courseId) => {
  if (collection.value) {
    void loadCourseDetail(courseId)
  }
})

onMounted(() => {
  void loadCourses()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="10" animated />

  <div v-else class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="inline-actions" style="justify-content: space-between; margin-bottom: 18px;">
          <div>
            <div class="section-kicker">Course Library</div>
            <h2 class="section-heading">课程列表</h2>
          </div>
          <el-button type="primary" plain @click="createNewCourse">新建课程</el-button>
        </div>

        <div v-if="collection?.courses.length" class="detail-list">
          <div
            v-for="course in collection.courses"
            :key="course.id"
            class="detail-item"
            style="display: grid; gap: 8px; cursor: pointer;"
            :style="selectedCourseId === course.id ? 'outline: 2px solid var(--accent);' : ''"
            @click="selectCourse(course.id)"
          >
            <div class="inline-actions" style="justify-content: space-between;">
              <div class="list-row__main">
                <strong>{{ course.title }}</strong>
                <span class="muted">{{ course.stage_label }}</span>
              </div>
              <el-tag :type="course.is_published ? 'success' : 'info'">
                {{ course.is_published ? '已发布' : '草稿' }}
              </el-tag>
            </div>
            <div class="muted">活动数 {{ course.activity_count ?? 0 }} · 书面作业 {{ course.assignment_title }}</div>
          </div>
        </div>
        <div v-else class="empty-state">当前还没有课程。</div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Course Settings</div>
        <h2 class="section-heading">课程主信息</h2>
        <el-form label-position="top">
          <el-form-item label="课程标题">
            <el-input v-model="courseForm.title" placeholder="例如：信息卡片网页设计" />
          </el-form-item>
          <div class="page-grid page-grid--two">
            <el-form-item label="阶段标签">
              <el-input v-model="courseForm.stage_label" placeholder="例如：第 2 课 · 结构设计" />
            </el-form-item>
            <el-form-item label="书面作业标题">
              <el-input v-model="courseForm.assignment_title" placeholder="例如：课堂成果提交" />
            </el-form-item>
          </div>
          <el-form-item label="课程概览">
            <el-input v-model="courseForm.overview" type="textarea" :rows="4" maxlength="2000" show-word-limit />
          </el-form-item>
          <el-form-item label="书面作业要求">
            <el-input v-model="courseForm.assignment_prompt" type="textarea" :rows="5" maxlength="5000" show-word-limit />
          </el-form-item>
          <div class="inline-actions">
            <el-button type="primary" plain :loading="saving" @click="saveCourse(false)">保存课程草稿</el-button>
            <el-button type="primary" :loading="publishing" @click="saveCourse(true)">保存并发布</el-button>
            <el-button
              v-if="detail"
              plain
              :loading="unpublishing"
              @click="togglePublish"
            >
              {{ detail.course.is_published ? '撤回发布' : '直接发布当前课程' }}
            </el-button>
          </div>
        </el-form>
      </div>
    </section>

    <section class="surface-card" style="padding: 24px;">
      <div class="inline-actions" style="justify-content: space-between; margin-bottom: 18px;">
        <div>
          <div class="section-kicker">Course Activities</div>
          <h2 class="section-heading">课程活动</h2>
          <p class="muted">活动支持富文本说明、顺序调整，以及交互网页任务上传。</p>
        </div>
        <div class="inline-actions">
          <el-button plain @click="addActivity('rich_text')">新增富文本活动</el-button>
          <el-button type="primary" plain @click="addActivity('interactive_page')">新增交互网页活动</el-button>
        </div>
      </div>

      <div v-if="courseForm.activities?.length" class="detail-list">
        <div
          v-for="(activity, index) in courseForm.activities"
          :key="`${activity.id ?? 'new'}-${index}`"
          class="detail-item"
          style="display: grid; gap: 16px;"
        >
          <div class="inline-actions" style="justify-content: space-between;">
            <div class="inline-actions" style="justify-content: flex-start;">
              <div class="status-pill">活动 {{ index + 1 }}</div>
              <el-tag :type="activity.activity_type === 'interactive_page' ? 'warning' : 'success'">
                {{ activity.activity_type === 'interactive_page' ? '交互网页' : '富文本活动' }}
              </el-tag>
            </div>
            <div class="inline-actions">
              <el-button size="small" plain :disabled="index === 0" @click="moveActivity(index, -1)">上移</el-button>
              <el-button size="small" plain :disabled="index === (courseForm.activities?.length ?? 1) - 1" @click="moveActivity(index, 1)">下移</el-button>
              <el-button size="small" type="danger" plain @click="removeActivity(index)">移除</el-button>
            </div>
          </div>

          <div class="page-grid page-grid--two">
            <el-form-item label="活动标题">
              <el-input v-model="activity.title" />
            </el-form-item>
            <el-form-item label="活动摘要">
              <el-input v-model="activity.summary" maxlength="255" />
            </el-form-item>
          </div>

          <div>
            <div class="section-kicker">活动内容</div>
            <RichTextEditor v-model="activity.instructions_html" />
          </div>

          <div
            v-if="activity.activity_type === 'interactive_page'"
            class="surface-card"
            style="padding: 18px; border-radius: 20px; box-shadow: none;"
          >
            <div class="section-kicker">Interactive Upload</div>
            <div class="page-grid page-grid--two">
              <div class="stack">
                <input type="file" accept=".html,.htm,.zip" @change="rememberFile($event, String(activity.id ?? index))" />
                <el-button
                  type="primary"
                  plain
                  :disabled="!activity.id"
                  :loading="uploadingActivityId === activity.id"
                  @click="uploadInteractivePackage(index)"
                >
                  上传交互网页
                </el-button>
                <div class="muted" v-if="!activity.id">先保存课程，活动获得编号后才能上传交互网页。</div>
              </div>

              <div class="stack">
                <div class="detail-item">
                  <div>预览链接</div>
                  <strong class="mono">{{ detailActivityById(activity.id)?.interactive_launch_url || '保存并上传后生成' }}</strong>
                </div>
                <div class="detail-item">
                  <div>JSON 提交接口</div>
                  <strong class="mono">{{ detailActivityById(activity.id)?.interactive_submission_api_url || '保存后自动生成' }}</strong>
                </div>
                <a
                  v-if="interactiveLink(activity.id)"
                  :href="interactiveLink(activity.id)"
                  target="_blank"
                  rel="noreferrer"
                >
                  <el-button plain>新窗口预览交互活动</el-button>
                </a>
              </div>
            </div>

            <div v-if="detailActivityById(activity.id)?.recent_submissions.length" class="detail-list" style="margin-top: 16px;">
              <div class="section-kicker">Recent Submissions</div>
              <div
                v-for="submission in detailActivityById(activity.id)?.recent_submissions"
                :key="submission.id"
                class="detail-item"
                style="display: grid; gap: 8px;"
              >
                <strong>{{ submission.submitted_by_name }} · {{ submission.submitted_at }}</strong>
                <div class="muted">{{ submission.payload_preview }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">先新增至少一个活动，课程才算完整。</div>
    </section>
  </div>
</template>
