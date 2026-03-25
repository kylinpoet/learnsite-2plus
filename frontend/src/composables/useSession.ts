import { computed, ref } from 'vue'
import type { LoginRole, SessionInfo } from '../api/types'
import { SESSION_STORAGE_KEY, readStoredSession } from '../api/client'

const sessionState = ref<SessionInfo | null>(readStoredSession())

export function useSession() {
  const isAuthenticated = computed(() => Boolean(sessionState.value?.token))

  function setSession(session: SessionInfo) {
    sessionState.value = session
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
  }

  function clearSession() {
    sessionState.value = null
    localStorage.removeItem(SESSION_STORAGE_KEY)
  }

  return {
    sessionState,
    isAuthenticated,
    setSession,
    clearSession,
  }
}

export function getDefaultRouteForRole(role: LoginRole | SessionInfo['role']): string {
  if (role === 'student') {
    return '/student/home'
  }
  if (role === 'teacher' || role === 'school_admin' || role === 'platform_admin') {
    return '/teacher/console'
  }
  return '/'
}
