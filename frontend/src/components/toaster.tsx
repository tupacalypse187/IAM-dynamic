import { useToast } from './ui/use-toast'
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastTitle,
  ToastViewport,
  RadixToastProvider,
} from './ui/toast'

export function Toaster() {
  const { toasts, dismiss } = useToast()

  return (
    <RadixToastProvider>
      {toasts.map(({ id, title, description, variant }) => (
        <Toast key={id} variant={variant} onOpenChange={(open) => !open && dismiss(id)}>
          <div className="grid gap-1">
            {title && <ToastTitle>{title}</ToastTitle>}
            {description && <ToastDescription>{description}</ToastDescription>}
          </div>
          <ToastClose aria-label="Dismiss notification" />
        </Toast>
      ))}
      <ToastViewport />
    </RadixToastProvider>
  )
}
