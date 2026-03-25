import axios from 'axios'
import type { SessionInfo } from './types'

export const SESSION_STORAGE_KEY = 'learnsite2-session'
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})

export function readStoredSession(): SessionInfo | null {
  const raw = localStorage.getItem(SESSION_STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as SessionInfo
  } catch {
    localStorage.removeItem(SESSION_STORAGE_KEY)
    return null
  }
}

apiClient.interceptors.request.use((config) => {
  const session = readStoredSession()
  if (session?.token) {
    config.headers.Authorization = `Bearer ${session.token}`
  }
  return config
})

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  if (API_BASE_URL.startsWith('http')) {
    return `${API_BASE_URL}${normalizedPath}`
  }
  return `${window.location.origin}${API_BASE_URL}${normalizedPath}`
}
