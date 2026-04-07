import { useAppStore } from '../stores/appStore'

/**
 * Returns true when running inside a Capacitor native app (Android / iOS).
 * Falls back to false in a regular browser.
 */
export function isCapacitorNative() {
  return typeof window !== 'undefined' && window.Capacitor?.isNativePlatform?.() === true
}

/**
 * Parse the error body from a failed fetch response.
 * Handles both JSON (`{ detail, message, error }`) and plain-text bodies.
 */
async function parseErrorBody(response) {
  const text = await response.text()
  try {
    const json = JSON.parse(text)
    return json.detail || json.message || json.error || text
  } catch {
    return text || `Request failed (${response.status})`
  }
}

// ---------------------------------------------------------------------------
// Google OAuth – native Capacitor path
// ---------------------------------------------------------------------------

/**
 * Sign in with Google using the native Capacitor plugin.
 * Should only be called when `isCapacitorNative()` is true.
 * Stores the ID token and user info in the app store.
 */
export async function signInWithGoogleNative() {
  const GOOGLE_CLIENT_ID =
    import.meta.env.VITE_GOOGLE_CLIENT_ID ||
    '710746488463-9ibge0al61j8sseikfde8c3ejc8h99uh.apps.googleusercontent.com'

  const { GoogleAuth } = await import('@codetrix-studio/capacitor-google-auth')

  await GoogleAuth.initialize({
    clientId: GOOGLE_CLIENT_ID,
    scopes: ['profile', 'email'],
    grantOfflineAccess: false
  })

  const result = await GoogleAuth.signIn()

  const store = useAppStore()
  store.state.token = result.authentication.idToken
  store.state.user = {
    name: result.name || result.email || 'User',
    email: result.email || '',
    picture: result.imageUrl || ''
  }
  store.state.authMethod = 'oauth'
}

// ---------------------------------------------------------------------------
// Basic auth – email / password
// ---------------------------------------------------------------------------

/**
 * Log in with email and password.
 * Expects the backend to return `{ token, user? }` or `{ access_token, user? }`.
 */
export async function loginBasic(email, password) {
  const store = useAppStore()
  const url = `${store.getBaseUrl()}/api/v1/auth/login`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })

  if (!response.ok) {
    throw new Error(await parseErrorBody(response))
  }

  const data = await response.json()
  store.state.token = data.token || data.access_token || ''
  store.state.user = {
    name: data.user?.name || data.name || email,
    email: data.user?.email || data.email || email,
    picture: data.user?.picture || data.picture || ''
  }
  store.state.authMethod = 'basic'
}

/**
 * Register a new account with name, email and password.
 * If the backend returns a token the user is automatically logged in.
 */
export async function registerBasic(name, email, password) {
  const store = useAppStore()
  const url = `${store.getBaseUrl()}/api/v1/auth/register`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password })
  })

  if (!response.ok) {
    throw new Error(await parseErrorBody(response))
  }

  const data = await response.json()
  const token = data.token || data.access_token
  if (token) {
    store.state.token = token
    store.state.user = {
      name: data.user?.name || name,
      email: data.user?.email || email,
      picture: data.user?.picture || ''
    }
    store.state.authMethod = 'basic'
  }
  return data
}

/**
 * Request a password-reset email for the given address.
 */
export async function forgotPassword(email) {
  const store = useAppStore()
  const url = `${store.getBaseUrl()}/api/v1/auth/forgot-password`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  })

  if (!response.ok) {
    throw new Error(await parseErrorBody(response))
  }
}

/**
 * Complete a password reset using the token from the reset email.
 */
export async function resetPassword(token, newPassword) {
  const store = useAppStore()
  const url = `${store.getBaseUrl()}/api/v1/auth/reset-password`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword })
  })

  if (!response.ok) {
    throw new Error(await parseErrorBody(response))
  }
}

/**
 * Change the password for the currently authenticated user.
 * Requires `state.token` to be set (basic-auth users only).
 */
export async function changePassword(currentPassword, newPassword) {
  const store = useAppStore()
  const url = `${store.getBaseUrl()}/api/v1/auth/change-password`
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${store.state.token}`
    },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
  })

  if (!response.ok) {
    throw new Error(await parseErrorBody(response))
  }
}
