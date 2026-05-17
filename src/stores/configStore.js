import { reactive } from 'vue'
import { getRuntimeConfig, resetRuntimeConfig, updateRuntimeConfig } from '../services/configApi'

const state = reactive({
  loading: false,
  saving: false,
  resetting: false,
  error: '',
  config: null
})

const loadConfig = async () => {
  state.loading = true
  state.error = ''
  try {
    const data = await getRuntimeConfig()
    state.config = data?.config || null
  } catch (err) {
    state.error = err.message || 'Failed to load config'
  } finally {
    state.loading = false
  }
}

const patchConfig = async (patch) => {
  state.saving = true
  state.error = ''
  const previous = state.config
  state.config = { ...(state.config || {}), ...patch }
  try {
    const data = await updateRuntimeConfig(patch)
    state.config = data?.config || state.config
    return state.config
  } catch (err) {
    state.config = previous
    state.error = err.message || 'Failed to update config'
    throw err
  } finally {
    state.saving = false
  }
}

const resetConfig = async () => {
  state.resetting = true
  state.error = ''
  try {
    const data = await resetRuntimeConfig()
    state.config = data?.config || null
    return state.config
  } catch (err) {
    state.error = err.message || 'Failed to reset config'
    throw err
  } finally {
    state.resetting = false
  }
}

export const useConfigStore = () => ({
  state,
  loadConfig,
  patchConfig,
  resetConfig
})

