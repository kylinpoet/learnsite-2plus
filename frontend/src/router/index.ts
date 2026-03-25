import { createRouter, createWebHistory } from 'vue-router'
import type { UserRole } from '../api/types'
import { useSession } from '../composables/useSession'
import AdminOverviewView from '../views/admin/AdminOverviewView.vue'
import StudentLoginView from '../views/login/StudentLoginView.vue'
import TeacherLoginView from '../views/login/TeacherLoginView.vue'
import StudentHomeView from '../views/student/StudentHomeView.vue'
import TeacherConsoleView from '../views/teacher/TeacherConsoleView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: StudentLoginView },
    { path: '/teacher/login', component: TeacherLoginView },
    { path: '/admin/login', redirect: '/teacher/login' },
    {
      path: '/student/home',
      component: StudentHomeView,
      meta: { requiresAuth: true, roles: ['student'] satisfies UserRole[] },
    },
    {
      path: '/teacher/console',
      component: TeacherConsoleView,
      meta: {
        requiresAuth: true,
        roles: ['teacher', 'school_admin', 'platform_admin'] satisfies UserRole[],
      },
    },
    {
      path: '/admin/overview',
      component: AdminOverviewView,
      meta: {
        requiresAuth: true,
        roles: ['school_admin', 'platform_admin'] satisfies UserRole[],
      },
    },
  ],
})

router.beforeEach((to) => {
  const { sessionState } = useSession()
  const session = sessionState.value
  const allowedRoles = to.meta.roles as UserRole[] | undefined

  if (to.meta.requiresAuth && !session) {
    if (
      allowedRoles?.includes('teacher') ||
      allowedRoles?.includes('school_admin') ||
      allowedRoles?.includes('platform_admin')
    ) {
      return '/teacher/login'
    }
    return '/'
  }

  if (allowedRoles && session && !allowedRoles.includes(session.role)) {
    if (
      session.role === 'teacher' ||
      session.role === 'school_admin' ||
      session.role === 'platform_admin'
    ) {
      return '/teacher/console'
    }
    if (session.role === 'student') {
      return '/student/home'
    }
    return '/'
  }

  return true
})

export default router
