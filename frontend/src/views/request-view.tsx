import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2, AlertCircle, Info, MessageCircleQuestion, Sparkles } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { usePolicyAgent, type SubmitOutcome } from '@/hooks/use-policy-agent'
import type { AgentProgress, ClarifyQuestion } from '@/types/desktop'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'

interface RequestViewProps {
  requestText: string
  onRequestTextChange: (text: string) => void
  duration: number
  onDurationChange: (duration: number) => void
  selectedProvider: string
  selectedModel?: string
  onSubmitted: (outcome: SubmitOutcome) => void
}

const EMPTY_GUIDED = { task: '', resources: '', ticket: '' }

export default function RequestView({
  requestText,
  onRequestTextChange,
  duration,
  onDurationChange,
  selectedProvider,
  selectedModel,
  onSubmitted,
}: RequestViewProps) {
  const [error, setError] = useState<string | null>(null)
  const [guided, setGuided] = useState(EMPTY_GUIDED)
  const [questions, setQuestions] = useState<ClarifyQuestion[] | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [stage, setStage] = useState<string | null>(null)
  const agent = usePolicyAgent()

  useEffect(() => agent.subscribeProgress((p: AgentProgress) => setStage(p.message)), [agent])

  const generateMutation = useMutation({
    mutationFn: (extraAnswers: Record<string, string>) =>
      agent.submit({
        freeText: requestText,
        guided,
        provider: selectedProvider,
        model: selectedModel,
        durationHours: duration,
        answers: extraAnswers,
      }),
    onSuccess: (outcome) => {
      setError(null)
      if (outcome.kind === 'clarify') {
        setQuestions(outcome.questions)
        setStage(null)
      } else {
        setQuestions(null)
        setAnswers({})
        setStage(null)
        onSubmitted(outcome)
      }
    },
    onError: (err: Error) => {
      setError(err.message)
      setStage(null)
    },
  })

  const handleSubmit = () => {
    if (!requestText.trim() && !guided.task.trim()) {
      setError('Describe what you are trying to do — a sentence or the guided fields below.')
      return
    }
    generateMutation.mutate({})
  }

  const handleAnswerSubmit = () => {
    generateMutation.mutate(answers)
  }

  const pending = generateMutation.isPending

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">New Request</h2>
        <p className="text-muted-foreground">
          Describe the job you need to do — not the permissions. AI figures out the least-privilege policy.
        </p>
      </div>

      <Card className="shadow-card">
        <CardHeader>
          <CardTitle>Access Request</CardTitle>
          <CardDescription>
            Start with what you are trying to accomplish. If anything is ambiguous, you will be
            asked at most three short follow-up questions.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Free text */}
          <div className="space-y-2" data-tour="request-input">
            <Label htmlFor="request-textarea">What are you trying to do?</Label>
            <Textarea
              id="request-textarea"
              placeholder="e.g. Investigate incident 501 in the orders table and billing bucket for 30 minutes."
              value={requestText}
              onChange={(e) => onRequestTextChange(e.target.value)}
              rows={4}
              className="resize-none"
            />
          </div>

          {/* Guided scaffold */}
          <div className="space-y-4 rounded-md border p-4" data-tour="guided-fields">
            <p className="flex items-center gap-2 text-sm font-medium">
              <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
              Help me describe it
              <span className="font-normal text-muted-foreground">(optional — fills in the blanks)</span>
            </p>
            <div className="space-y-2">
              <Label htmlFor="guided-task">The task</Label>
              <Input
                id="guided-task"
                placeholder="e.g. Debug failed checkout webhooks"
                value={guided.task}
                onChange={(e) => setGuided({ ...guided, task: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="guided-resources">Where (resources, if known)</Label>
              <Input
                id="guided-resources"
                placeholder='e.g. "checkout-events" SQS queue, production logs bucket'
                value={guided.resources}
                onChange={(e) => setGuided({ ...guided, resources: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="guided-ticket">Why (ticket or incident)</Label>
              <Input
                id="guided-ticket"
                placeholder="e.g. incident 501, CHG-1234"
                value={guided.ticket}
                onChange={(e) => setGuided({ ...guided, ticket: e.target.value })}
              />
            </div>
          </div>

          {/* Duration */}
          <div className="space-y-4" data-tour="request-duration">
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

          {/* Clarifying questions */}
          {questions && questions.length > 0 && (
            <div className="space-y-4 rounded-md border border-primary/30 bg-primary/5 p-4" role="form" aria-label="Clarifying questions">
              <p className="flex items-center gap-2 text-sm font-medium">
                <MessageCircleQuestion className="h-4 w-4 text-primary" aria-hidden="true" />
                A few quick questions so the policy isn&apos;t broader than it needs to be
              </p>
              {questions.map((q) => (
                <div key={q.field} className="space-y-2">
                  <Label htmlFor={`clarify-${q.field}`}>{q.prompt}</Label>
                  <Input
                    id={`clarify-${q.field}`}
                    placeholder={q.placeholder}
                    value={answers[q.field] ?? ''}
                    onChange={(e) => setAnswers({ ...answers, [q.field]: e.target.value })}
                  />
                </div>
              ))}
              <Button onClick={handleAnswerSubmit} disabled={pending} className="w-full">
                {pending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {stage ?? 'Analyzing...'}
                  </>
                ) : (
                  'Continue with these answers'
                )}
              </Button>
            </div>
          )}

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

          {/* Submit */}
          {!questions && (
            <Button
              onClick={handleSubmit}
              disabled={pending || (!requestText.trim() && !guided.task.trim())}
              className="w-full"
              size="lg"
              data-tour="request-submit"
            >
              {pending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {stage ?? 'Analyzing...'}
                </>
              ) : (
                'Submit Request'
              )}
            </Button>
          )}
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
                go to an administrator for review. Approval alone issues nothing — you activate
                the credentials when you are ready to use them.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
