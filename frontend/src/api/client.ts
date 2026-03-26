import axios from 'axios'
import type { SessionInfo } from './types'

export const SESSION_STORAGE_KEY = 'learnsite2-session'

function resolveApiBaseUrl(): string {
  const configuredValue = import.meta.env.VITE_API_BASE_URL?.trim()
  if (!configuredValue || configuredValue.startsWith('/')) {
    return configuredValue ?? '/api'
  }

  if (!import.meta.env.DEV) {
    return configuredValue
  }

  try {
    const url = new URL(configuredValue)
    const isLocalDevBackend =
      ['127.0.0.1', 'localhost'].includes(url.hostname) && url.port === '8001'
    if (isLocalDevBackend) {
      return '/api'
    }
  } catch {
    return configuredValue
  }

  return configuredValue
}

const API_BASE_URL = resolveApiBaseUrl()

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})

function resolveDownloadFilename(contentDisposition: string | undefined, fallbackFilename: string): string {
  if (!contentDisposition) {
    return fallbackFilename
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }

  const plainMatch = contentDisposition.match(/filename=\"?([^\";]+)\"?/i)
  return plainMatch?.[1] ?? fallbackFilename
}

export function readStoredSession(): SessionInfo | null {
  const raw = localStorage.getItem(SESSION_STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    const session = JSON.parse(raw) as SessionInfo
    const expiresAt = Date.parse(session.expires_at)
    if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
      clearStoredSession()
      return null
    }
    return session
  } catch {
    clearStoredSession()
    return null
  }
}

export function clearStoredSession() {
  localStorage.removeItem(SESSION_STORAGE_KEY)
}

apiClient.interceptors.request.use((config) => {
  const session = readStoredSession()
  if (session?.token) {
    config.headers.Authorization = `Bearer ${session.token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status as number | undefined
    if (status === 401) {
      clearStoredSession()
      const currentPath = window.location.pathname
      const isTeacherArea = currentPath.startsWith('/teacher') || currentPath.startsWith('/admin')
      const isStudentArea = currentPath.startsWith('/student')
      const isProtectedArea = isStudentArea || isTeacherArea
      const loginPath = isTeacherArea ? '/teacher/login' : '/'
      if (isProtectedArea && currentPath !== loginPath) {
        window.location.assign(loginPath)
      }
    }
    return Promise.reject(error)
  },
)

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  if (API_BASE_URL.startsWith('http')) {
    return `${API_BASE_URL}${normalizedPath}`
  }
  return `${window.location.origin}${API_BASE_URL}${normalizedPath}`
}

export async function downloadApiFile(path: string, fallbackFilename: string) {
  const response = await apiClient.get<Blob>(path, {
    responseType: 'blob',
  })
  const contentDisposition = response.headers['content-disposition'] as string | undefined
  const filename = resolveDownloadFilename(contentDisposition, fallbackFilename)
  const blobUrl = window.URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = blobUrl
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => {
    window.URL.revokeObjectURL(blobUrl)
  }, 0)
}
