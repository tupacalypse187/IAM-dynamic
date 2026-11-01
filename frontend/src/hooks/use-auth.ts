import { createContext, useContext } from 'react'

export type AuthState = {
  isAuthenticated: boolean
  username: string | null
  isLoading: boolean
  authRequired: boolean
  isAdmin: boolean
  login: (token: string, username: string) => void
  /**
   * TEMPORARY hackathon demo aid: switch to a view-as token WITHOUT
   * touching the OS vault (the admin's real session is restored on exit).
   */
  impersonate: (token: string, username: string) => void
  logout: () => void
}

export const AuthContext = createContext<AuthState>({
  isAuthenticated: false,
  username: null,
  isLoading: true,
  authRequired: true,
  isAdmin: false,
  login: () => null,
  impersonate: () => null,
  logout: () => null,
})

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
