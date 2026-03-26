<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiClient } from '../../api/client'
import type {
  CreateDraftResponse,
  ReviewDecision,
  SubmissionQueueItem,
  SubmissionReviewPayload,
  TeacherSubmissionDetail,
  TeacherSubmissionsResponse,
} from '../../api/types'

const route = useRoute()
const detail = ref<TeacherSubmissionDetail | null>(null)
const overview = ref<TeacherSubmissionsResponse | null>(null)
const loading = ref(true)
const error = ref('')
const reviewing = ref(false)
const generating = ref(false)

const submissionId = computed(() => Number(route.params.submissionId))

const reviewForm = reactive<SubmissionReviewPayload>({
  decision: 'revision_requested',
  feedback: '',
  resolve_help_requests: true,
})

const reviewDecisionOptions: Array<{ value: ReviewDecision; label: string }> = [
  { value: 'approved', label: '通过' },
  { value: 'revision_requested', label: '修改后重交' },
  { value: 'rejected', label: '暂不通过' },
]

const queueItem = computed<SubmissionQueueItem | null>(() => {
  if (!overview.value) {
    return null
  }
  return overview.value.submissions.find((item) => item.id === submissionId.value) ?? null
})

function syncReviewForm() {
  if (!detail.value) {
    return
  }
  reviewForm.decision = detail.value.review_decision ?? 'revision_requested'
  reviewForm.feedback = detail.value.teacher_feedback ?? ''
  reviewForm.resolve_help_requests = true
}

async function loadDetail() {
  loading.value = true
  try {
    const [detailResponse, overviewResponse] = await Promise.all([
      apiClient.get<TeacherSubmissionDetail>(`/teacher/submissions/${submissionId.value}`),
      apiClient.get<TeacherSubmissionsResponse>('/teacher/submissions'),
    ])
    detail.value = detailResponse.data
    overview.value = overviewResponse.data
    syncReviewForm()
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载批改详情。'
  } finally {
    loading.value = false
  }
}

async function generateFeedbackDraft() {
  generating.value = true
  try {
    const response = await apiClient.post<CreateDraftResponse>(`/teacher/submissions/${submissionId.value}/feedback-draft`)
    reviewForm.feedback = response.data.draft.content
    ElMessage.success('已生成反馈草稿')
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('反馈草稿生成失败')
  } finally {
    generating.value = false
  }
}

async function submitReview() {
  reviewing.value = true
  try {
    await apiClient.post(`/teacher/submissions/${submissionId.value}/review`, reviewForm)
    ElMessage.success('批改结果已发布')
    await loadDetail()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('批改发布失败')
  } finally {
    reviewing.value = false
  }
}

watch(submissionId, () => {
  void loadDetail()
})

onMounted(() => {
  void loadDetail()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="10" animated />

  <div v-else-if="detail" class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Submission</div>
        <h2 class="section-heading">{{ detail.title }}</h2>
        <div class="inline-actions" style="justify-content: flex-start; margin-bottom: 12px;">
          <el-tag :type="queueItem?.status === 'submitted' ? 'success' : queueItem?.status === 'reviewed' ? 'warning' : 'info'">
            {{ queueItem?.status ?? detail.status }}
          </el-tag>
          <el-tag v-if="detail.help_requested" type="warning">该学生当前有求助</el-tag>
        </div>
        <div class="detail-item" style="display: block;">
          <div>{{ detail.content }}</div>
        </div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Review Workspace</div>
        <h2 class="section-heading">批改工作位</h2>
        <el-form label-position="top">
          <el-form-item label="批改结论">
            <el-select v-model="reviewForm.decision" class="full-width">
              <el-option v-for="option in reviewDecisionOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="反馈内容">
            <el-input v-model="reviewForm.feedback" type="textarea" :rows="9" maxlength="2000" show-word-limit />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="reviewForm.resolve_help_requests">发布反馈后自动关闭求助</el-checkbox>
          </el-form-item>
          <div class="inline-actions">
            <el-button type="primary" plain :loading="generating" :disabled="detail.status === 'draft'" @click="generateFeedbackDraft">
              生成反馈草稿
            </el-button>
            <el-button type="primary" :loading="reviewing" :disabled="detail.status === 'draft'" @click="submitReview">
              发布批改结果
            </el-button>
          </div>
        </el-form>
      </div>
    </section>

    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Help Messages</div>
        <h2 class="section-heading">关联求助</h2>
        <div v-if="detail.help_messages.length > 0" class="detail-list">
          <div v-for="message in detail.help_messages" :key="message.id" class="detail-item" style="display: grid; gap: 8px;">
            <strong>{{ message.created_at }}</strong>
            <div>{{ message.message }}</div>
          </div>
        </div>
        <div v-else class="empty-state">该作品当前没有关联求助。</div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">History</div>
        <h2 class="section-heading">提交与批改历史</h2>
        <div v-if="detail.history.length > 0" class="detail-list">
          <div v-for="entry in detail.history" :key="`${entry.entry_type}-${entry.id}`" class="detail-item" style="display: grid; gap: 8px;">
            <strong>{{ entry.summary }}</strong>
            <div class="muted">{{ entry.actor_name }} · {{ entry.occurred_at }}</div>
          </div>
        </div>
        <div v-else class="empty-state">当前没有历史记录。</div>
      </div>
    </section>
  </div>
</template>
