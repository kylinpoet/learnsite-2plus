<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiClient } from '../../api/client'
import type { AdminOverviewResponse, SchoolSettingsUpdatePayload } from '../../api/types'
import { useSession } from '../../composables/useSession'
import { themeOptions } from '../../composables/useTheme'

const { sessionState, setSession } = useSession()

const overview = ref<AdminOverviewResponse | null>(null)
const loadError = ref('')
const saving = ref(false)
const loading = ref(false)
const selectedSchoolCode = ref('')
const schoolForm = reactive<SchoolSettingsUpdatePayload>({
  name: '',
  city: '',
  slogan: '',
  theme_style: 'workshop',
})

const showSchoolSwitcher = computed(() => (overview.value?.managed_schools.length ?? 0) > 1)

function requestParams() {
  return selectedSchoolCode.value ? { school_code: selectedSchoolCode.value } : undefined
}

function syncSchoolForm() {
  if (!overview.value) {
    return
  }
  schoolForm.name = overview.value.current_school.name
  schoolForm.city = overview.value.current_school.city
  schoolForm.slogan = overview.value.current_school.slogan
  schoolForm.theme_style = overview.value.current_school.theme_style
}

function applyOverview(data: AdminOverviewResponse) {
  overview.value = data
  selectedSchoolCode.value = data.current_school.code
  syncSchoolForm()
  loadError.value = ''
}

async function loadOverview() {
  loading.value = true
  try {
    const { data } = await apiClient.get<AdminOverviewResponse>('/admin/overview', {
      params: requestParams(),
    })
    applyOverview(data)
  } catch (requestError) {
    loadError.value = '学校配置加载失败，请确认管理员会话仍然有效。'
    console.error(requestError)
  } finally {
    loading.value = false
  }
}

async function handleSchoolSwitch() {
  await loadOverview()
}

async function saveSchoolSettings() {
  if (!schoolForm.name.trim() || !schoolForm.city.trim() || !schoolForm.slogan.trim()) {
    ElMessage.warning('请先填写学校名称、城市和登录页标语')
    return
  }

  saving.value = true
  try {
    const payload: SchoolSettingsUpdatePayload = {
      name: schoolForm.name.trim(),
      city: schoolForm.city.trim(),
      slogan: schoolForm.slogan.trim(),
      theme_style: schoolForm.theme_style,
    }
    const { data } = await apiClient.post<AdminOverviewResponse>('/admin/school-settings', payload, {
      params: requestParams(),
    })
    applyOverview(data)
    if (sessionState.value && sessionState.value.school_code === data.current_school.code) {
      setSession({
        ...sessionState.value,
        school_name: data.current_school.name,
        theme_style: data.current_school.theme_style,
      })
    }
    ElMessage.success('学校信息与默认主题已更新')
  } catch (requestError) {
    ElMessage.error('保存学校配置失败')
    console.error(requestError)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadOverview()
})
</script>

<template>
  <section class="surface-card" style="padding: 24px;">
    <div class="section-kicker">School Identity</div>
    <h2 class="section-heading">学校信息与默认主题</h2>
    <p class="muted" style="margin-bottom: 18px;">
      为当前学校维护门户名称、城市、登录页标语与默认风格。这里设置的是学校默认值，不会强制覆盖教师或学生手动切换过的主题偏好。
    </p>

    <el-alert v-if="loadError" type="warning" :closable="false" :title="loadError" style="margin-bottom: 16px;" />

    <template v-if="overview">
      <div v-if="showSchoolSwitcher" class="page-grid page-grid--two" style="margin-bottom: 16px;">
        <div class="stack" style="gap: 8px;">
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
        <div class="detail-item" style="display: grid; gap: 6px;">
          <div class="section-kicker">Current Scope</div>
          <div>
            {{ overview.current_school.name }} · {{ overview.current_school.city }} · {{ overview.current_school.code }}
          </div>
        </div>
      </div>

      <el-form label-position="top">
        <div class="page-grid page-grid--two">
          <el-form-item label="学校名称">
            <el-input v-model="schoolForm.name" maxlength="128" placeholder="例如：实验学校 A" />
          </el-form-item>
          <el-form-item label="所在城市">
            <el-input v-model="schoolForm.city" maxlength="64" placeholder="例如：上海" />
          </el-form-item>
        </div>

        <div class="page-grid page-grid--two">
          <el-form-item label="学校代码">
            <el-input :model-value="overview.current_school.code" disabled />
          </el-form-item>
          <el-form-item label="默认风格主题">
            <el-select v-model="schoolForm.theme_style" class="full-width">
              <el-option
                v-for="theme in themeOptions"
                :key="theme.id"
                :label="`${theme.name} · ${theme.description}`"
                :value="theme.id"
              />
            </el-select>
          </el-form-item>
        </div>

        <el-form-item label="登录页标语">
          <el-input
            v-model="schoolForm.slogan"
            maxlength="255"
            show-word-limit
            placeholder="例如：让课堂更清楚，让学习更有参与感"
          />
        </el-form-item>

        <div class="detail-item" style="margin-bottom: 16px;">
          <div class="muted">
            当前学校默认风格：{{ overview.current_school.theme_style }}。更新后，新登录的师生会优先看到这套学校默认风格。
          </div>
        </div>

        <div class="inline-actions">
          <el-button plain :disabled="loading" @click="syncSchoolForm">恢复当前值</el-button>
          <el-button plain :loading="loading" @click="loadOverview">重新加载</el-button>
          <el-button type="primary" :loading="saving" @click="saveSchoolSettings">保存学校配置</el-button>
        </div>
      </el-form>
    </template>

    <el-skeleton v-else :rows="4" animated />
  </section>
</template>
