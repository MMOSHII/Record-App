import { describe, it, expect, beforeEach, vi } from 'vitest'

describe('themeStore', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.resetModules()
  })

  it('applies explicit dark preference', async () => {
    const { useThemeStore } = await import('../stores/themeStore.js')
    const theme = useThemeStore()
    theme.setPreference('dark')
    expect(theme.state.preference).toBe('dark')
    expect(theme.state.resolvedTheme).toBe('dark')
  })

  it('resolves system preference using media query', async () => {
    Object.defineProperty(window, 'matchMedia', {
      value: vi.fn().mockImplementation(() => ({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn()
      })),
      configurable: true
    })
    const { useThemeStore } = await import('../stores/themeStore.js')
    const theme = useThemeStore()
    theme.setPreference('system')
    expect(theme.state.resolvedTheme).toBe('dark')
  })
})

