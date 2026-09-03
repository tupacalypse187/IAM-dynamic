import { useState, useCallback } from 'react'
import { Check, Copy } from 'lucide-react'
import { copyText } from '@/lib/clipboard'
import { useToast } from '@/hooks/use-toast'
import { Button } from './ui/button'
import { cn } from '@/lib/utils'

interface CopyButtonProps {
  /** Text to copy, or a lazy getter (e.g. reading an element's content) */
  value: string | (() => string)
  label?: string
  className?: string
  variant?: 'outline' | 'ghost' | 'secondary'
}

/**
 * Reusable copy-to-clipboard button with success feedback and a
 * destructive toast when the browser blocks clipboard access.
 */
export function CopyButton({
  value,
  label = 'Copy',
  className,
  variant = 'outline',
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const { toast } = useToast()

  const handleCopy = useCallback(async () => {
    const text = typeof value === 'function' ? value() : value
    const succeeded = await copyText(text)
    if (succeeded) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } else {
      toast({
        title: 'Copy failed',
        description:
          'Your browser blocked clipboard access. Select the text and press Ctrl/Cmd+C to copy manually.',
        variant: 'destructive',
      })
    }
  }, [value, toast])

  return (
    <Button
      type="button"
      variant={variant}
      size="sm"
      onClick={handleCopy}
      aria-label={copied ? 'Copied to clipboard' : `${label} to clipboard`}
      className={cn(className)}
    >
      {copied ? (
        <>
          <Check className="h-4 w-4" aria-hidden="true" />
          Copied!
        </>
      ) : (
        <>
          <Copy className="h-4 w-4" aria-hidden="true" />
          {label}
        </>
      )}
    </Button>
  )
}
