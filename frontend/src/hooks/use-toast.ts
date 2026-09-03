import { createContext, useContext } from 'react'

export type ToastProps = {
  id: string
  title?: React.ReactNode
  description?: React.ReactNode
  variant?: 'default' | 'destructive' | 'success'
}

type ToastContextState = {
  toasts: ToastProps[]
  toast: (toast: Omit<ToastProps, 'id'>) => void
  dismiss: (id: string) => void
}

export const ToastContext = createContext<ToastContextState | null>(null)

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within a ToastProvider')
  return context
}
