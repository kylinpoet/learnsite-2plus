<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { apiClient } from '../../api/client'
import type {
  MessageResponse,
  StudentAssignmentsResponse,
  SubmissionActionResponse,
  SubmissionUpsertPayload,
} from '../../api/types'

const data = ref<StudentAssignmentsResponse | null>(null)
const loading = ref(true)
const error = ref('')
const savingDraft = ref(false)
const submitting = ref(false)
const requestingHelp = ref(false)

const submissionForm = reactive<SubmissionUpsertPayload>({
  title: '',
  content: '',
})

function syncForm() {
  if (!data.value) {
    return
  }
  submissionForm.title = data.value.submission.title
  submissionForm.content = data.value.submission.content
}

async function loadWorkbench() {
  loading.value = true
  try {
    const response = await apiClient.get<StudentAssignmentsResponse>('/student/assignments')
    data.value = response.data
    syncForm()
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载书面提交工作台。'
  } finally {
    loading.value = false
  }
}

async function persistSubmission(mode: 'draft' | 'submit') {
  if (!submissionForm.title.trim() || !submissionForm.content.trim()) {
    ElMessage.warning('请先填写标题和内容')
    return
  }

  const loadingRef = mode === 'draft' ? savingDraft : submitting
  loadingRef.value = true
  try {
    const endpoint = mode === 'draft' ? '/student/submission/draft' : '/student/submission/submit'
    await apiClient.post<SubmissionActionResponse>(endpoint, submissionForm)
    ElMessage.success(mode === 'draft' ? '草稿已保存' : '作品已正式提交')
    await loadWorkbench()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error(mode === 'draft' ? '草稿保存失败' : '正式提交失败')
  } finally {
    loadingRef.value = false
  }
}

async function askForHelp() {
  requestingHelp.value = true
  try {
    await apiClient.post<MessageResponse>('/student/help-requests', {
      message: '老师，我需要帮助完善当前书面提交内容。',
    })
    ElMessage.success('已向教师端发送求助')
    await loadWorkbench()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('求助发送失败')
  } finally {
    requestingHelp.value = false
  }
}

onMounted(() => {
  void loadWorkbench()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="8" animated />

  <div v-else-if="data" class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Written Submission</div>
        <h2 class="section-heading">{{ data.assignment_title }}</h2>
        <p class="muted" style="margin-bottom: 18px;">{{ data.assignment_prompt }}</p>

        <el-form label-position="top">
          <el-form-item label="作品标题">
            <el-input v-model="submissionForm.title" maxlength="128" :disabled="!data.submission.can_edit" />
          </el-form-item>

          <el-form-item label="作品内容">
            <el-input
              v-model="submissionForm.content"
              type="textarea"
              :rows="12"
              maxlength="5000"
              show-word-limit
              :disabled="!data.submission.can_edit"
            />
          </el-form-item>

          <div class="inline-actions">
            <el-button type="primary" plain :loading="savingDraft" :disabled="!data.submission.can_edit" @click="persistSubmission('draft')">
              保存草稿
            </el-button>
            <el-button type="primary" :loading="submitting" :disabled="!data.submission.can_edit" @click="persistSubmission('submit')">
              正式提交
            </el-button>
            <el-button plain :loading="requestingHelp" @click="askForHelp">举手求助</el-button>
          </div>
        </el-form>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Status</div>
        <h2 class="section-heading">提交状态</h2>
        <div class="detail-list">
          <div class="detail-item">
            <div>当前状态</div>
            <strong>{{ data.submission.status }}</strong>
          </div>
          <div class="detail-item">
            <div>当前版本</div>
            <strong>v{{ data.submission.version }}</strong>
          </div>
          <div class="detail-item">
            <div>教师反馈</div>
            <strong>{{ data.submission.teacher_feedback || '暂无反馈' }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Submission History</div>
      <h2 class="section-heading">提交历史</h2>
      <el-timeline v-if="data.submission_history.length > 0">
        <el-timeline-item
          v-for="entry in data.submission_history"
          :key="`${entry.entry_type}-${entry.id}`"
          :timestamp="entry.occurred_at"
          placement="top"
        >
          <div class="detail-item" style="display: grid; gap: 8px;">
            <strong>{{ entry.summary }}</strong>
            <div class="muted">{{ entry.actor_name }}</div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <div v-else class="empty-state">还没有书面提交历史。</div>
    </section>
  </div>
</template>
