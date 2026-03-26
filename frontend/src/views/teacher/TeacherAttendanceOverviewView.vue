<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { apiClient } from '../../api/client'
import type { TeacherAttendanceResponse } from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'

const data = ref<TeacherAttendanceResponse | null>(null)
const loading = ref(true)
const error = ref('')

const attendancePreview = computed(() => data.value?.attendance_records.slice(0, 6) ?? [])

async function loadAttendance() {
  loading.value = true
  try {
    const response = await apiClient.get<TeacherAttendanceResponse>('/teacher/attendance')
    data.value = response.data
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载签到分析。'
  } finally {
    loading.value = false
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
    <section class="metric-grid">
      <MetricCard label="在线人数" :value="`${data.radar.online}/${data.radar.expected}`" hint="课堂实时雷达" :primary="true" />
      <MetricCard label="未开始" :value="String(data.radar.not_started)" hint="需要点名跟进" />
      <MetricCard label="求助人数" :value="String(data.radar.help_requests)" hint="详情页查看求助队列" />
    </section>

    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Attendance Preview</div>
        <h2 class="section-heading">签到概览</h2>
        <div v-if="attendancePreview.length > 0" class="detail-list">
          <div v-for="record in attendancePreview" :key="record.id" class="detail-item">
            <div class="list-row__main">
              <strong>{{ record.student_name }} · {{ record.student_username }}</strong>
              <span class="muted">最近活跃 {{ record.last_seen_at || '暂无' }}</span>
            </div>
            <el-tag :type="record.status === 'present' ? 'success' : record.status === 'late' ? 'warning' : 'info'">
              {{ record.status }}
            </el-tag>
          </div>
        </div>
        <div v-else class="empty-state">当前还没有签到记录。</div>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Action</div>
        <h2 class="section-heading">进入明细处理</h2>
        <p class="muted">分析页只看统计和风险，进入二级页再执行点名、改签到和处理求助。</p>
        <RouterLink v-if="data.session_id" :to="`/teacher/attendance/sessions/${data.session_id}`">
          <el-button type="primary">进入本节签到明细</el-button>
        </RouterLink>
        <div v-else class="empty-state">当前没有可查看的课堂会话。</div>
      </div>
    </section>

    <section class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Highlights</div>
      <h2 class="section-heading">课堂提醒</h2>
      <div class="detail-list">
        <div v-for="highlight in data.analytics.highlights" :key="highlight" class="detail-item">
          <div>{{ highlight }}</div>
        </div>
      </div>
    </section>
  </div>
</template>
