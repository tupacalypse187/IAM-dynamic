import * as React from 'react'

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

const ToastContext = React.createContext<ToastContextState | null>(null)

const TOAST_LIMIT = 3
const TOAST_DURATION_MS = 5000

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastProps[]>([])
  const timers = React.useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const dismiss = React.useCallback((id: string) => {
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
    setToasts((current) => current.filter((t) => t.id !== id))
  }, [])

  const toast = React.useCallback(
    (newToast: Omit<ToastProps, 'id'>) => {
      const id = crypto.randomUUID()
      setToasts((current) => [...current.slice(-(TOAST_LIMIT - 1)), { ...newToast, id }])
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), TOAST_DURATION_MS)
      )
    },
    [dismiss]
  )

  React.useEffect(() => {
    const pending = timers.current
    return () => pending.forEach((timer) => clearTimeout(timer))
  }, [])

  const value = React.useMemo(() => ({ toasts, toast, dismiss }), [toasts, toast, dismiss])

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function useToast() {
  const context = React.useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within a ToastProvider')
  return context
}
