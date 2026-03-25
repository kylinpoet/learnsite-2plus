import { createRouter, createWebHistory } from 'vue-router'
import type { UserRole } from '../api/types'
import { useSession } from '../composables/useSession'

const StudentLoginView = () => import('../views/login/StudentLoginView.vue')
const TeacherLoginView = () => import('../views/login/TeacherLoginView.vue')
const StudentHomeView = () => import('../views/student/StudentHomeView.vue')
const TeacherConsoleView = () => import('../views/teacher/TeacherConsoleView.vue')

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
      redirect: '/teacher/console',
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
