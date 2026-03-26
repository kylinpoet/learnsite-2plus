<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { apiClient } from '../../api/client'
import type {
  CreateDraftResponse,
  TeacherCopilotResponse,
  TeacherDraft,
  TeacherDraftUpdatePayload,
  TeacherReflectionDraftResponse,
  TeacherReflectionPayload,
  TeacherReflectionSummary,
} from '../../api/types'

const data = ref<TeacherCopilotResponse | null>(null)
const loading = ref(true)
const error = ref('')
const draftGoal = ref('为当前学案生成 3 条分层课堂活动建议')
const generating = ref(false)
const generatingReflection = ref(false)
const savingReflection = ref(false)
const draftEditors = reactive<Record<number, TeacherDraftUpdatePayload>>({})

const reflectionForm = reactive<TeacherReflectionPayload>({
  strengths: '',
  risks: '',
  next_actions: '',
  student_support_plan: '',
})

function syncReflection(reflection: TeacherReflectionSummary) {
  reflectionForm.strengths = reflection.strengths
  reflectionForm.risks = reflection.risks
  reflectionForm.next_actions = reflection.next_actions
  reflectionForm.student_support_plan = reflection.student_support_plan
}

function syncDraftEditors() {
  for (const draft of data.value?.ai_drafts ?? []) {
    draftEditors[draft.id] = {
      title: draft.title,
      content: draft.content,
    }
  }
}

async function loadCopilot() {
  loading.value = true
  try {
    const response = await apiClient.get<TeacherCopilotResponse>('/teacher/copilot')
    data.value = response.data
    syncReflection(response.data.reflection)
    syncDraftEditors()
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载 AI 副驾模块。'
  } finally {
    loading.value = false
  }
}

async function generateDraft() {
  generating.value = true
  try {
    await apiClient.post<CreateDraftResponse>('/teacher/ai/drafts', { goal: draftGoal.value })
    ElMessage.success('AI 草稿已生成')
    await loadCopilot()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('AI 草稿生成失败')
  } finally {
    generating.value = false
  }
}

async function saveDraftEdit(draft: TeacherDraft) {
  try {
    await apiClient.post(`/teacher/ai/drafts/${draft.id}/save`, draftEditors[draft.id])
    ElMessage.success('草稿编辑已保存')
    await loadCopilot()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('草稿保存失败')
  }
}

async function acceptDraft(draft: TeacherDraft) {
  try {
    await apiClient.post(`/teacher/ai/drafts/${draft.id}/accept`, draftEditors[draft.id])
    ElMessage.success('草稿已采纳')
    await loadCopilot()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('采纳失败')
  }
}

async function rejectDraft(draft: TeacherDraft) {
  try {
    await apiClient.post(`/teacher/ai/drafts/${draft.id}/reject`)
    ElMessage.success('草稿已驳回')
    await loadCopilot()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('驳回失败')
  }
}

async function saveReflection() {
  savingReflection.value = true
  try {
    const response = await apiClient.post<TeacherReflectionSummary>('/teacher/reflection', reflectionForm)
    data.value = data.value
      ? {
          ...data.value,
          reflection: response.data,
        }
      : data.value
    ElMessage.success('教学反思已保存')
    await loadCopilot()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('教学反思保存失败')
  } finally {
    savingReflection.value = false
  }
}

async function generateReflectionDraft() {
  generatingReflection.value = true
  try {
    const response = await apiClient.post<TeacherReflectionDraftResponse>('/teacher/reflection/draft')
    syncReflection(response.data.reflection)
    ElMessage.success('反思草稿已生成')
    await loadCopilot()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('反思草稿生成失败')
  } finally {
    generatingReflection.value = false
  }
}

onMounted(() => {
  void loadCopilot()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="10" animated />

  <div v-else-if="data" class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">AI Drafts</div>
        <h2 class="section-heading">课堂建议与草稿</h2>
        <el-input v-model="draftGoal" type="textarea" :rows="4" placeholder="描述希望 AI 生成的课堂建议" />
        <div class="inline-actions" style="margin-top: 16px;">
          <el-button type="primary" :loading="generating" :disabled="!data.session_id" @click="generateDraft">生成课堂草稿</el-button>
        </div>

        <div v-if="data.ai_drafts.length > 0" class="detail-list" style="margin-top: 18px;">
          <div v-for="draft in data.ai_drafts" :key="draft.id" class="detail-item" style="display: grid; gap: 10px;">
            <div class="inline-actions" style="justify-content: flex-start;">
              <div class="status-pill">{{ draft.draft_type }}</div>
              <el-tag :type="draft.status === 'accepted' ? 'success' : draft.status === 'rejected' ? 'danger' : 'info'">
                {{ draft.status }}
              </el-tag>
            </div>
            <el-input v-model="draftEditors[draft.id].title" :disabled="draft.status !== 'draft'" />
            <el-input v-model="draftEditors[draft.id].content" type="textarea" :rows="6" :disabled="draft.status !== 'draft'" />
            <div class="inline-actions">
              <el-button plain :disabled="draft.status !== 'draft'" @click="saveDraftEdit(draft)">保存编辑</el-button>
              <el-button type="primary" :disabled="draft.status !== 'draft'" @click="acceptDraft(draft)">采纳</el-button>
              <el-button type="danger" plain :disabled="draft.status !== 'draft'" @click="rejectDraft(draft)">驳回</el-button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state" style="margin-top: 18px;">当前还没有 AI 草稿。</div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Reflection</div>
        <h2 class="section-heading">教学反思</h2>
        <el-form label-position="top">
          <el-form-item label="亮点">
            <el-input v-model="reflectionForm.strengths" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="风险">
            <el-input v-model="reflectionForm.risks" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="下一步动作">
            <el-input v-model="reflectionForm.next_actions" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="学生支持计划">
            <el-input v-model="reflectionForm.student_support_plan" type="textarea" :rows="4" />
          </el-form-item>
          <div class="inline-actions">
            <el-button type="primary" plain :loading="generatingReflection" :disabled="!data.session_id" @click="generateReflectionDraft">生成反思草稿</el-button>
            <el-button type="primary" :loading="savingReflection" :disabled="!data.session_id" @click="saveReflection">保存反思</el-button>
          </div>
        </el-form>
      </div>
    </section>
  </div>
</template>
