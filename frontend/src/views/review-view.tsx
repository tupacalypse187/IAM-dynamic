import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2, AlertCircle, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react'
import { api } from '@/lib/api'
import type { PolicyResponse, Credentials } from '@/types/api'
import { Button } from '@/components/ui/button'
import { CopyButton } from '@/components/copy-button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

interface ReviewViewProps {
  policyData: PolicyResponse
  onBack: () => void
  onCredentialsIssued: (credentials: Credentials) => void
  onRejected: () => void
}

// Static class maps — Tailwind's JIT scanner must see full class names,
// so risk colors can never be assembled at runtime.
const riskConfig = {
  low: {
    iconBg: 'bg-success',
    border: 'border-l-success',
    label: 'Low Risk',
    icon: CheckCircle2,
  },
  medium: {
    iconBg: 'bg-warning',
    border: 'border-l-warning',
    label: 'Medium Risk',
    icon: AlertTriangle,
  },
  high: {
    iconBg: 'bg-orange-600',
    border: 'border-l-orange-600',
    label: 'High Risk',
    icon: AlertTriangle,
  },
  critical: {
    iconBg: 'bg-destructive',
    border: 'border-l-destructive',
    label: 'Critical Risk',
    icon: AlertCircle,
  },
} as const

export default function ReviewView({
  policyData,
  onBack,
  onCredentialsIssued,
  onRejected,
}: ReviewViewProps) {
  const [changeCase, setChangeCase] = useState('')
  const [error, setError] = useState<string | null>(null)

  const issueMutation = useMutation({
    mutationFn: api.issueCredentials,
    onSuccess: (data) => {
      setError(null)
      onCredentialsIssued(data)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const handleIssue = () => {
    if (!policyData.auto_approved && !changeCase.trim()) {
      setError('Please provide a business justification')
      return
    }
    issueMutation.mutate({
      policy: policyData.policy,
      duration: policyData.max_duration,
      approved: true,
      change_case: changeCase || undefined,
    })
  }

  const risk = riskConfig[policyData.risk] ?? riskConfig.medium
  const RiskIcon = risk.icon

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div>
        <Button variant="ghost" onClick={onBack} className="mb-2">
          ← Back
        </Button>
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Policy Review</h2>
        <p className="text-muted-foreground">
          Review the generated IAM policy before issuing credentials.
        </p>
      </div>

      {/* Risk Badge */}
      <Card className={`border-l-4 ${risk.border} shadow-card`}>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-3">
            <div className={`rounded-full p-2 ${risk.iconBg}`} aria-hidden="true">
              <RiskIcon className="h-5 w-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold">{risk.label}</h3>
              <p className="text-sm text-muted-foreground">
                {policyData.auto_approved
                  ? 'Auto-approved - No additional approval required'
                  : 'Manual approval required'}
              </p>
            </div>
            <Badge variant="outline" className="ml-auto">
              Max: {policyData.max_duration}h
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Policy Details */}
      <Card>
        <CardHeader>
          <CardTitle>Generated Policy</CardTitle>
          <CardDescription>
            AI-generated IAM policy based on your request
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="json">
            <TabsList>
              <TabsTrigger value="json">JSON</TabsTrigger>
              <TabsTrigger value="explanation">Explanation</TabsTrigger>
            </TabsList>
            <TabsContent value="json" className="mt-4">
              <div className="relative">
                <pre className="overflow-auto rounded-md bg-muted p-4 pr-24 font-mono text-sm">
                  {JSON.stringify(policyData.policy, null, 2)}
                </pre>
                <CopyButton
                  value={JSON.stringify(policyData.policy, null, 2)}
                  label="Copy JSON"
                  className="absolute right-2 top-2"
                />
              </div>
            </TabsContent>
            <TabsContent value="explanation" className="mt-4 space-y-4">
              <div>
                <h4 className="font-semibold">Explanation</h4>
                <p className="text-muted-foreground">{policyData.explanation}</p>
              </div>
              {policyData.approver_note && (
                <div>
                  <h4 className="font-semibold">Approver Note</h4>
                  <p className="text-muted-foreground">{policyData.approver_note}</p>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Approval Section */}
      <Card>
        <CardHeader>
          <CardTitle>Credential Issuance</CardTitle>
          <CardDescription>
            {policyData.auto_approved
              ? 'Your request qualifies for automatic approval.'
              : 'Please provide business justification for manual approval.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!policyData.auto_approved && (
            <div className="space-y-2">
              <Label htmlFor="changeCase">Business Justification</Label>
              <Textarea
                id="changeCase"
                placeholder="Enter ticket number or business justification..."
                value={changeCase}
                onChange={(e) => setChangeCase(e.target.value)}
                rows={3}
              />
            </div>
          )}

          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
              {error}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              onClick={handleIssue}
              disabled={issueMutation.isPending || (!policyData.auto_approved && !changeCase.trim())}
              className="flex-1"
              size="lg"
            >
              {issueMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Issuing Credentials...
                </>
              ) : (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Issue Credentials
                </>
              )}
            </Button>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="lg" className="shrink-0">
                  <XCircle className="mr-2 h-4 w-4" />
                  Reject
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Reject this request?</AlertDialogTitle>
                  <AlertDialogDescription>
                    The request will be marked as rejected and no credentials will be issued.
                    You can review AI guidance for resubmitting a better-scoped request
                    afterwards.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    onClick={onRejected}
                  >
                    Reject request
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          {policyData.auto_approved && (
            <p className="text-xs text-center text-muted-foreground">
              You can still reject this request if you have concerns.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
