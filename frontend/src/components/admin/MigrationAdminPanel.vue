<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiClient } from '../../api/client'
import type {
  AcademicTermCreatePayload,
  AdminOverviewResponse,
  AdminStudentImportResponse,
  AdminTeacherSummary,
  ManagedTeacherRole,
  MigrationFixPayload,
  MigrationPreviewRow,
  PasswordResetPayload,
  ResourceCategoryCreatePayload,
  ResourceCategoryStatusPayload,
  ResourceCategorySummary,
  StudentAssignmentPayload,
  StudentImportPayload,
  TeacherAccountSavePayload,
  UserStatusUpdatePayload,
} from '../../api/types'
import { useSession } from '../../composables/useSession'
import MetricCard from '../common/MetricCard.vue'

const { sessionState } = useSession()

const overview = ref<AdminOverviewResponse | null>(null)
const error = ref('')
const executing = ref(false)
const rollingBack = ref(false)
const resolvingId = ref<number | null>(null)
const creatingTerm = ref(false)
const activatingTermId = ref<number | null>(null)
const savingTeacher = ref(false)
const resettingTeacherId = ref<number | null>(null)
const togglingTeacherId = ref<number | null>(null)
const creatingResourceCategory = ref(false)
const togglingResourceCategoryId = ref<number | null>(null)
const assigningStudentId = ref<number | null>(null)
const importingStudents = ref(false)
const resettingStudentId = ref<number | null>(null)
const togglingStudentId = ref<number | null>(null)
const selectedSchoolCode = ref('')
const resolutionForms = reactive<Record<number, MigrationFixPayload>>({})
const assignmentForms = reactive<Record<number, StudentAssignmentPayload>>({})
const teacherForm = reactive<TeacherAccountSavePayload>({
  teacher_id: null,
  username: '',
  display_name: '',
  role: 'teacher',
  password: '222221',
  classroom_ids: [],
})
const importForm = reactive<StudentImportPayload>({
  classroom_id: 0,
  rows_text: '',
  default_password: '12345',
})
const teacherResetForm = reactive<PasswordResetPayload>({
  new_password: '222221',
})
const studentResetForm = reactive<PasswordResetPayload>({
  new_password: '12345',
})
const termForm = reactive<AcademicTermCreatePayload>({
  school_year_label: '2026-2027',
  term_name: '2026 秋季学期',
  start_on: '',
  end_on: '',
  activate_now: true,
})
const resourceCategoryForm = reactive<ResourceCategoryCreatePayload>({
  name: '',
  description: '',
  sort_order: 1,
})

const statusOrder = ['draft', 'validated', 'previewed', 'executing', 'completed', 'rolled_back']
const showSchoolSwitcher = computed(() => (overview.value?.managed_schools.length ?? 0) > 1)
const canManageSchoolAdmins = computed(() => sessionState.value?.role === 'platform_admin')
const nextResourceCategorySortOrder = computed(() => {
  const maxSortOrder = Math.max(0, ...(overview.value?.resource_categories.map((category) => category.sort_order) ?? [0]))
  return maxSortOrder + 1
})
const teacherRoleOptions = computed<Array<{ value: ManagedTeacherRole; label: string }>>(() =>
  canManageSchoolAdmins.value
    ? [
        { value: 'teacher', label: '教师' },
        { value: 'school_admin', label: '管理员' },
      ]
    : [{ value: 'teacher', label: '教师' }],
)
const activeTermLabel = computed(() => {
  if (!overview.value?.active_term) {
    return '未设置'
  }
  return `${overview.value.active_term.school_year_label} · ${overview.value.active_term.term_name}`
})
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

function teacherRoleLabel(role: ManagedTeacherRole) {
  return role === 'school_admin' ? '管理员态' : '教师态'
}

function teacherRoleTagType(role: ManagedTeacherRole) {
  return role === 'school_admin' ? 'warning' : 'success'
}

