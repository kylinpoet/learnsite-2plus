<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiClient } from '../../api/client'
import type { AdminOverviewResponse, MigrationFixPayload, MigrationPreviewRow } from '../../api/types'
import MetricCard from '../common/MetricCard.vue'

const overview = ref<AdminOverviewResponse | null>(null)
const error = ref('')
const executing = ref(false)
const rollingBack = ref(false)
const resolvingId = ref<number | null>(null)
const selectedSchoolCode = ref('')
const resolutionForms = reactive<Record<number, MigrationFixPayload>>({})

const statusOrder = ['draft', 'validated', 'previewed', 'executing', 'completed', 'rolled_back']
const showSchoolSwitcher = computed(() => (overview.value?.managed_schools.length ?? 0) > 1)
const activeStep = computed(() => {
  if (!overview.value) {
    return 0
  }
  const normalizedStatus =
    overview.value.active_migration.status === 'partially_failed' ? 'completed' : overview.value.active_migration.status
  const foundIndex = statusOrder.indexOf(normalizedStatus)
  return foundIndex >= 0 ? foundIndex : 0
})

function requestParams() {
  return selectedSchoolCode.value ? { school_code: selectedSchoolCode.value } : undefined
}

function syncResolutionForms(rows: MigrationPreviewRow[]) {
  rows.forEach((row) => {
    resolutionForms[row.id] = {
      new_value: row.new_value,
      resolution_note: row.resolution_note ?? '',
      status: row.status === 'mapped' ? 'mapped' : 'resolved',
    }
  })
}

async function loadOverview() {
  try {
    const { data } = await apiClient.get<AdminOverviewResponse>('/admin/overview', {
      params: requestParams(),
    })
    overview.value = data
    selectedSchoolCode.value = data.current_school.code
    syncResolutionForms(data.active_migration.preview_rows)
    error.value = ''
  } catch (requestError) {
    error.value = '治理面板加载失败，请确认管理员会话仍然有效。'
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
      undefined,
      {
        params: requestParams(),
      },
    )
    overview.value = data
    selectedSchoolCode.value = data.current_school.code
    syncResolutionForms(data.active_migration.preview_rows)
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
      undefined,
      {
        params: requestParams(),
      },
    )
    overview.value = data
    selectedSchoolCode.value = data.current_school.code
    syncResolutionForms(data.active_migration.preview_rows)
    ElMessage.success('迁移结果已回滚')
  } catch (requestError) {
    ElMessage.error('迁移回滚失败')
    console.error(requestError)
  } finally {
    rollingBack.value = false
  }
}

async function resolvePreviewRow(row: MigrationPreviewRow) {
  if (!overview.value) {
    return
  }
  const form = resolutionForms[row.id]
  if (!form?.new_value.trim() || !form.resolution_note.trim()) {
    ElMessage.warning('请填写修复后的新值和修复说明')
    return
  }

  resolvingId.value = row.id
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(
      `/admin/migrations/${overview.value.active_migration.id}/preview-items/${row.id}/resolve`,
      form,
      {
        params: requestParams(),
      },
    )
    overview.value = data
    selectedSchoolCode.value = data.current_school.code
    syncResolutionForms(data.active_migration.preview_rows)
    ElMessage.success('预览问题已保存修复结果')
  } catch (requestError) {
    ElMessage.error('保存修复失败')
    console.error(requestError)
  } finally {
    resolvingId.value = null
  }
}

async function handleSchoolChange(value: string) {
  selectedSchoolCode.value = value
  await loadOverview()
}

onMounted(async () => {
  await loadOverview()
})
</script>

