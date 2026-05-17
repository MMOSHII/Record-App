import { reactive } from 'vue'
import { THEME_KEY, THEME_TOKENS } from '../theme/themeTokens'

const savedPreference = (() => {
  try {
    return localStorage.getItem(THEME_KEY) || 'system'
  } catch {
    return 'system'
  }
})()

const state = reactive({
  preference: savedPreference,
  resolvedTheme: 'light'
})

const systemTheme = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'

const resolveTheme = (preference) => (preference === 'system' ? systemTheme() : preference)

const applyTheme = (preference = state.preference) => {
  const resolved = resolveTheme(preference)
  const tokens = THEME_TOKENS[resolved] || THEME_TOKENS.light
  state.preference = preference
  state.resolvedTheme = resolved

  if (typeof document !== 'undefined') {
    const root = document.documentElement
    root.setAttribute('data-theme', preference)
    root.setAttribute('data-theme-resolved', resolved)
    root.style.colorScheme = resolved === 'light' ? 'light' : 'dark'
    Object.entries(tokens).forEach(([key, value]) => root.style.setProperty(key, value))
  }

  try {
    localStorage.setItem(THEME_KEY, preference)
  } catch {
    // ignore storage failures
  }
}

const setPreference = (value) => {
  applyTheme(value || 'system')
}

const handleSystemThemeChange = () => {
  if (state.preference === 'system') applyTheme('system')
}

export const useThemeStore = () => ({
  state,
  applyTheme,
  setPreference,
  handleSystemThemeChange
})

