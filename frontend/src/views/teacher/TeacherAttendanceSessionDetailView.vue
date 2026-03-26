<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiClient } from '../../api/client'
import type {
  AttendanceMarkPayload,
  AttendanceRecordSummary,
  MessageResponse,
  TeacherAttendanceResponse,
} from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'

const route = useRoute()
const data = ref<TeacherAttendanceResponse | null>(null)
const loading = ref(true)
const error = ref('')
const updatingId = ref<number | null>(null)

const sessionId = computed(() => Number(route.params.sessionId))

const statusOptions = [
  { label: '到课', value: 'present' },
  { label: '迟到', value: 'late' },
  { label: '缺席', value: 'absent' },
  { label: '请假', value: 'excused' },
]

async function loadSession() {
  loading.value = true
  try {
    const response = await apiClient.get<TeacherAttendanceResponse>(`/teacher/attendance/sessions/${sessionId.value}`)
    data.value = response.data
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载签到明细。'
  } finally {
    loading.value = false
  }
}

async function markAttendance(record: AttendanceRecordSummary, statusValue: string) {
  updatingId.value = record.id
  try {
    const payload: AttendanceMarkPayload = {
      status: statusValue as AttendanceMarkPayload['status'],
      note: record.note ?? '',
    }
    await apiClient.post<MessageResponse>(`/teacher/attendance/${record.id}/mark`, payload)
    ElMessage.success('签到状态已更新')
    await loadSession()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('更新签到失败')
  } finally {
    updatingId.value = null
  }
}

watch(sessionId, () => {
  void loadSession()
})

onMounted(() => {
  void loadSession()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="10" animated />

  <div v-else-if="data" class="stack">
    <section class="metric-grid">
      <MetricCard label="出勤率" :value="`${data.analytics.attendance_rate}%`" hint="本节签到结果" :primary="true" />
      <MetricCard label="迟到人数" :value="String(data.analytics.late_count)" hint="重点关注迟到与未开始学生" />
      <MetricCard label="求助队列" :value="String(data.help_requests.length)" hint="可与签到明细一起处理" />
    </section>

    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Attendance Detail</div>
        <h2 class="section-heading">点名明细</h2>
        <div v-if="data.attendance_records.length > 0" class="detail-list">
          <div
            v-for="record in data.attendance_records"
            :key="record.id"
            class="detail-item"
            style="display: grid; gap: 10px;"
          >
            <div class="inline-actions" style="justify-content: space-between;">
              <div class="list-row__main">
                <strong>{{ record.student_name }} · {{ record.student_username }}</strong>
                <span class="muted">最近活跃 {{ record.last_seen_at || '暂无' }}</span>
              </div>
              <el-tag :type="record.status === 'present' ? 'success' : record.status === 'late' ? 'warning' : 'info'">
                {{ record.status }}
              </el-tag>
            </div>
            <div class="inline-actions">
              <el-button
                v-for="option in statusOptions"
                :key="option.value"
                size="small"
                plain
                :loading="updatingId === record.id && option.value === record.status"
                @click="markAttendance(record, option.value)"
              >
                {{ option.label }}
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">当前会话还没有签到名单。</div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Help Queue</div>
        <h2 class="section-heading">课堂求助</h2>
        <div v-if="data.help_requests.length > 0" class="detail-list">
          <div
            v-for="request in data.help_requests"
            :key="request.id"
            class="detail-item"
            style="display: grid; gap: 6px;"
          >
            <strong>{{ request.student_name }} · {{ request.student_username }}</strong>
            <div>{{ request.message }}</div>
            <div class="muted">{{ request.created_at }}</div>
          </div>
        </div>
        <div v-else class="empty-state">当前没有待处理的课堂求助。</div>
      </div>
    </section>
  </div>
</template>