function canManageTeacherAccount(account: AdminTeacherSummary) {
  return canManageSchoolAdmins.value || account.role === 'teacher'
}

function resetTeacherForm() {
  teacherForm.teacher_id = null
  teacherForm.username = ''
  teacherForm.display_name = ''
  teacherForm.role = 'teacher'
  teacherForm.password = '222221'
  teacherForm.classroom_ids = []
}

function resetResourceCategoryForm() {
  resourceCategoryForm.name = ''
  resourceCategoryForm.description = ''
  resourceCategoryForm.sort_order = nextResourceCategorySortOrder.value
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

function syncAssignmentForms() {
  overview.value?.students.forEach((student) => {
    assignmentForms[student.id] = {
      classroom_id: student.classroom_id ?? overview.value?.classrooms[0]?.id ?? 0,
    }
  })
  if (overview.value?.classrooms.length) {
    importForm.classroom_id = importForm.classroom_id || overview.value.classrooms[0].id
  }
}

function syncTeacherEditor() {
  if (teacherForm.teacher_id === null) {
    return
  }
  const account = overview.value?.teacher_accounts.find((item) => item.id === teacherForm.teacher_id)
  if (!account || !canManageTeacherAccount(account)) {
    resetTeacherForm()
    return
  }
  teacherForm.username = account.username
  teacherForm.display_name = account.display_name
  teacherForm.role = account.role
  teacherForm.classroom_ids = [...account.assigned_classroom_ids]
}

function applyOverview(data: AdminOverviewResponse) {
  overview.value = data
  selectedSchoolCode.value = data.current_school.code
  syncResolutionForms(data.active_migration.preview_rows)
  syncAssignmentForms()
  syncTeacherEditor()
  if (!resourceCategoryForm.name.trim()) {
    resourceCategoryForm.sort_order = nextResourceCategorySortOrder.value
  }
  error.value = ''
}

function editTeacherAccount(account: AdminTeacherSummary) {
  if (!canManageTeacherAccount(account)) {
    ElMessage.warning('当前账号权限不允许直接编辑管理员态账号。')
    return
  }

  teacherForm.teacher_id = account.id
  teacherForm.username = account.username
  teacherForm.display_name = account.display_name
  teacherForm.role = account.role
  teacherForm.password = ''
  teacherForm.classroom_ids = [...account.assigned_classroom_ids]
}

async function loadOverview() {
  try {
    const { data } = await apiClient.get<AdminOverviewResponse>('/admin/overview', {
      params: requestParams(),
    })
    applyOverview(data)
  } catch (requestError) {
    error.value = '治理面板加载失败，请确认管理员会话仍然有效。'
    console.error(requestError)
  }
}

async function createTerm() {
  if (!termForm.school_year_label.trim() || !termForm.term_name.trim()) {
    ElMessage.warning('请先填写学年和学期名称')
    return
  }

  creatingTerm.value = true
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>('/admin/terms', termForm, {
      params: requestParams(),
    })
    applyOverview(data)
    ElMessage.success('学期已创建')
  } catch (requestError) {
    ElMessage.error('创建学期失败')
    console.error(requestError)
  } finally {
    creatingTerm.value = false
  }
}

async function activateTerm(termId: number) {
  activatingTermId.value = termId
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(`/admin/terms/${termId}/activate`, undefined, {
      params: requestParams(),
    })
    applyOverview(data)
    ElMessage.success('当前学期已切换')
  } catch (requestError) {
    ElMessage.error('切换学期失败')
    console.error(requestError)
  } finally {
    activatingTermId.value = null
  }
}

