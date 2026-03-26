<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiClient, downloadApiFile } from '../../api/client'
import type { ResourceAudience, TeacherResourcesResponse } from '../../api/types'

const data = ref<TeacherResourcesResponse | null>(null)
const loading = ref(true)
const error = ref('')
const uploading = ref(false)
const selectedFile = ref<File | null>(null)

const query = ref('')

const resourceForm = reactive<{
  title: string
  description: string
  audience: ResourceAudience
  category_id: number | null
  classroom_id: number | null
}>({
  title: '',
  description: '',
  audience: 'student',
  category_id: null,
  classroom_id: null,
})

const filteredResources = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return (data.value?.resources ?? []).filter((resource) => {
    if (!keyword) {
      return true
    }
    return (
      resource.title.toLowerCase().includes(keyword) ||
      resource.original_filename.toLowerCase().includes(keyword) ||
      (resource.description ?? '').toLowerCase().includes(keyword)
    )
  })
})

function syncDefaults() {
  if (!data.value) {
    return
  }
  resourceForm.category_id = data.value.resource_categories[0]?.id ?? null
  resourceForm.classroom_id = data.value.managed_classrooms[0]?.id ?? null
}

async function loadResources() {
  loading.value = true
  try {
    const response = await apiClient.get<TeacherResourcesResponse>('/teacher/resources/overview')
    data.value = response.data
    syncDefaults()
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载资源模块。'
  } finally {
    loading.value = false
  }
}

function captureFile(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
}

async function uploadResource() {
  if (!selectedFile.value || !resourceForm.title.trim()) {
    ElMessage.warning('请先填写标题并选择文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('title', resourceForm.title)
    formData.append('description', resourceForm.description)
    formData.append('audience', resourceForm.audience)
    if (resourceForm.category_id) {
      formData.append('category_id', String(resourceForm.category_id))
    }
    if (resourceForm.classroom_id) {
      formData.append('classroom_id', String(resourceForm.classroom_id))
    }
    formData.append('upload', selectedFile.value)
    await apiClient.post('/teacher/resources', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success('资源已上传')
    resourceForm.title = ''
    resourceForm.description = ''
    selectedFile.value = null
    await loadResources()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('资源上传失败')
  } finally {
    uploading.value = false
  }
}

async function toggleResource(resourceId: number, active: boolean) {
  try {
    await apiClient.post(`/teacher/resources/${resourceId}/status`, { active })
    ElMessage.success(active ? '资源已启用' : '资源已停用')
    await loadResources()
  } catch (requestError) {
    console.error(requestError)
    ElMessage.error('资源状态更新失败')
  }
}

async function downloadResource(resourceId: number, filename: string) {
  await downloadApiFile(`/teacher/resources/${resourceId}/download`, filename)
}

onMounted(() => {
  void loadResources()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="10" animated />

  <div v-else-if="data" class="stack">
    <section class="page-grid page-grid--two">
      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Upload</div>
        <h2 class="section-heading">上传资源</h2>
        <el-form label-position="top">
          <el-form-item label="资源标题">
            <el-input v-model="resourceForm.title" />
          </el-form-item>
          <div class="page-grid page-grid--two">
            <el-form-item label="资源分类">
              <el-select v-model="resourceForm.category_id" class="full-width">
                <el-option v-for="category in data.resource_categories" :key="category.id" :label="category.name" :value="category.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="所属班级">
              <el-select v-model="resourceForm.classroom_id" class="full-width" clearable>
                <el-option
                  v-for="classroom in data.managed_classrooms"
                  :key="classroom.id"
                  :label="`${classroom.grade_label} · ${classroom.name}`"
                  :value="classroom.id"
                />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="说明">
            <el-input v-model="resourceForm.description" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="上传文件">
            <input type="file" @change="captureFile" />
          </el-form-item>
          <div class="inline-actions">
            <el-button type="primary" :loading="uploading" @click="uploadResource">上传资源</el-button>
          </div>
        </el-form>
      </div>

      <div class="surface-card" style="padding: 24px;">
        <div class="section-kicker">Search</div>
        <h2 class="section-heading">资源筛选</h2>
        <el-input v-model="query" clearable placeholder="搜索标题、文件名或说明" />
      </div>
    </section>

    <section class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Library</div>
      <h2 class="section-heading">已上传资源</h2>
      <div v-if="filteredResources.length > 0" class="detail-list">
        <div v-for="resource in filteredResources" :key="resource.id" class="detail-item" style="display: grid; gap: 10px;">
          <div class="inline-actions" style="justify-content: space-between;">
            <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
              <el-tag :type="resource.active ? 'success' : 'info'">{{ resource.active ? '启用中' : '已停用' }}</el-tag>
              <el-tag type="warning">{{ resource.category_name || '未分类' }}</el-tag>
              <strong>{{ resource.title }}</strong>
            </div>
            <span class="muted">{{ resource.original_filename }}</span>
          </div>
          <div class="muted">
            {{ resource.classroom_name ? `班级：${resource.classroom_name}` : '学校共享资源' }} · {{ resource.file_size_label }} ·
            上传者 {{ resource.uploaded_by_name }}
          </div>
          <div v-if="resource.description">{{ resource.description }}</div>
          <div class="inline-actions">
            <el-button size="small" plain @click="downloadResource(resource.id, resource.original_filename)">下载</el-button>
            <el-button size="small" plain @click="toggleResource(resource.id, !resource.active)">
              {{ resource.active ? '停用' : '启用' }}
            </el-button>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">当前没有匹配的资源。</div>
    </section>
  </div>
</template>
