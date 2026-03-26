<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiClient } from '../../api/client'
import type { AdminOverviewResponse, AuditLogLevel, BackupCreatePayload, BackupSnapshotSummary, MessageResponse } from '../../api/types'
import { useSession } from '../../composables/useSession'

const { sessionState } = useSession()

const overview = ref<AdminOverviewResponse | null>(null)
const loadError = ref('')
const creatingBackup = ref(false)
const restoringBackupId = ref<number | null>(null)
const selectedSchoolCode = ref('')
const backupForm = reactive<BackupCreatePayload>({
  note: '',
})

const canManageBackupSnapshots = computed(() => sessionState.value?.role === 'platform_admin')
const showSchoolSwitcher = computed(() => (overview.value?.managed_schools.length ?? 0) > 1)

function requestParams() {
  return selectedSchoolCode.value ? { school_code: selectedSchoolCode.value } : undefined
}

function applyOverview(data: AdminOverviewResponse) {
  overview.value = data
  selectedSchoolCode.value = data.current_school.code
  loadError.value = ''
}

function auditLevelTagType(level: AuditLogLevel) {
  if (level === 'risk') {
    return 'danger'
  }
  if (level === 'warning') {
    return 'warning'
  }
  return 'info'
}

function auditRoleLabel(role: string) {
  if (role === 'platform_admin') {
    return '平台管理员'
  }
  if (role === 'school_admin') {
    return '学校管理员'
  }
  return role === 'teacher' ? '教师' : '学生'
}

function backupStatusTagType(snapshot: BackupSnapshotSummary) {
  return snapshot.status === 'restored' ? 'warning' : 'success'
}

async function loadOverview() {
  try {
    const { data } = await apiClient.get<AdminOverviewResponse>('/admin/overview', {
      params: requestParams(),
    })
    applyOverview(data)
  } catch (requestError) {
    loadError.value = '治理审计面板加载失败，请确认管理员会话仍然有效。'
    console.error(requestError)
  }
}

async function handleSchoolSwitch() {
  await loadOverview()
}

async function createBackupSnapshot() {
  if (!canManageBackupSnapshots.value) {
    ElMessage.warning('本地 SQLite 快照创建仅开放给平台管理员')
    return
  }
  creatingBackup.value = true
  try {
    const payload: BackupCreatePayload = {
      note: backupForm.note?.trim() || null,
    }
    const { data } = await apiClient.post<AdminOverviewResponse>('/admin/backups', payload, {
      params: requestParams(),
    })
    applyOverview(data)
    backupForm.note = ''
    ElMessage.success('本地备份快照已创建')
  } catch (requestError) {
    ElMessage.error('创建备份快照失败')
    console.error(requestError)
  } finally {
    creatingBackup.value = false
  }
}

async function restoreBackupSnapshot(snapshot: BackupSnapshotSummary) {
  if (!canManageBackupSnapshots.value) {
    ElMessage.warning('本地 SQLite 快照恢复仅开放给平台管理员')
    return
  }
  restoringBackupId.value = snapshot.id
  try {
    const { data } = await apiClient.post<MessageResponse>(`/admin/backups/${snapshot.id}/restore`, undefined, {
      params: requestParams(),
    })
    await loadOverview()
    ElMessage.success(data.message || '备份快照已恢复')
  } catch (requestError) {
    ElMessage.error('恢复备份快照失败')
    console.error(requestError)
  } finally {
    restoringBackupId.value = null
  }
}

onMounted(async () => {
  await loadOverview()
})
</script>

