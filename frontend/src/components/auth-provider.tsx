import { useEffect, useState, useCallback } from 'react'
import { api, setToken } from '@/lib/api'
import { AuthContext, type AuthState } from '@/hooks/use-auth'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [username, setUsername] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [authRequired, setAuthRequired] = useState(true)

  const logout = useCallback(() => {
    setToken(null)
    setIsAuthenticated(false)
    setUsername(null)
  }, [])

  const login = useCallback((token: string, user: string) => {
    setToken(token)
    setIsAuthenticated(true)
    setUsername(user)
  }, [])

  // Verify session on mount
  useEffect(() => {
    api.verifySession()
      .then((status) => {
        setAuthRequired(status.auth_required)
        setIsAuthenticated(status.authenticated)
        setUsername(status.username)
      })
      .catch(() => {
        setToken(null)
        setIsAuthenticated(false)
      })
      .finally(() => setIsLoading(false))
  }, [])

  // Listen for forced logout from 401 responses
  useEffect(() => {
    const handler = () => logout()
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [logout])

  const value: AuthState = { isAuthenticated, username, isLoading, authRequired, login, logout }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
