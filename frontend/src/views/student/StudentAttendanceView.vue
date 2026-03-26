<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
import { apiClient } from '../../api/client'
import type { MessageResponse, StudentAttendanceResponse } from '../../api/types'

const data = ref<StudentAttendanceResponse | null>(null)
const loading = ref(true)
const error = ref('')
const checkingIn = ref(false)

async function loadAttendance() {
  loading.value = true
  try {
    const response = await apiClient.get<StudentAttendanceResponse>('/student/attendance')
    data.value = response.data
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载签到信息。'
  } finally {
    loading.value = false
  }
}

async function checkIn() {
  checkingIn.value = true
  try {
    await apiClient.post<MessageResponse>('/student/attendance/check-in')
    ElMessage.success('签到成功')
    await loadAttendance()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('签到失败')
  } finally {
    checkingIn.value = false
  }
}

onMounted(() => {
  void loadAttendance()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="8" animated />

  <div v-else-if="data" class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card surface-card--accent" style="padding: 24px;">
        <div class="hero-task">
          <div class="section-kicker">Attendance</div>
          <h2 class="hero-task__title">{{ data.lesson_title }}</h2>
          <p class="muted">签到页只保留当前状态和历史，不再和作业编辑混在一起。</p>
          <div class="hero-task__meta">
            <span class="status-pill">{{ data.class_name }}</span>
            <span class="status-pill">当前状态：{{ data.attendance_status }}</span>
            <span class="status-pill" v-if="data.checked_in_at">签到时间：{{ data.checked_in_at }}</span>
          </div>
          <div class="inline-actions">
            <el-button
              type="primary"
              :loading="checkingIn"
              :disabled="!data.can_check_in"
              @click="checkIn"
            >
              {{ data.can_check_in ? '立即签到' : '已完成签到' }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Live Status</div>
        <h2 class="section-heading">当前课堂状态</h2>
        <div class="detail-list">
          <div class="detail-item">
            <div>会话状态</div>
            <strong>{{ data.session_status }}</strong>
          </div>
          <div class="detail-item">
            <div>最近活跃</div>
            <strong>{{ data.last_seen_at ?? '暂无记录' }}</strong>
          </div>
          <div class="detail-item">
            <div>求助状态</div>
            <strong>{{ data.help_open ? '已有求助' : '暂无求助' }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="surface-card" style="padding: 24px;">
      <div class="section-kicker">History</div>
      <h2 class="section-heading">签到历史</h2>
      <el-timeline v-if="data.attendance_history.length > 0">
        <el-timeline-item
          v-for="item in data.attendance_history"
          :key="`${item.session_id}-${item.started_at}`"
          :timestamp="item.started_at"
          placement="top"
        >
          <div class="detail-item" style="display: grid; gap: 8px;">
            <strong>{{ item.lesson_title }}</strong>
            <div class="muted">{{ item.class_name }}</div>
            <div class="inline-actions" style="justify-content: flex-start;">
              <el-tag :type="item.status === 'present' ? 'success' : item.status === 'late' ? 'warning' : 'info'">
                {{ item.status }}
              </el-tag>
              <span class="muted" v-if="item.marked_at">记录时间 {{ item.marked_at }}</span>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <div v-else class="empty-state">还没有签到历史记录。</div>
    </section>
  </div>
</template>
