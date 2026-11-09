import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || '/api'

const ACCESS_KEY = 'agentforge.access_token'
const REFRESH_KEY = 'agentforge.refresh_token'

// ---------------------------------------------------------------- token store
export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set({ access_token, refresh_token }) {
    localStorage.setItem(ACCESS_KEY, access_token)
    localStorage.setItem(REFRESH_KEY, refresh_token)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

// Notified when refresh fails so the auth context can log the user out.
let onAuthFailure = () => {}
export const setAuthFailureHandler = (handler) => {
  onAuthFailure = handler
}

const api = axios.create({ baseURL: API_URL })

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ------------------------------------------------------------- token refresh
// A single in-flight refresh is shared by all requests that hit a 401 at once,
// because refresh tokens are single-use on the backend.
let refreshPromise = null

export function refreshAccessToken() {
  if (!refreshPromise) {
    const refreshToken = tokenStore.getRefresh()
    refreshPromise = (
      refreshToken
        ? axios.post(`${API_URL}/auth/refresh`, { refresh_token: refreshToken })
        : Promise.reject(new Error('No refresh token'))
    )
      .then(({ data }) => {
        tokenStore.set(data)
        return data.access_token
      })
      .catch((error) => {
        tokenStore.clear()
        onAuthFailure()
        throw error
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthRoute = original?.url?.startsWith('/auth/')
    if (error.response?.status === 401 && original && !original._retry && !isAuthRoute) {
      original._retry = true
      const token = await refreshAccessToken()
      original.headers.Authorization = `Bearer ${token}`
      return api(original)
    }
    return Promise.reject(error)
  },
)

/** Human-readable message from an axios error / backend error envelope. */
export function getErrorMessage(error, fallback = 'Something went wrong') {
  const body = error?.response?.data
  if (body?.error?.message) {
    const details = body.error.details
    if (Array.isArray(details) && details[0]?.msg) return `${body.error.message}: ${details[0].msg}`
    return body.error.message
  }
  return error?.message || fallback
}

export default api