<template>
  <section class="page-grid page-grid--two">
    <div class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Risk Operations</div>
      <h2 class="section-heading">本地备份与恢复</h2>
      <p class="muted" style="margin-bottom: 16px;">
        当前默认仍是本地 SQLite 开发环境。执行迁移、批量导入或高风险治理操作前，建议先创建一份快照。
      </p>

      <el-alert v-if="loadError" type="warning" :closable="false" :title="loadError" style="margin-bottom: 16px;" />

      <template v-if="overview">
        <div v-if="showSchoolSwitcher" class="stack" style="gap: 8px; margin-bottom: 16px;">
          <div class="section-kicker">当前治理学校</div>
          <el-select v-model="selectedSchoolCode" class="full-width" @change="handleSchoolSwitch">
            <el-option
              v-for="school in overview.managed_schools"
              :key="school.code"
              :label="`${school.name}（${school.code}）`"
              :value="school.code"
            />
          </el-select>
        </div>

        <el-alert
          type="warning"
          :closable="false"
          title="恢复快照会直接覆盖当前本地数据库文件，仅建议在开发验证环境中使用。"
          style="margin-bottom: 16px;"
        />
        <el-alert
          v-if="!canManageBackupSnapshots"
          type="info"
          :closable="false"
          title="当前账号只有查看权限，本地 SQLite 快照创建与恢复仅开放给平台管理员。"
          style="margin-bottom: 16px;"
        />

        <el-form label-position="top">
          <el-form-item label="快照备注">
            <el-input
              v-model="backupForm.note"
              maxlength="255"
              show-word-limit
              placeholder="例如：执行批量导入前的治理快照"
            />
          </el-form-item>
          <div class="inline-actions" style="margin-bottom: 18px;">
            <el-button type="primary" :loading="creatingBackup" :disabled="!canManageBackupSnapshots" @click="createBackupSnapshot">
              创建本地备份快照
            </el-button>
          </div>
        </el-form>

        <div v-if="overview.backup_snapshots.length > 0" class="detail-list">
          <div
            v-for="snapshot in overview.backup_snapshots"
            :key="snapshot.id"
            class="detail-item"
            style="display: grid; gap: 10px;"
          >
            <div class="inline-actions" style="justify-content: space-between;">
              <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
                <el-tag :type="backupStatusTagType(snapshot)">{{ snapshot.status === 'restored' ? '最近已恢复' : '可恢复' }}</el-tag>
                <el-tag>{{ snapshot.file_size_label }}</el-tag>
                <strong>{{ snapshot.file_name }}</strong>
              </div>
              <el-button
                size="small"
                type="danger"
                plain
                :loading="restoringBackupId === snapshot.id"
                :disabled="!canManageBackupSnapshots"
                @click="restoreBackupSnapshot(snapshot)"
              >
                恢复此快照
              </el-button>
            </div>
            <div class="muted">
              创建人：{{ snapshot.actor_display_name }} · {{ snapshot.created_at }}
              <span v-if="snapshot.restored_at"> · 最近恢复于 {{ snapshot.restored_at }}</span>
            </div>
            <div v-if="snapshot.note">{{ snapshot.note }}</div>
          </div>
        </div>
        <div v-else class="empty-state">当前还没有备份快照，建议先创建一份再执行高风险治理动作。</div>
      </template>

      <el-skeleton v-else :rows="4" animated />
    </div>

    <div class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Audit Trail</div>
      <h2 class="section-heading">治理审计日志</h2>
      <p class="muted" style="margin-bottom: 16px;">
        记录当前学校治理动作的最近留痕，帮助回看是谁在什么时间改了什么。
      </p>

      <el-alert v-if="loadError" type="warning" :closable="false" :title="loadError" style="margin-bottom: 16px;" />

      <template v-if="overview">
        <div v-if="overview.recent_audit_logs.length > 0" class="detail-list">
          <div
            v-for="log in overview.recent_audit_logs"
            :key="log.id"
            class="detail-item"
            style="display: grid; gap: 8px;"
          >
            <div class="inline-actions" style="justify-content: space-between;">
              <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
                <el-tag :type="auditLevelTagType(log.level)">{{ log.level }}</el-tag>
                <el-tag>{{ auditRoleLabel(log.actor_role) }}</el-tag>
                <strong>{{ log.summary }}</strong>
              </div>
              <span class="muted">{{ log.created_at }}</span>
            </div>
            <div class="muted">{{ log.actor_display_name }} · {{ log.actor_username }} · {{ log.target_type }} / {{ log.target_label }}</div>
            <div v-if="log.detail">{{ log.detail }}</div>
          </div>
        </div>
        <div v-else class="empty-state">当前学校还没有治理审计日志。</div>
      </template>

      <el-skeleton v-else :rows="5" animated />
    </div>
  </section>
</template>
