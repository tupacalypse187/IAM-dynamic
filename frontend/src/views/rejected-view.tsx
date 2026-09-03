import { useState, useRef } from 'react'
import { Loader2, AlertCircle, Lightbulb, RefreshCw, FileEdit, RotateCcw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { api } from '@/lib/api'
import type { PolicyResponse } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { CopyButton } from '@/components/copy-button'

/** Code block with a hover/focus-revealed copy button (the modern standard). */
function MarkdownPre({ children, ...props }: React.ComponentPropsWithoutRef<'pre'>) {
  const preRef = useRef<HTMLPreElement>(null)
  return (
    <div className="group relative">
      <CopyButton
        value={() => preRef.current?.textContent ?? ''}
        label="Copy"
        variant="secondary"
        className="absolute right-2 top-2 opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
      />
      <pre ref={preRef} {...props}>
        {children}
      </pre>
    </div>
  )
}

interface RejectedViewProps {
  policyData: PolicyResponse
  requestText: string
  duration: number
  selectedProvider: string
  selectedModel?: string
  onReviseRequest: (text: string) => void
  onStartFresh: () => void
}

// Soft tint + strong text keeps every pair readable in both themes
const riskBadgeClass = {
  low: 'bg-success/15 text-success',
  medium: 'bg-warning/15 text-warning',
  high: 'bg-orange-600/15 text-orange-700 dark:text-orange-400',
  critical: 'bg-destructive/15 text-destructive',
} as const

const riskLabel = {
  low: 'Low Risk',
  medium: 'Medium Risk',
  high: 'High Risk',
  critical: 'Critical Risk',
} as const

export default function RejectedView({
  policyData,
  requestText,
  duration,
  selectedProvider,
  selectedModel,
  onReviseRequest,
  onStartFresh,
}: RejectedViewProps) {
  const [guidance, setGuidance] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const badgeClass = riskBadgeClass[policyData.risk] ?? riskBadgeClass.medium
  const label = riskLabel[policyData.risk] ?? riskLabel.medium

  // Fetch AI guidance for improving the request
  const fetchGuidance = async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await api.generateRejectionGuidance({
        original_request: requestText,
        policy: policyData.policy,
        risk: policyData.risk,
        provider: selectedProvider,
        model: selectedModel,
      })
      const rawGuidance = data.guidance || 'No guidance available. Please try revising your request with more specific resource names and limited actions.'
      // Use raw guidance directly - backend now outputs clean markdown
      setGuidance(rawGuidance)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate guidance')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-destructive sm:text-3xl">
          Request Rejected
        </h2>
        <p className="text-muted-foreground">
          Your access request was rejected. You can revise and resubmit with better scoping.
        </p>
      </div>

      {/* Alert */}
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Request Rejected</AlertTitle>
        <AlertDescription>
          This request was rejected due to elevated risk level ({label}).
          Please review the guidance below and revise your request with more specific scoping.
        </AlertDescription>
      </Alert>

      {/* Original Request Details */}
      <Card>
        <CardHeader>
          <CardTitle>Original Request</CardTitle>
          <CardDescription>The request that was rejected</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-2">Request Text:</p>
            <p className="p-3 bg-muted rounded-md">{requestText}</p>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <Badge variant="outline" className={`border-0 ${badgeClass}`}>
              {label}
            </Badge>
            <Badge variant="outline">
              Duration: {duration}h
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Button
          onClick={fetchGuidance}
          disabled={loading}
          variant="default"
          className="w-full"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Generating...
            </>
          ) : guidance ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh Guidance
            </>
          ) : (
            <>
              <Lightbulb className="mr-2 h-4 w-4" />
              Get AI Guidance
            </>
          )}
        </Button>

        <Button
          onClick={() => onReviseRequest(requestText)}
          variant="outline"
          className="w-full"
        >
          <FileEdit className="mr-2 h-4 w-4" />
          Revise Request
        </Button>

        <Button
          onClick={onStartFresh}
          variant="outline"
          className="w-full"
        >
          <RotateCcw className="mr-2 h-4 w-4" />
          Start Fresh
        </Button>
      </div>

      {/* Error */}
      {error && (
        <Alert variant="destructive" role="alert">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* AI Guidance */}
      {guidance && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-warning" aria-hidden="true" />
              AI Guidance for Resubmission
            </CardTitle>
            <CardDescription>
              Here are specific suggestions to improve your request
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="prose max-w-none dark:prose-invert prose-custom">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{ pre: MarkdownPre }}
              >
                {guidance}
              </ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
