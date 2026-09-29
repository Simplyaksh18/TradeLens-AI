import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as authApi from '../api/auth'
import { AbortedRequestError } from '../api/client'
import type { AuthUser } from '../api/types'
import { AuthContext, type AuthStatus } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  useEffect(() => {
    const controller = new AbortController()
    authApi
      .getCurrentUser({ signal: controller.signal })
      .then((current) => {
        setUser(current)
        setStatus('authenticated')
      })
      .catch((err) => {
        // React StrictMode double-invokes effects in development: the
        // first mount's request is aborted by cleanup before the second
        // mount's request resolves. Without this check, the aborted
        // request's rejection could land AFTER the real request's success
        // and incorrectly flip a genuinely authenticated session back to
        // "unauthenticated" (found via manual smoke testing — a refresh
        // bounced a just-registered user back to /login).
        if (err instanceof AbortedRequestError) return
        setUser(null)
        setStatus('unauthenticated')
      })
    return () => controller.abort()
  }, [])

  const login = useCallback(async (payload: authApi.LoginPayload) => {
    const current = await authApi.login(payload)
    setUser(current)
    setStatus('authenticated')
  }, [])

  const register = useCallback(async (payload: authApi.RegisterPayload) => {
    const current = await authApi.register(payload)
    setUser(current)
    setStatus('authenticated')
  }, [])

  const loginWithGoogle = useCallback(async (credential: string) => {
    const current = await authApi.loginWithGoogle(credential)
    setUser(current)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setUser(null)
    setStatus('unauthenticated')
  }, [])

  const updateProfile = useCallback(async (payload: authApi.ProfileUpdatePayload) => {
    const current = await authApi.updateProfile(payload)
    setUser(current)
  }, [])

  const value = useMemo(
    () => ({ user, status, login, register, loginWithGoogle, logout, updateProfile }),
    [user, status, login, register, loginWithGoogle, logout, updateProfile],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