<template>
  <section class="stack">
    <div>
      <div class="section-kicker">Governance Console</div>
      <h2 class="section-heading">迁移兼容与治理能力</h2>
      <p class="muted">管理员以教师控制台为统一工作台，在同一页面处理课堂和治理任务。</p>
    </div>

    <el-alert v-if="error" :closable="false" type="warning" :title="error" />

    <template v-else-if="overview">
      <section class="metric-grid">
        <MetricCard
          label="当前查看学校"
          :value="overview.current_school.name"
          :hint="`${overview.current_school.city} · 默认主题 ${overview.current_school.theme_style}`"
          :primary="true"
        />
        <MetricCard label="接入学校数" :value="String(overview.active_school_count)" hint="当前平台可管理的学校" :primary="true" />
        <MetricCard label="未解决预览项" :value="String(overview.unresolved_preview_count)" hint="修复完成后才允许执行迁移" />
        <MetricCard label="映射记录" :value="String(overview.legacy_mappings.length)" hint="本批次已生成的兼容映射数量" />
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Managed Schools</div>
          <h2 class="section-heading">多学校上下文</h2>
          <p class="muted" style="margin-bottom: 16px;">
            当前治理作用域：{{ overview.current_school.name }} · {{ overview.current_school.city }}
          </p>
          <el-form-item v-if="showSchoolSwitcher" label="切换查看学校" style="margin-bottom: 16px;">
            <el-select v-model="selectedSchoolCode" class="full-width" placeholder="请选择学校" @change="handleSchoolChange">
              <el-option
                v-for="school in overview.managed_schools"
                :key="school.code"
                :label="`${school.name} · ${school.city}`"
                :value="school.code"
              />
            </el-select>
          </el-form-item>
          <div class="list-panel">
            <div v-for="snapshot in overview.school_snapshots" :key="snapshot.school.code" class="detail-item" style="display: grid; gap: 10px;">
              <div class="list-row__main">
                <strong>{{ snapshot.school.name }}</strong>
                <span class="muted">
                  {{ snapshot.school.city }} · 默认风格 {{ snapshot.school.theme_style }}
                  <span v-if="snapshot.latest_batch_name"> · {{ snapshot.latest_batch_name }}</span>
                </span>
                <span v-if="snapshot.current_step" class="muted">{{ snapshot.current_step }}</span>
              </div>
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-tag>{{ snapshot.school.code }}</el-tag>
                <el-tag :type="snapshot.is_current ? 'success' : 'info'">
                  {{ snapshot.is_current ? '当前查看' : '可切换' }}
                </el-tag>
                <el-tag v-if="snapshot.latest_batch_status" :type="snapshot.unresolved_preview_count > 0 ? 'warning' : 'success'">
                  {{ snapshot.latest_batch_status }}
                </el-tag>
                <el-tag :type="snapshot.unresolved_preview_count > 0 ? 'warning' : 'info'">
                  未解决 {{ snapshot.unresolved_preview_count }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Migration State</div>
          <h2 class="section-heading">迁移状态机</h2>
          <p class="muted" style="margin-bottom: 16px;">当前批次：{{ overview.active_migration.name }} · {{ overview.current_school.name }}</p>
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
            <el-alert
              v-if="overview.unresolved_preview_count > 0"
              type="warning"
              :closable="false"
              :title="`还有 ${overview.unresolved_preview_count} 条预览问题未解决，暂不可执行迁移。`"
            />
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
        <h2 class="section-heading">预览问题与人工修复</h2>
        <div class="detail-list">
          <div
            v-for="row in overview.active_migration.preview_rows"
            :key="row.id"
            class="detail-item"
            style="display: grid; gap: 14px;"
          >
            <div class="inline-actions" style="justify-content: space-between;">
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-tag :type="row.requires_resolution ? 'warning' : 'success'">{{ row.status }}</el-tag>
                <strong>{{ row.field_name }}</strong>
              </div>
              <span v-if="row.resolved_at" class="muted">最近修复：{{ row.resolved_at }}</span>
            </div>

            <div class="page-grid page-grid--two">
              <div class="detail-item" style="display: grid; gap: 6px;">
                <div class="section-kicker">Legacy Value</div>
                <div>{{ row.legacy_value }}</div>
              </div>
              <div class="detail-item" style="display: grid; gap: 6px;">
                <div class="section-kicker">Current Mapping</div>
                <div>{{ row.new_value }}</div>
              </div>
            </div>

            <div v-if="row.issue_detail" class="muted">{{ row.issue_detail }}</div>
            <div v-if="row.resolution_note" class="muted">修复说明：{{ row.resolution_note }}</div>

            <div v-if="row.requires_resolution" class="page-grid page-grid--two">
              <el-form-item label="修复后的新值" style="margin-bottom: 0;">
                <el-input v-model="resolutionForms[row.id].new_value" placeholder="输入修复后的映射值" />
              </el-form-item>
              <el-form-item label="修复说明" style="margin-bottom: 0;">
                <el-input v-model="resolutionForms[row.id].resolution_note" placeholder="说明为什么这样修复" />
              </el-form-item>
            </div>

            <div v-if="row.requires_resolution" class="inline-actions">
              <el-button type="primary" :loading="resolvingId === row.id" @click="resolvePreviewRow(row)">
                保存修复
              </el-button>
            </div>
          </div>
        </div>
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
    </template>

    <el-skeleton v-else :rows="8" animated />
  </section>
</template>
