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

const topNavItems: NavItem[] = [
  { label: '学习总览', to: '/student/home' },
  { label: '课堂签到', to: '/student/attendance' },
  { label: '作业任务', to: '/student/assignments' },
  { label: '资源中心', to: '/student/resources' },
]

const routeCopy = computed(() => {
  switch (route.name) {
    case 'student-attendance':
      return {
        title: '课堂签到',
        subtitle: '先看当前签到状态，再进入历史记录了解自己的课堂参与情况。',
      }
    case 'student-assignments':
      return {
        title: '作业总览',
        subtitle: '这里先看任务概况、活动列表和提交状态，进入二级页再进行编辑或交互操作。',
      }
    case 'student-assignment-workbench':
      return {
        title: '书面提交工作台',
        subtitle: '在独立作业页完成文字作品保存、提交与历史回看，不再与其他模块混在一起。',
      }
    case 'student-activity-detail':
      return {
        title: '活动详情',
        subtitle: '阅读活动说明，打开交互网页任务，并把产生的数据直接提交到后台。',
      }
    case 'student-resources':
      return {
        title: '资源中心',
        subtitle: '统一浏览教师发布的资料，不与签到、作业流程混排。',
      }
    default:
      return {
        title: '学习总览',
        subtitle: '先看本节课堂的进度、待办和提醒，再按模块进入签到或作业详情。',
      }
  }
})

const sideNavSections = computed(() => {
  const sections: NavSection[] = [{ title: '主导航', items: topNavItems }]

  if (route.path.startsWith('/student/assignments')) {
    sections.push({
      title: '作业入口',
      items: [
        { label: '作业总览', to: '/student/assignments', caption: '先看分析' },
        { label: '书面提交', to: '/student/assignments/workbench', caption: '进入编辑' },
      ],
    })
    if (route.name === 'student-activity-detail' && typeof route.params.activityId === 'string') {
      sections.push({
        title: '当前活动',
        items: [
          {
            label: `活动 ${route.params.activityId}`,
            to: route.fullPath,
            caption: '交互任务详情',
          },
        ],
      })
    }
  }

  return sections
})
</script>

<template>
  <PortalLayout
    role-label="学生学习门户"
    :title="routeCopy.title"
    :subtitle="routeCopy.subtitle"
    :school-name="sessionState?.school_name ?? '加载中...'"
    :user-name="sessionState?.display_name ?? '学生'"
    :top-nav-items="topNavItems"
    :side-nav-sections="sideNavSections"
  >
    <RouterView />
  </PortalLayout>
</template>