async function saveTeacherAccount() {
  if (!teacherForm.username?.trim() || !teacherForm.display_name?.trim()) {
    ElMessage.warning('请先填写账号和教师姓名')
    return
  }
  if (teacherForm.role === 'school_admin' && !canManageSchoolAdmins.value) {
    ElMessage.warning('当前会话只能创建普通教师账号')
    return
  }

  savingTeacher.value = true
  try {
    const payload: TeacherAccountSavePayload = {
      teacher_id: teacherForm.teacher_id,
      username: teacherForm.username.trim(),
      display_name: teacherForm.display_name.trim(),
      role: teacherForm.role,
      password: teacherForm.password?.trim() || null,
      classroom_ids: teacherForm.role === 'teacher' ? [...teacherForm.classroom_ids] : [],
    }
    if (!payload.teacher_id && !payload.password) {
      payload.password = '222221'
    }
    const { data } = await apiClient.post<AdminOverviewResponse>('/admin/teachers', payload, {
      params: requestParams(),
    })
    applyOverview(data)
    ElMessage.success(payload.teacher_id ? '账号资料已更新' : '教师账号已创建')
    resetTeacherForm()
  } catch (requestError) {
    ElMessage.error('保存教师账号失败')
    console.error(requestError)
  } finally {
    savingTeacher.value = false
  }
}

async function resetTeacherPassword(teacherId: number) {
  if (!teacherResetForm.new_password.trim()) {
    ElMessage.warning('请先填写教师重置密码')
    return
  }

  resettingTeacherId.value = teacherId
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(
      `/admin/teachers/${teacherId}/reset-password`,
      teacherResetForm,
      {
        params: requestParams(),
      },
    )
    applyOverview(data)
    ElMessage.success('教师账号密码已重置')
  } catch (requestError) {
    ElMessage.error('重置教师密码失败')
    console.error(requestError)
  } finally {
    resettingTeacherId.value = null
  }
}

async function updateTeacherStatus(account: AdminTeacherSummary, active: boolean) {
  const payload: UserStatusUpdatePayload = { active }
  togglingTeacherId.value = account.id
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(`/admin/teachers/${account.id}/status`, payload, {
      params: requestParams(),
    })
    applyOverview(data)
    ElMessage.success(active ? '教师账号已启用' : '教师账号已停用')
  } catch (requestError) {
    ElMessage.error(active ? '启用教师账号失败' : '停用教师账号失败')
    console.error(requestError)
  } finally {
    togglingTeacherId.value = null
  }
}

async function createResourceCategory() {
  if (!resourceCategoryForm.name.trim()) {
    ElMessage.warning('请先填写资源分类名称')
    return
  }

  creatingResourceCategory.value = true
  try {
    const payload: ResourceCategoryCreatePayload = {
      name: resourceCategoryForm.name.trim(),
      description: resourceCategoryForm.description?.trim() || null,
      sort_order: resourceCategoryForm.sort_order,
    }
    const { data } = await apiClient.post<AdminOverviewResponse>('/admin/resource-categories', payload, {
      params: requestParams(),
    })
    applyOverview(data)
    resetResourceCategoryForm()
    ElMessage.success('资源分类已创建')
  } catch (requestError) {
    ElMessage.error('创建资源分类失败')
    console.error(requestError)
  } finally {
    creatingResourceCategory.value = false
  }
}

async function updateResourceCategoryStatus(category: ResourceCategorySummary, active: boolean) {
  const payload: ResourceCategoryStatusPayload = { active }
  togglingResourceCategoryId.value = category.id
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(
      `/admin/resource-categories/${category.id}/status`,
      payload,
      {
        params: requestParams(),
      },
    )
    applyOverview(data)
    ElMessage.success(active ? '资源分类已启用' : '资源分类已停用')
  } catch (requestError) {
    ElMessage.error(active ? '启用资源分类失败' : '停用资源分类失败')
    console.error(requestError)
  } finally {
    togglingResourceCategoryId.value = null
  }
}

async function assignStudent(studentId: number) {
  if (!overview.value) {
    return
  }
  const form = assignmentForms[studentId]
  if (!form?.classroom_id) {
    ElMessage.warning('请先选择目标班级')
    return
  }

  assigningStudentId.value = studentId
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(
      `/admin/students/${studentId}/assign-classroom`,
      form,
      {
        params: requestParams(),
      },
    )
    applyOverview(data)
    ElMessage.success('学生编班已更新')
  } catch (requestError) {
    ElMessage.error('更新学生编班失败')
    console.error(requestError)
  } finally {
    assigningStudentId.value = null
  }
}

