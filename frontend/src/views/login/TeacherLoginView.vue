<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '../../api/client'
import type { BootstrapResponse, LoginResponse } from '../../api/types'
import { useSession } from '../../composables/useSession'
import { applyTheme } from '../../composables/useTheme'
import AuthLayout from '../../layouts/AuthLayout.vue'

const router = useRouter()
const { setSession } = useSession()

const bootstrap = ref<BootstrapResponse | null>(null)
const loading = ref(false)
const loadError = ref('')

const form = reactive({
  schoolCode: '',
  username: 'kylin',
  password: '222221',
})

async function loadBootstrap() {
  loadError.value = ''
  try {
    const { data } = await apiClient.get<BootstrapResponse>('/bootstrap')
    bootstrap.value = data
    form.schoolCode = data.schools[0]?.code ?? ''
    loadError.value = ''
  } catch (error) {
    loadError.value = '暂时无法加载学校列表。请检查 FastAPI 服务、前端 API 地址，或点击重试。'
    console.error(error)
  }
}

async function submit() {
  loading.value = true
  try {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', {
      role: 'teacher',
      school_code: form.schoolCode,
      username: form.username,
      password: form.password,
    })
    setSession(data.session)
    applyTheme(data.session.theme_style)
    ElMessage.success(data.session.role === 'teacher' ? '教师登录成功' : '教师管理员登录成功')
    await router.push(data.redirect_path)
  } catch (error) {
    ElMessage.error('教师 / 管理登录失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadBootstrap()
})
</script>

<template>
  <AuthLayout
    eyebrow="教师 / 管理入口"
    title="教师和管理员共用一个入口，但管理员默认带着教师工作台进入系统。"
    description="现在教师与管理员通过同一个入口登录。管理员不再有独立登录页，而是以“教师管理员权限态”进入，先落到教师控制台，再在同一工作台中使用治理能力。"
    :highlights="[
      '课堂实时雷达采用学生心跳上报 + 教师 SSE 订阅的轻量实时链路。',
      '教师 AI 副驾只生成草稿，不会绕过教师直接发布。',
      '管理员登录已经合并到教师入口，并在同一工作区内附带治理权限。'
    ]"
    :role-links="[
      { label: '学生登录', to: '/' },
      { label: '教师 / 管理登录', to: '/teacher/login' }
    ]"
  >
    <div class="stack">
      <div>
        <div class="section-kicker">Teacher / Admin Login</div>
        <h2 class="section-heading">进入教师工作台或教师管理员权限态</h2>
        <p class="muted">
          测试账号：实验学校 A 教师 `kylin / 222221`、管理员 `admin / 222221`；
          未来学校 B 教师 `linhua / 222221`、管理员 `adminb / 222221`；
          平台管理员 `platform / 222221`。
        </p>
      </div>

      <div v-if="loadError" class="stack" style="gap: 12px;">
        <el-alert :closable="false" type="warning" :title="loadError" />
        <el-button plain @click="loadBootstrap">重新加载学校列表</el-button>
      </div>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="学校">
          <el-select v-model="form.schoolCode" class="full-width" placeholder="请选择学校">
            <el-option
              v-for="school in bootstrap?.schools ?? []"
              :key="school.code"
              :label="`${school.name} · ${school.city}`"
              :value="school.code"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="教师 / 管理账号">
          <el-input v-model="form.username" placeholder="请输入教师或管理员账号" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input v-model="form.password" placeholder="请输入密码" show-password />
        </el-form-item>

        <el-button class="full-width" type="primary" size="large" :loading="loading" @click="submit">
          进入教师 / 管理工作区
        </el-button>
      </el-form>

      <div class="auth-highlight">
        <div style="font-weight: 800;">统一入口，统一工作区</div>
        <div class="muted">上课、备课、签到、作品、学生管理依然是教师主干；管理员则在同一入口登录后附带治理、迁移和多学校权限。</div>
      </div>
    </div>
  </AuthLayout>
</template>
