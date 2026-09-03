import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2, AlertCircle, Info } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '@/lib/api'
import type { PolicyResponse } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'

interface RequestViewProps {
  requestText: string
  onRequestTextChange: (text: string) => void
  duration: number
  onDurationChange: (duration: number) => void
  selectedProvider: string
  selectedModel?: string
  onPolicyGenerated: (data: PolicyResponse) => void
}

export default function RequestView({
  requestText,
  onRequestTextChange,
  duration,
  onDurationChange,
  selectedProvider,
  selectedModel,
  onPolicyGenerated,
}: RequestViewProps) {
  const [error, setError] = useState<string | null>(null)

  const generateMutation = useMutation({
    mutationFn: api.generatePolicy,
    onSuccess: (data) => {
      setError(null)
      onPolicyGenerated(data)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const handleSubmit = () => {
    if (!requestText.trim()) {
      setError('Please describe your access needs')
      return
    }
    generateMutation.mutate({
      request_text: requestText,
      provider: selectedProvider,
      model: selectedModel,
      duration,
    })
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">New Request</h2>
        <p className="text-muted-foreground">
          Describe your AWS access needs and AI will generate a least-privilege IAM policy.
        </p>
      </div>

      <Card className="shadow-card">
        <CardHeader>
          <CardTitle>Access Request</CardTitle>
          <CardDescription>
            Be specific about the resources and actions you need. The more detailed your request,
            the more accurate the generated policy will be.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Request Text */}
          <div className="space-y-2">
            <Label htmlFor="request">Describe your access needs</Label>
            <Textarea
              id="request"
              placeholder="e.g. I need read-only access to the 'production-logs' S3 bucket to debug an issue."
              value={requestText}
              onChange={(e) => onRequestTextChange(e.target.value)}
              rows={5}
              className="resize-none"
            />
          </div>

          {/* Duration */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="session-duration">Session Duration</Label>
              <span className="text-sm font-medium tabular-nums">{duration} hours</span>
            </div>
            <Slider
              id="session-duration"
              aria-label="Session duration in hours"
              value={[duration]}
              onValueChange={(values) => onDurationChange(values[0])}
              min={1}
              max={12}
              step={1}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Maximum duration may be limited based on risk level assessment.
            </p>
          </div>

          {/* Error */}
          {error && (
            <div
              className="rounded-md bg-destructive/10 border border-destructive/20 p-4"
              role="alert"
              aria-live="polite"
            >
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" aria-hidden="true" />
                <div className="flex-1 text-sm prose prose-sm max-w-none dark:prose-invert">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {error}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <Button
            onClick={handleSubmit}
            disabled={generateMutation.isPending || !requestText.trim()}
            className="w-full"
            size="lg"
          >
            {generateMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              'Analyze & Generate Policy'
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <div className="rounded-full bg-primary/10 p-2" aria-hidden="true">
              <Info className="h-4 w-4 text-primary" />
            </div>
            <div className="text-sm">
              <p className="font-medium">How it works</p>
              <p className="mt-1 text-muted-foreground">
                Our AI analyzes your request and generates a least-privilege IAM policy tailored
                to your needs. Low-risk requests are auto-approved, while higher-risk requests
                may require manual approval.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
