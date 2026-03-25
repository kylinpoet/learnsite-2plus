import { ref } from 'vue'
import type { ThemeStyle, ThemeStyleOption } from '../api/types'

const THEME_STORAGE_KEY = 'learnsite2-theme-style'

export const themeOptions: ThemeStyleOption[] = [
  { id: 'workshop', name: 'Classroom Workshop', description: '暖纸面、课堂感、任务舞台' },
  { id: 'material', name: 'Material Design', description: '结构清晰、层次明确、现代规范' },
  { id: 'natural', name: 'Natural', description: '大地色、有机感、自然温暖' },
]

function restoreTheme(): ThemeStyle {
  const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) as ThemeStyle | null
  if (savedTheme && themeOptions.some((theme) => theme.id === savedTheme)) {
    return savedTheme
  }
  return 'workshop'
}

const activeTheme = ref<ThemeStyle>(restoreTheme())

export function applyTheme(theme: ThemeStyle) {
  activeTheme.value = theme
  document.documentElement.setAttribute('data-style', theme)
  localStorage.setItem(THEME_STORAGE_KEY, theme)
}

export function initializeTheme() {
  applyTheme(activeTheme.value)
}

export function useTheme() {
  function cycleTheme() {
    const currentIndex = themeOptions.findIndex((theme) => theme.id === activeTheme.value)
    const nextTheme = themeOptions[(currentIndex + 1) % themeOptions.length]
    applyTheme(nextTheme.id)
  }

  return {
    activeTheme,
    themeOptions,
    applyTheme,
    cycleTheme,
  }
}
