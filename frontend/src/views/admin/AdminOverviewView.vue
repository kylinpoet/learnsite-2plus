<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  void router.replace('/teacher/console')
})
</script>

<template>
  <div class="empty-state">管理员能力已合并到教师控制台，正在跳转...</div>
</template>
