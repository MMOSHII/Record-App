import { useThemeStore } from '../stores/themeStore'

let mediaQuery
let mediaListener

export const initThemeProvider = () => {
  const themeStore = useThemeStore()
  themeStore.applyTheme(themeStore.state.preference)

  if (typeof window === 'undefined' || !window.matchMedia) return
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaListener = () => themeStore.handleSystemThemeChange()
  if (typeof mediaQuery.addEventListener === 'function') {
    mediaQuery.addEventListener('change', mediaListener)
  } else {
    mediaQuery.addListener(mediaListener)
  }
}

export const disposeThemeProvider = () => {
  if (!mediaQuery || !mediaListener) return
  if (typeof mediaQuery.removeEventListener === 'function') {
    mediaQuery.removeEventListener('change', mediaListener)
  } else {
    mediaQuery.removeListener(mediaListener)
  }
}

