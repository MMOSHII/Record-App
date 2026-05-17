export const THEME_KEY = 'recordnote_theme_preference_v1'

export const THEME_OPTIONS = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'dim', label: 'Dimmed Dark' },
  { value: 'high-contrast', label: 'High Contrast' }
]

export const THEME_TOKENS = {
  light: {
    '--app-bg': '#f8fafc',
    '--app-surface': '#ffffff',
    '--app-text': '#0f172a'
  },
  dark: {
    '--app-bg': '#020617',
    '--app-surface': '#0f172a',
    '--app-text': '#e2e8f0'
  },
  dim: {
    '--app-bg': '#111827',
    '--app-surface': '#1f2937',
    '--app-text': '#e5e7eb'
  },
  'high-contrast': {
    '--app-bg': '#000000',
    '--app-surface': '#000000',
    '--app-text': '#ffffff'
  }
}

