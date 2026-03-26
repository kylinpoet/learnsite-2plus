<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiClient, buildApiUrl } from '../../api/client'
import type { ActivitySubmissionResponse, StudentActivityDetailResponse } from '../../api/types'

const route = useRoute()
const data = ref<StudentActivityDetailResponse | null>(null)
const loading = ref(true)
const error = ref('')
const submitting = ref(false)

const activityId = computed(() => Number(route.params.activityId))
const iframeUrl = computed(() => {
  const launchUrl = data.value?.activity.interactive_launch_url
  if (!launchUrl) {
    return ''
  }
  return buildApiUrl(launchUrl.replace(/^\/api/, ''))
})

async function loadActivityDetail() {
  loading.value = true
  try {
    const response = await apiClient.get<StudentActivityDetailResponse>(`/student/activities/${activityId.value}`)
    data.value = response.data
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载活动详情。'
  } finally {
    loading.value = false
  }
}

async function handleActivitySubmit(payload: unknown) {
  submitting.value = true
  try {
    await apiClient.post<ActivitySubmissionResponse>(`/student/activities/${activityId.value}/submissions`, payload)
    ElMessage.success('活动数据已提交到后台')
    await loadActivityDetail()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('活动数据提交失败')
  } finally {
    submitting.value = false
  }
}

function onMessage(event: MessageEvent) {
  const message = event.data as
    | {
        type?: string
        activityId?: number
        payload?: unknown
      }
    | undefined

  if (!message || message.type !== 'learnsite:activity-submit' || message.activityId !== activityId.value) {
    return
  }

  void handleActivitySubmit(message.payload ?? {})
}

watch(activityId, () => {
  void loadActivityDetail()
})

onMounted(() => {
  window.addEventListener('message', onMessage)
  void loadActivityDetail()
})

onBeforeUnmount(() => {
  window.removeEventListener('message', onMessage)
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="8" animated />

  <div v-else-if="data" class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Activity</div>
        <h2 class="section-heading">{{ data.activity.title }}</h2>
        <div class="muted" v-if="data.activity.summary">{{ data.activity.summary }}</div>
        <div class="detail-item" style="display: block; margin-top: 18px;">
          <div v-html="data.activity.instructions_html" />
        </div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Activity Meta</div>
        <h2 class="section-heading">提交与运行信息</h2>
        <div class="detail-list">
          <div class="detail-item">
            <div>活动类型</div>
            <strong>{{ data.activity.activity_type }}</strong>
          </div>
          <div class="detail-item">
            <div>提交地址</div>
            <strong class="mono">{{ data.activity.interactive_submission_api_url || '当前为门户内提交' }}</strong>
          </div>
          <div class="detail-item">
            <div>最近提交</div>
            <strong>{{ data.activity.last_submitted_at || '暂无记录' }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section v-if="data.activity.activity_type === 'interactive_page'" class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Interactive Task</div>
      <h2 class="section-heading">交互网页任务</h2>
      <el-alert
        v-if="!data.activity.has_interactive_asset"
        type="info"
        :closable="false"
        title="教师还没有上传交互网页包，当前只展示活动说明和生成的提交接口。"
      />
      <div v-else class="stack">
        <div class="muted">
          交互网页会在沙箱中运行；如果网页调用 `window.learnsiteSubmit(payload)`，数据会直接进入后台。
        </div>
        <iframe
          :src="iframeUrl"
          title="Interactive activity"
          class="interactive-activity-frame"
          sandbox="allow-scripts allow-forms allow-downloads"
        />
        <el-tag v-if="submitting" type="warning">正在提交活动数据...</el-tag>
      </div>
    </section>

    <section v-if="data.activity.recent_submissions.length > 0" class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Recent Data</div>
      <h2 class="section-heading">我的活动提交</h2>
      <div class="detail-list">
        <div
          v-for="submission in data.activity.recent_submissions"
          :key="submission.id"
          class="detail-item"
          style="display: grid; gap: 8px;"
        >
          <strong>{{ submission.submitted_at }}</strong>
          <div class="muted">{{ submission.payload_preview }}</div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.interactive-activity-frame {
  width: 100%;
  min-height: 620px;
  border: 1px solid var(--line);
  border-radius: 24px;
  background: white;
}
</style>
