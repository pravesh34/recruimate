import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import api, { tokens } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [authEnabled, setAuthEnabled] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const status = await api.authStatus()
        if (cancelled) return
        setAuthEnabled(Boolean(status?.auth_enabled))
        if (status?.auth_enabled && tokens.access) {
          try {
            const me = await api.me()
            if (!cancelled) setUser(me)
          } catch {
            tokens.clear()
          }
        }
      } catch {
        // Backend offline or auth disabled: fall back to trusted-local mode.
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email, password) => {
    const data = await api.login({ email, password })
    tokens.set(data)
    setUser(data.user)
    return data.user
  }, [])

  const register = useCallback(async (email, password, display_name) => {
    const data = await api.register({ email, password, display_name })
    tokens.set(data)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    await api.logout()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, authEnabled, login, register, logout, setUser }),
    [user, loading, authEnabled, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside an AuthProvider')
  return ctx
}
