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

const loading = ref(false)
const bootstrap = ref<BootstrapResponse | null>(null)
const loadError = ref('')

const form = reactive({
  schoolCode: '',
  username: '240101',
  password: '12345',
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
      role: 'student',
      school_code: form.schoolCode,
      username: form.username,
      password: form.password,
    })
    setSession(data.session)
    applyTheme(data.session.theme_style)
    ElMessage.success('学生登录成功')
    await router.push(data.redirect_path)
  } catch (error) {
    ElMessage.error('登录失败，请检查学校、账号和密码')
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
    eyebrow="学生入口"
    title="进入课堂，不只是进入一个登录框。"
    description="首页默认就是学生登录页。当前版本按多学校模式设计，但首屏仍然强调“这节课我现在该做什么”，而不是传统门户目录。"
    :highlights="[
      '默认字体统一使用 Noto Sans SC，不使用 ZCOOL XiaoWei 这类特殊字体。',
      '主题切换是风格切换，不是亮暗模式切换。',
      '本地开发后端使用 FastAPI + SQLite，后续可平滑切到正式数据库。'
    ]"
    :role-links="[
      { label: '学生登录', to: '/' },
      { label: '教师 / 管理登录', to: '/teacher/login' }
    ]"
  >
    <div class="stack">
      <div>
        <div class="section-kicker">Student Login</div>
        <h2 class="section-heading">学生进入课堂</h2>
        <p class="muted">测试账号：实验学校 A `240101 / 12345`，未来学校 B `250201 / 12345`。建议先选择学校，再进入学生首页。</p>
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

        <el-form-item label="学号">
          <el-input v-model="form.username" placeholder="请输入学号" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input v-model="form.password" placeholder="请输入密码" show-password />
        </el-form-item>

        <el-button class="full-width" type="primary" size="large" :loading="loading" @click="submit">
          进入学生首页
        </el-button>
      </el-form>

      <div class="auth-highlight">
        <div style="font-weight: 800;">多学校入口说明</div>
        <div class="muted">登录后会进入学校作用域内的数据视图，不同学校默认主题和文案可以独立配置。</div>
      </div>
    </div>
  </AuthLayout>
</template>
