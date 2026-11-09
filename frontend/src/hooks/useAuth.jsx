import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import api, { setAuthFailureHandler, tokenStore } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokenStore.getAccess() || tokenStore.getRefresh()))

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  useEffect(() => {
    setAuthFailureHandler(() => setUser(null))
    if (!tokenStore.getAccess() && !tokenStore.getRefresh()) return
    api
      .get('/auth/me')
      .then(({ data }) => setUser(data))
      .catch(() => logout())
      .finally(() => setLoading(false))
  }, [logout])

  const handleAuth = useCallback(({ user: nextUser, tokens }) => {
    tokenStore.set(tokens)
    setUser(nextUser)
    return nextUser
  }, [])

  const login = useCallback(
    async (email, password) => handleAuth((await api.post('/auth/login', { email, password })).data),
    [handleAuth],
  )

  const register = useCallback(
    async (email, password, fullName) =>
      handleAuth((await api.post('/auth/register', { email, password, full_name: fullName || null })).data),
    [handleAuth],
  )

  const value = useMemo(
    () => ({ user, loading, isAuthenticated: Boolean(user), login, register, logout }),
    [user, loading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
