import { createContext, useContext } from 'react'

export type AuthState = {
  isAuthenticated: boolean
  username: string | null
  isLoading: boolean
  authRequired: boolean
  login: (token: string, username: string) => void
  logout: () => void
}

export const AuthContext = createContext<AuthState>({
  isAuthenticated: false,
  username: null,
  isLoading: true,
  authRequired: true,
  login: () => null,
  logout: () => null,
})

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
