<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import PortalLayout from '../../layouts/PortalLayout.vue'
import { useSession } from '../../composables/useSession'

type NavItem = {
  label: string
  to: string
  caption?: string
}

type NavSection = {
  title: string
  items: NavItem[]
}

const route = useRoute()
const { sessionState } = useSession()

const isAdmin = computed(
  () => sessionState.value?.role === 'school_admin' || sessionState.value?.role === 'platform_admin',
)

const topNavItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { label: '总览看板', to: '/teacher/dashboard' },
    { label: '签到分析', to: '/teacher/attendance' },
    { label: '作业批改', to: '/teacher/submissions' },
    { label: '课程发布', to: '/teacher/courses' },
    { label: 'AI 副驾', to: '/teacher/copilot' },
    { label: '资源中心', to: '/teacher/resources' },
  ]

  if (isAdmin.value) {
    items.push({ label: '治理后台', to: '/teacher/admin' })
  }
  return items
})

const routeCopy = computed(() => {
  switch (route.name) {
    case 'teacher-attendance':
      return {
        title: '签到分析',
        subtitle: '这一页只保留签到分析和风险提示，点进二级路径再处理具体点名明细。',
      }
    case 'teacher-attendance-session':
      return {
        title: '签到明细',
        subtitle: '进入具体课堂会话后，再逐条处理签到、在线状态与求助信息。',
      }
    case 'teacher-submissions':
      return {
        title: '作业总览',
        subtitle: '先看提交量、待批改数量和队列概况，再进入单份作品详情执行批改。',
      }
    case 'teacher-submission-detail':
      return {
        title: '批改详情',
        subtitle: '单独进入某份作品的全文、求助历史和批改工作位，避免所有信息堆在一页。',
      }
    case 'teacher-courses':
    case 'teacher-course-detail':
      return {
        title: '课程发布',
        subtitle: '课程与活动拆开管理，一个课程可以维护多个活动、调整顺序并上传交互网页任务。',
      }
    case 'teacher-copilot':
      return {
        title: '教师 AI 副驾',
        subtitle: 'AI 草稿、教学反思和课堂建议集中在独立模块，减少与课堂操作互相打扰。',
      }
    case 'teacher-resources':
      return {
        title: '资源中心',
        subtitle: '课堂资源上传、筛选和启停单独管理，不再挤在课堂控制台里。',
      }
    case 'teacher-admin':
      return {
        title: '治理后台',
        subtitle: '管理员能力并入教师入口，但治理页面仍然作为独立子页面处理。',
      }
    default:
      return {
        title: '教师工作台',
        subtitle: '总览页先看课堂雷达、班级风险和发课入口，再分模块进入签到、批改或治理页面。',
      }
  }
})

const sideNavSections = computed(() => {
  const sections: NavSection[] = [{ title: '主导航', items: topNavItems.value }]

  if (route.path.startsWith('/teacher/attendance')) {
    sections.push({
      title: '签到子页',
      items: [
        { label: '签到分析', to: '/teacher/attendance', caption: '先看统计' },
        {
          label: '当前会话详情',
          to:
            route.name === 'teacher-attendance-session'
              ? route.fullPath
              : '/teacher/attendance',
          caption: '进入点名',
        },
      ],
    })
  }

  if (route.path.startsWith('/teacher/submissions')) {
    sections.push({
      title: '作业子页',
      items: [
        { label: '提交总览', to: '/teacher/submissions', caption: '先看队列' },
        {
          label: '当前批改详情',
          to:
            route.name === 'teacher-submission-detail'
              ? route.fullPath
              : '/teacher/submissions',
          caption: '进入作品',
        },
      ],
    })
  }

  if (route.path.startsWith('/teacher/courses')) {
    sections.push({
      title: '课程子页',
      items: [
        { label: '课程列表', to: '/teacher/courses', caption: '全部课程' },
        {
          label: '当前课程编辑',
          to:
            route.name === 'teacher-course-detail'
              ? route.fullPath
              : '/teacher/courses',
          caption: '活动编辑',
        },
      ],
    })
  }

  return sections
})
</script>

<template>
  <PortalLayout
    :role-label="isAdmin ? '教师管理员工作区' : '教师工作区'"
    :title="routeCopy.title"
    :subtitle="routeCopy.subtitle"
    :school-name="sessionState?.school_name ?? '加载中...'"
    :user-name="sessionState?.display_name ?? '教师'"
    :top-nav-items="topNavItems"
    :side-nav-sections="sideNavSections"
    :header-pills="isAdmin ? ['管理员权限已启用'] : []"
  >
    <RouterView />
  </PortalLayout>
</template>
