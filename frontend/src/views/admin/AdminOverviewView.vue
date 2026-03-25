<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiClient } from '../../api/client'
import type { AdminOverviewResponse } from '../../api/types'
import MetricCard from '../../components/common/MetricCard.vue'
import { useSession } from '../../composables/useSession'
import PortalLayout from '../../layouts/PortalLayout.vue'

const { sessionState } = useSession()
const overview = ref<AdminOverviewResponse | null>(null)
const error = ref('')
const executing = ref(false)
const rollingBack = ref(false)
const navItems = [
  { label: '课堂控制台', to: '/teacher/console' },
  { label: '迁移兼容中心', to: '/admin/overview' },
]

const statusOrder = ['draft', 'validated', 'previewed', 'executing', 'completed', 'partially_failed', 'rolled_back']
const activeStep = computed(() => {
  if (!overview.value) {
    return 0
  }
  const normalizedStatus = overview.value.active_migration.status === 'partially_failed' ? 'completed' : overview.value.active_migration.status
  const foundIndex = statusOrder.indexOf(normalizedStatus)
  return foundIndex >= 0 ? foundIndex : 0
})

async function loadOverview() {
  try {
    const { data } = await apiClient.get<AdminOverviewResponse>('/admin/overview')
    overview.value = data
    error.value = ''
  } catch (requestError) {
    error.value = '管理后台加载失败，请确认后端服务已启动。'
    console.error(requestError)
  }
}

async function executeMigration() {
  if (!overview.value) {
    return
  }

  executing.value = true
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(
      `/admin/migrations/${overview.value.active_migration.id}/execute`,
    )
    overview.value = data
    ElMessage.success('迁移执行完成')
  } catch (requestError) {
    ElMessage.error('迁移执行失败')
    console.error(requestError)
  } finally {
    executing.value = false
  }
}

async function rollbackMigration() {
  if (!overview.value) {
    return
  }

  rollingBack.value = true
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(
      `/admin/migrations/${overview.value.active_migration.id}/rollback`,
    )
    overview.value = data
    ElMessage.success('迁移结果已回滚')
  } catch (requestError) {
    ElMessage.error('迁移回滚失败')
    console.error(requestError)
  } finally {
    rollingBack.value = false
  }
}

onMounted(async () => {
  await loadOverview()
})
</script>

<template>
  <PortalLayout
    role-label="教师管理员工作区"
    title="迁移兼容中心"
    subtitle="管理员通过教师入口登录后，可在同一工作区里执行迁移与回滚。"
    :school-name="overview?.school_name ?? sessionState?.school_name ?? '加载中...'"
    :user-name="overview?.admin_name ?? sessionState?.display_name ?? '管理员'"
    :nav-items="navItems"
  >
    <el-alert v-if="error" :closable="false" type="warning" :title="error" />

    <div v-else-if="overview" class="stack">
      <section class="metric-grid">
        <MetricCard label="接入学校数" :value="String(overview.active_school_count)" hint="当前平台可管理的学校" :primary="true" />
        <MetricCard label="迁移批次" :value="overview.active_migration.name" hint="当前活跃批次名称" />
        <MetricCard label="映射记录" :value="String(overview.legacy_mappings.length)" hint="本批次已生成的兼容映射数量" />
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Managed Schools</div>
          <h2 class="section-heading">多学校上下文</h2>
          <div class="list-panel">
            <div v-for="school in overview.managed_schools" :key="school.code" class="list-row">
              <div class="list-row__main">
                <strong>{{ school.name }}</strong>
                <span class="muted">{{ school.city }} · 默认风格 {{ school.theme_style }}</span>
              </div>
              <el-tag>{{ school.code }}</el-tag>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Migration State</div>
          <h2 class="section-heading">迁移状态机</h2>
          <el-steps :active="activeStep" finish-status="success" align-center>
            <el-step title="draft" />
            <el-step title="validated" />
            <el-step title="previewed" />
            <el-step title="executing" />
            <el-step title="completed" />
            <el-step title="rolled_back" />
          </el-steps>
          <div class="stack" style="margin-top: 18px;">
            <el-progress :percentage="overview.active_migration.progress" :stroke-width="18" />
            <div class="status-pill">当前步骤：{{ overview.active_migration.current_step }}</div>
            <div class="inline-actions">
              <el-button type="primary" :loading="executing" :disabled="!overview.can_execute_migration" @click="executeMigration">
                执行迁移
              </el-button>
              <el-button type="danger" plain :loading="rollingBack" :disabled="!overview.can_rollback_migration" @click="rollbackMigration">
                回滚迁移
              </el-button>
            </div>
          </div>
        </div>
      </section>

      <section class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Preview Diff</div>
        <h2 class="section-heading">旧模板预览差异</h2>
        <el-table :data="overview.active_migration.preview_rows" style="width: 100%;">
          <el-table-column prop="field_name" label="字段" />
          <el-table-column prop="legacy_value" label="旧值" />
          <el-table-column prop="new_value" label="新值" />
          <el-table-column prop="status" label="状态" />
        </el-table>
      </section>

      <section class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Legacy Mapping</div>
        <h2 class="section-heading">迁移兼容映射</h2>
        <el-table :data="overview.legacy_mappings" style="width: 100%;">
          <el-table-column prop="entity_type" label="类型" />
          <el-table-column prop="legacy_id" label="旧 ID / 旧值" />
          <el-table-column prop="new_id" label="新 ID / 新值" />
          <el-table-column label="是否生效">
            <template #default="{ row }">
              <el-tag :type="row.active ? 'success' : 'info'">{{ row.active ? 'active' : 'inactive' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Guardrails</div>
        <h2 class="section-heading">平台治理约束</h2>
        <div class="detail-list">
          <div v-for="rule in overview.guardrails" :key="rule" class="detail-item">
            <div>{{ rule }}</div>
          </div>
        </div>
      </section>
    </div>

    <el-skeleton v-else :rows="8" animated />
  </PortalLayout>
</template>