async function resetStudentPassword(studentId: number) {
  if (!studentResetForm.new_password.trim()) {
    ElMessage.warning('请先填写学生重置密码')
    return
  }

  resettingStudentId.value = studentId
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(
      `/admin/students/${studentId}/reset-password`,
      studentResetForm,
      {
        params: requestParams(),
      },
    )
    applyOverview(data)
    ElMessage.success('学生密码已重置')
  } catch (requestError) {
    ElMessage.error('重置学生密码失败')
    console.error(requestError)
  } finally {
    resettingStudentId.value = null
  }
}

async function updateStudentStatus(studentId: number, active: boolean) {
  const payload: UserStatusUpdatePayload = { active }
  togglingStudentId.value = studentId
  try {
    const { data } = await apiClient.post<AdminOverviewResponse>(`/admin/students/${studentId}/status`, payload, {
      params: requestParams(),
    })
    applyOverview(data)
    ElMessage.success(active ? '学生账号已启用' : '学生账号已停用')
  } catch (requestError) {
    ElMessage.error(active ? '启用学生账号失败' : '停用学生账号失败')
    console.error(requestError)
  } finally {
    togglingStudentId.value = null
  }
}

async function importStudents() {
  if (!importForm.classroom_id || !importForm.rows_text.trim()) {
    ElMessage.warning('请先选择班级并粘贴学生数据')
    return
  }

  importingStudents.value = true
  try {
    const { data } = await apiClient.post<AdminStudentImportResponse>('/admin/students/import', importForm, {
      params: requestParams(),
    })
    applyOverview(data.overview)
    importForm.rows_text = ''
    ElMessage.success(`导入完成：新增 ${data.result.imported_count}，更新 ${data.result.updated_count}，跳过 ${data.result.skipped_count}`)
  } catch (requestError) {
    ElMessage.error('学生导入失败')
    console.error(requestError)
  } finally {
    importingStudents.value = false
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
    applyOverview(data)
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
    applyOverview(data)
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
    applyOverview(data)
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
  resetTeacherForm()
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
        <MetricCard label="接入学校数" :value="String(overview.active_school_count)" hint="当前平台可管理的学校" />
        <MetricCard label="当前学期" :value="activeTermLabel" :hint="overview.active_term ? '已配置当前生效学期' : '尚未设置学期'" />
        <MetricCard label="学生总数" :value="String(overview.students.length)" hint="当前学校纳入管理的学生数量" />
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

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Academic Terms</div>
          <h2 class="section-heading">学年学期设置</h2>
          <p class="muted" style="margin-bottom: 16px;">
            当前生效学期：{{ overview.active_term ? `${overview.active_term.school_year_label} · ${overview.active_term.term_name}` : '尚未设置' }}
          </p>

          <el-form label-position="top">
            <div class="page-grid page-grid--two">
              <el-form-item label="学年">
                <el-input v-model="termForm.school_year_label" placeholder="例如 2026-2027" />
              </el-form-item>
              <el-form-item label="学期名称">
                <el-input v-model="termForm.term_name" placeholder="例如 2026 秋季学期" />
              </el-form-item>
            </div>
            <div class="page-grid page-grid--two">
              <el-form-item label="开始日期">
                <el-input v-model="termForm.start_on" placeholder="YYYY-MM-DD" />
              </el-form-item>
              <el-form-item label="结束日期">
                <el-input v-model="termForm.end_on" placeholder="YYYY-MM-DD" />
              </el-form-item>
            </div>
            <el-form-item>
              <el-checkbox v-model="termForm.activate_now">创建后立即设为当前学期</el-checkbox>
            </el-form-item>
            <el-button type="primary" :loading="creatingTerm" @click="createTerm">
              创建学期
            </el-button>
          </el-form>

          <div class="detail-list" style="margin-top: 18px;">
            <div
              v-for="term in overview.academic_terms"
              :key="term.id"
              class="detail-item"
              style="display: grid; gap: 10px;"
            >
              <div class="inline-actions" style="justify-content: space-between;">
                <div class="inline-actions" style="justify-content: flex-start;">
                  <el-tag :type="term.is_active ? 'success' : 'info'">{{ term.is_active ? '当前学期' : '历史 / 待启用' }}</el-tag>
                  <strong>{{ term.school_year_label }} · {{ term.term_name }}</strong>
                </div>
                <el-button
                  size="small"
                  plain
                  :loading="activatingTermId === term.id"
                  :disabled="term.is_active"
                  @click="activateTerm(term.id)"
                >
                  设为当前学期
                </el-button>
              </div>
              <div class="muted">{{ term.start_on || '未设置开始日期' }} 至 {{ term.end_on || '未设置结束日期' }}</div>
            </div>
          </div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Class Structure</div>
          <h2 class="section-heading">班级体系</h2>
          <p class="muted" style="margin-bottom: 16px;">先选学校，再看当前学校内部的班级分布和学生承载情况。</p>
          <div class="detail-list">
            <div
              v-for="classroom in overview.classrooms"
              :key="classroom.id"
              class="detail-item"
              style="display: grid; gap: 8px;"
            >
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-tag>{{ classroom.grade_label }}</el-tag>
                <strong>{{ classroom.name }}</strong>
              </div>
              <div class="muted">当前学生数：{{ classroom.student_count }}</div>
            </div>
          </div>
        </div>
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Teacher Accounts</div>
          <h2 class="section-heading">教师 / 管理员账号</h2>
          <p class="muted" style="margin-bottom: 16px;">
            管理员仍然通过教师入口登录，这里统一维护教师态与管理员态账号。
          </p>
          <el-form-item label="教师一键重置密码" style="margin-bottom: 16px;">
            <el-input v-model="teacherResetForm.new_password" placeholder="点击列表中的重置密码按钮时使用" />
          </el-form-item>
          <div v-if="overview.teacher_accounts.length > 0" class="detail-list">
            <div
              v-for="account in overview.teacher_accounts"
              :key="account.id"
              class="detail-item"
              style="display: grid; gap: 10px;"
            >
              <div class="inline-actions" style="justify-content: space-between;">
                <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
                  <el-tag :type="teacherRoleTagType(account.role)">{{ teacherRoleLabel(account.role) }}</el-tag>
                  <el-tag :type="account.active ? 'success' : 'info'">{{ account.active ? '在用' : '停用' }}</el-tag>
                  <strong>{{ account.display_name }}</strong>
                </div>
                <span class="muted">{{ account.username }}</span>
              </div>
              <div class="muted">
                授课班级：{{ account.assigned_classroom_names.length > 0 ? account.assigned_classroom_names.join('、') : '未分配班级' }}
              </div>
              <div class="inline-actions" style="justify-content: flex-start;">
                <el-button size="small" plain :disabled="!canManageTeacherAccount(account)" @click="editTeacherAccount(account)">
                  编辑
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :loading="resettingTeacherId === account.id"
                  :disabled="!canManageTeacherAccount(account)"
                  @click="resetTeacherPassword(account.id)"
                >
                  重置密码
                </el-button>
                <el-button
                  size="small"
                  :type="account.active ? 'danger' : 'success'"
                  plain
                  :loading="togglingTeacherId === account.id"
                  :disabled="!canManageTeacherAccount(account)"
                  @click="updateTeacherStatus(account, !account.active)"
                >
                  {{ account.active ? '停用账号' : '启用账号' }}
                </el-button>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">当前学校还没有教师账号，请先在右侧创建。</div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Account Editor</div>
          <h2 class="section-heading">{{ teacherForm.teacher_id ? '编辑教师账号' : '新建教师账号' }}</h2>
          <el-form label-position="top">
            <div class="page-grid page-grid--two">
              <el-form-item label="登录账号">
                <el-input v-model="teacherForm.username" placeholder="例如 kyli-tech-01" />
              </el-form-item>
              <el-form-item label="教师姓名">
                <el-input v-model="teacherForm.display_name" placeholder="例如 李老师" />
              </el-form-item>
            </div>
            <div class="page-grid page-grid--two">
              <el-form-item label="账号角色">
                <el-select v-model="teacherForm.role" class="full-width">
                  <el-option
                    v-for="roleOption in teacherRoleOptions"
                    :key="roleOption.value"
                    :label="roleOption.label"
                    :value="roleOption.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="teacherForm.teacher_id ? '新密码（留空则不修改）' : '初始密码'">
                <el-input
                  v-model="teacherForm.password"
                  type="password"
                  show-password
                  :placeholder="teacherForm.teacher_id ? '不修改时可留空' : '默认 222221'"
                />
              </el-form-item>
            </div>
            <el-form-item v-if="teacherForm.role === 'teacher'" label="可授课班级">
              <el-select
                v-model="teacherForm.classroom_ids"
                class="full-width"
                placeholder="请选择教师可开课的班级"
                multiple
                collapse-tags
                collapse-tags-tooltip
              >
                <el-option
                  v-for="classroom in overview.classrooms"
                  :key="classroom.id"
                  :label="`${classroom.grade_label} · ${classroom.name}`"
                  :value="classroom.id"
                />
              </el-select>
            </el-form-item>
            <div v-else class="detail-item" style="margin-bottom: 16px;">
              <div class="muted">管理员态账号默认拥有全校治理视图，不单独限制到具体班级。</div>
            </div>
            <div class="detail-item" style="margin-bottom: 16px;">
              <div class="muted">
                平台管理员可以维护管理员态账号；学校管理员本轮先只维护普通教师账号，避免权限扩散。
              </div>
            </div>
            <div class="inline-actions">
              <el-button plain @click="resetTeacherForm">新建空白账号</el-button>
              <el-button type="primary" :loading="savingTeacher" @click="saveTeacherAccount">保存账号</el-button>
            </div>
          </el-form>
        </div>
      </section>

      <section class="page-grid page-grid--two">
        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Resource Taxonomy</div>
          <h2 class="section-heading">资源分类治理</h2>
          <p class="muted" style="margin-bottom: 16px;">
            统一维护当前学校的资源分类，教师上传时会直接使用这里的分类体系。
          </p>
          <div v-if="overview.resource_categories.length > 0" class="detail-list">
            <div
              v-for="category in overview.resource_categories"
              :key="category.id"
              class="detail-item"
              style="display: grid; gap: 10px;"
            >
              <div class="inline-actions" style="justify-content: space-between;">
                <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
                  <el-tag :type="category.active ? 'success' : 'info'">{{ category.active ? '启用中' : '已停用' }}</el-tag>
                  <el-tag>排序 {{ category.sort_order }}</el-tag>
                  <strong>{{ category.name }}</strong>
                </div>
                <el-button
                  size="small"
                  :type="category.active ? 'warning' : 'success'"
                  plain
                  :loading="togglingResourceCategoryId === category.id"
                  @click="updateResourceCategoryStatus(category, !category.active)"
                >
                  {{ category.active ? '停用分类' : '重新启用' }}
                </el-button>
              </div>
              <div class="muted">{{ category.description || '当前分类暂无描述。' }}</div>
            </div>
          </div>
          <div v-else class="empty-state">当前学校还没有资源分类，请先在右侧创建。</div>
        </div>

        <div class="surface-card" style="padding: 24px;">
          <div class="section-kicker">Category Editor</div>
          <h2 class="section-heading">新建资源分类</h2>
          <el-form label-position="top">
            <div class="page-grid page-grid--two">
              <el-form-item label="分类名称">
                <el-input v-model="resourceCategoryForm.name" placeholder="例如 项目案例" />
              </el-form-item>
              <el-form-item label="排序">
                <el-input-number v-model="resourceCategoryForm.sort_order" class="full-width" :min="1" :max="999" />
              </el-form-item>
            </div>
            <el-form-item label="分类说明">
              <el-input
                v-model="resourceCategoryForm.description"
                type="textarea"
                :rows="4"
                maxlength="255"
                show-word-limit
                placeholder="说明教师在什么场景下应使用这个分类"
              />
            </el-form-item>
            <div class="inline-actions">
              <el-button plain @click="resetResourceCategoryForm">清空表单</el-button>
              <el-button type="primary" :loading="creatingResourceCategory" @click="createResourceCategory">
                创建分类
              </el-button>
            </div>
          </el-form>
        </div>
      </section>

      <section class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Student Assignment</div>
        <h2 class="section-heading">学生编班</h2>
        <p class="muted" style="margin-bottom: 18px;">这是当前学校的学生名册与班级归属。支持在不离开治理工作台的情况下做班级调整。</p>
        <div class="detail-item" style="display: grid; gap: 14px; margin-bottom: 18px;">
          <div class="section-kicker">Student Import</div>
          <div class="page-grid page-grid--two">
            <el-form-item label="导入到班级" style="margin-bottom: 0;">
              <el-select v-model="importForm.classroom_id" class="full-width" placeholder="请选择班级">
                <el-option
                  v-for="classroom in overview.classrooms"
                  :key="classroom.id"
                  :label="`${classroom.grade_label} · ${classroom.name}`"
                  :value="classroom.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="默认密码" style="margin-bottom: 0;">
              <el-input v-model="importForm.default_password" placeholder="未填写第三列密码时使用" />
            </el-form-item>
          </div>
          <el-form-item label="批量导入内容" style="margin-bottom: 0;">
            <el-input
              v-model="importForm.rows_text"
              type="textarea"
              :rows="5"
              placeholder="每行一名学生，支持逗号或 Tab 分隔：学号,姓名,密码"
            />
          </el-form-item>
          <el-form-item label="学生一键重置密码" style="margin-bottom: 0;">
            <el-input v-model="studentResetForm.new_password" placeholder="点击表格中的重置密码按钮时使用" />
          </el-form-item>
          <div class="inline-actions">
            <el-button type="primary" :loading="importingStudents" @click="importStudents">
              批量导入学生
            </el-button>
          </div>
        </div>
        <el-table :data="overview.students" style="width: 100%;">
          <el-table-column prop="display_name" label="姓名" min-width="120" />
          <el-table-column prop="username" label="学号" min-width="120" />
          <el-table-column label="当前班级" min-width="160">
            <template #default="{ row }">
              <span>{{ row.classroom_name || '未分配' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="目标班级" min-width="220">
            <template #default="{ row }">
              <el-select v-model="assignmentForms[row.id].classroom_id" class="full-width" placeholder="请选择班级">
                <el-option
                  v-for="classroom in overview.classrooms"
                  :key="classroom.id"
                  :label="`${classroom.grade_label} · ${classroom.name}`"
                  :value="classroom.id"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.active ? 'success' : 'info'">{{ row.active ? '在用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="320">
            <template #default="{ row }">
              <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :loading="assigningStudentId === row.id"
                  @click="assignStudent(row.id)"
                >
                  更新编班
                </el-button>
                <el-button
                  size="small"
                  plain
                  :loading="resettingStudentId === row.id"
                  @click="resetStudentPassword(row.id)"
                >
                  重置密码
                </el-button>
                <el-button
                  size="small"
                  :type="row.active ? 'danger' : 'success'"
                  plain
                  :loading="togglingStudentId === row.id"
                  @click="updateStudentStatus(row.id, !row.active)"
                >
                  {{ row.active ? '停用账号' : '启用账号' }}
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
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
