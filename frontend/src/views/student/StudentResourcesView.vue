<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiClient, downloadApiFile } from '../../api/client'
import type { StudentResourcesResponse } from '../../api/types'

const data = ref<StudentResourcesResponse | null>(null)
const loading = ref(true)
const error = ref('')
const query = ref('')

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

async function loadResources() {
  loading.value = true
  try {
    const response = await apiClient.get<StudentResourcesResponse>('/student/resources')
    data.value = response.data
    error.value = ''
  } catch (requestError) {
    console.error(requestError)
    error.value = '暂时无法加载资源列表。'
  } finally {
    loading.value = false
  }
}

async function downloadResource(resourceId: number, filename: string) {
  await downloadApiFile(`/student/resources/${resourceId}/download`, filename)
}

onMounted(() => {
  void loadResources()
})
</script>

<template>
  <el-alert v-if="error" :closable="false" type="warning" :title="error" />
  <el-skeleton v-else-if="loading" :rows="8" animated />

  <div v-else-if="data" class="stack">
    <section class="surface-card" style="padding: 24px;">
      <div class="section-kicker">Resource Center</div>
      <h2 class="section-heading">学习资源</h2>
      <el-input v-model="query" clearable placeholder="搜索资源标题、文件名或说明" style="margin-bottom: 18px;" />

      <div v-if="filteredResources.length > 0" class="detail-list">
        <div v-for="resource in filteredResources" :key="resource.id" class="detail-item" style="display: grid; gap: 10px;">
          <div class="inline-actions" style="justify-content: space-between;">
            <div class="inline-actions" style="justify-content: flex-start; flex-wrap: wrap;">
              <el-tag type="success">{{ resource.classroom_name || '学校共享' }}</el-tag>
              <el-tag v-if="resource.category_name" type="warning">{{ resource.category_name }}</el-tag>
              <strong>{{ resource.title }}</strong>
            </div>
            <span class="muted">{{ resource.original_filename }}</span>
          </div>
          <div v-if="resource.description">{{ resource.description }}</div>
          <div class="muted">{{ resource.file_size_label }} · {{ resource.uploaded_at }} · Downloads {{ resource.download_count }}</div>
          <div class="inline-actions">
            <el-button size="small" plain @click="downloadResource(resource.id, resource.original_filename)">下载资源</el-button>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">当前没有可用的学习资源。</div>
    </section>
  </div>
</template>
