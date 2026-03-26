import { createRouter, createWebHistory } from 'vue-router'
import type { UserRole } from '../api/types'
import { useSession } from '../composables/useSession'

const StudentLoginView = () => import('../views/login/StudentLoginView.vue')
const TeacherLoginView = () => import('../views/login/TeacherLoginView.vue')
const StudentPortalView = () => import('../views/student/StudentPortalView.vue')
const StudentDashboardView = () => import('../views/student/StudentDashboardView.vue')
const StudentAttendanceView = () => import('../views/student/StudentAttendanceView.vue')
const StudentAssignmentsOverviewView = () => import('../views/student/StudentAssignmentsOverviewView.vue')
const StudentAssignmentWorkbenchView = () => import('../views/student/StudentAssignmentWorkbenchView.vue')
const StudentActivityDetailView = () => import('../views/student/StudentActivityDetailView.vue')
const StudentResourcesView = () => import('../views/student/StudentResourcesView.vue')
const TeacherPortalView = () => import('../views/teacher/TeacherPortalView.vue')
const TeacherDashboardView = () => import('../views/teacher/TeacherDashboardView.vue')
const TeacherAttendanceOverviewView = () => import('../views/teacher/TeacherAttendanceOverviewView.vue')
const TeacherAttendanceSessionDetailView = () => import('../views/teacher/TeacherAttendanceSessionDetailView.vue')
const TeacherSubmissionsOverviewView = () => import('../views/teacher/TeacherSubmissionsOverviewView.vue')
const TeacherSubmissionDetailView = () => import('../views/teacher/TeacherSubmissionDetailView.vue')
const TeacherCoursesView = () => import('../views/teacher/TeacherCoursesView.vue')
const TeacherCopilotView = () => import('../views/teacher/TeacherCopilotView.vue')
const TeacherResourcesView = () => import('../views/teacher/TeacherResourcesView.vue')
const TeacherAdminView = () => import('../views/teacher/TeacherAdminView.vue')

const teacherRoles: UserRole[] = ['teacher', 'school_admin', 'platform_admin']
const adminRoles: UserRole[] = ['school_admin', 'platform_admin']

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: StudentLoginView },
    { path: '/teacher/login', component: TeacherLoginView },
    { path: '/admin/login', redirect: '/teacher/login' },
    {
      path: '/student',
      component: StudentPortalView,
      meta: { requiresAuth: true, roles: ['student'] satisfies UserRole[] },
      children: [
        { path: '', redirect: '/student/home' },
        { path: 'home', name: 'student-home', component: StudentDashboardView },
        { path: 'attendance', name: 'student-attendance', component: StudentAttendanceView },
        { path: 'assignments', name: 'student-assignments', component: StudentAssignmentsOverviewView },
        { path: 'assignments/workbench', name: 'student-assignment-workbench', component: StudentAssignmentWorkbenchView },
        { path: 'assignments/activity/:activityId', name: 'student-activity-detail', component: StudentActivityDetailView },
        { path: 'resources', name: 'student-resources', component: StudentResourcesView },
      ],
    },
    {
      path: '/teacher',
      component: TeacherPortalView,
      meta: { requiresAuth: true, roles: teacherRoles },
      children: [
        { path: '', redirect: '/teacher/dashboard' },
        { path: 'dashboard', name: 'teacher-dashboard', component: TeacherDashboardView },
        { path: 'attendance', name: 'teacher-attendance', component: TeacherAttendanceOverviewView },
        {
          path: 'attendance/sessions/:sessionId',
          name: 'teacher-attendance-session',
          component: TeacherAttendanceSessionDetailView,
        },
        { path: 'submissions', name: 'teacher-submissions', component: TeacherSubmissionsOverviewView },
        {
          path: 'submissions/:submissionId',
          name: 'teacher-submission-detail',
          component: TeacherSubmissionDetailView,
        },
        { path: 'courses', name: 'teacher-courses', component: TeacherCoursesView },
        { path: 'courses/:courseId', name: 'teacher-course-detail', component: TeacherCoursesView },
        { path: 'copilot', name: 'teacher-copilot', component: TeacherCopilotView },
        { path: 'resources', name: 'teacher-resources', component: TeacherResourcesView },
        {
          path: 'admin',
          name: 'teacher-admin',
          component: TeacherAdminView,
          meta: { requiresAuth: true, roles: adminRoles },
        },
      ],
    },
    { path: '/teacher/console', redirect: '/teacher/dashboard' },
    { path: '/admin/overview', redirect: '/teacher/admin' },
  ],
})

router.beforeEach((to) => {
  const { sessionState } = useSession()
  const session = sessionState.value
  const allowedRoles = to.meta.roles as UserRole[] | undefined

  if (to.meta.requiresAuth && !session) {
    if (allowedRoles?.some((role) => teacherRoles.includes(role))) {
      return '/teacher/login'
    }
    return '/'
  }

  if (allowedRoles && session && !allowedRoles.includes(session.role)) {
    if (teacherRoles.includes(session.role)) {
      return '/teacher/dashboard'
    }
    if (session.role === 'student') {
      return '/student/home'
    }
    return '/'
  }

  return true
})

export default router
