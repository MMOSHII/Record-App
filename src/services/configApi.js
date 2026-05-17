import { useAppStore } from '../stores/appStore'
import { requestJson } from './httpClient'

const store = useAppStore()

const authHeaders = () => {
  const token = (store.state.settings.configAdminToken || '').trim()
  return token ? { 'X-Config-Token': token } : {}
}

export const getRuntimeConfig = () =>
  requestJson(`${store.getBaseUrl()}/api/v1/config`, {
    method: 'GET',
    headers: { Accept: 'application/json', ...authHeaders() },
    timeoutMs: 10000,
    retries: 0,
    errorLabel: 'Failed to load config'
  })

export const updateRuntimeConfig = (patch) =>
  requestJson(`${store.getBaseUrl()}/api/v1/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...authHeaders() },
    body: JSON.stringify({ patch }),
    timeoutMs: 15000,
    retries: 0,
    errorLabel: 'Failed to update config'
  })

export const resetRuntimeConfig = () =>
  requestJson(`${store.getBaseUrl()}/api/v1/config/reset`, {
    method: 'POST',
    headers: { Accept: 'application/json', ...authHeaders() },
    timeoutMs: 15000,
    retries: 0,
    errorLabel: 'Failed to reset config'
  })

