<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { apiClient, buildApiUrl } from '../../api/client'
import type { TeacherConsoleResponse, TeacherDraft } from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'
import { useSession } from '../../composables/useSession'
import PortalLayout from '../../layouts/PortalLayout.vue'

const { sessionState } = useSession()
const consoleData = ref<TeacherConsoleResponse | null>(null)
const loadError = ref('')
const radarWarning = ref('')
const generating = ref(false)
const draftGoal = ref('为当前学案生成 3 条分层课堂活动建议')
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
    : '实时雷达在左，课堂工作区在中，AI 副驾在右。',
)

async function loadConsole() {
  try {
    const { data } = await apiClient.get<TeacherConsoleResponse>('/teacher/console')
    consoleData.value = data
    loadError.value = ''
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
        <MetricCard label="举手求助" :value="String(consoleData.radar.help_requests)" hint="需快速响应的学生数" />
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Live Radar</div>
          <h2 class="section-heading">{{ consoleData.class_name }} · {{ consoleData.lesson_title }}</h2>
          <div class="radar-grid">
            <div class="radar-card">
              <div class="muted">未签到 / 离线</div>
              <strong>{{ consoleData.radar.absent }}</strong>
              <div class="muted">学生持续超时未上报心跳</div>
            </div>
            <div class="radar-card">
              <div class="muted">长时间停留</div>
              <strong>{{ consoleData.radar.idle }}</strong>
              <div class="muted">需要检查是否卡在步骤中</div>
            </div>
            <div class="radar-card">
              <div class="muted">未进入任务</div>
              <strong>{{ consoleData.radar.not_started }}</strong>
              <div class="muted">尚未开始当前课堂任务</div>
            </div>
            <div class="radar-card">
              <div class="muted">举手求助</div>
              <strong>{{ consoleData.radar.help_requests }}</strong>
              <div class="muted">教师可优先处理的学生请求</div>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Workbench</div>
          <h2 class="section-heading">当前课堂主工作区</h2>
          <div class="list-panel">
            <div v-for="step in consoleData.workbench_steps" :key="step.title" class="list-row">
              <div class="list-row__main">
                <strong>{{ step.title }}</strong>
                <span class="muted">教师仍然保有旧站“上课 / 备课 / 作品 / 签到”链路，但界面更清晰。</span>
              </div>
              <el-tag :type="step.status === 'done' ? 'success' : step.status === 'active' ? 'warning' : 'info'">
                {{ step.status }}
              </el-tag>
            </div>
          </div>
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
