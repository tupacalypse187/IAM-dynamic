import { useState, useEffect } from 'react'
import { Download, RotateCcw, ShieldAlert } from 'lucide-react'
import type { Credentials } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { CopyButton } from '@/components/copy-button'

interface CredentialsViewProps {
  credentials: Credentials
  duration: number
  onNewRequest: () => void
}

type ScriptFormat = 'bash' | 'powershell' | 'aws-cli'

export default function CredentialsView({ credentials, duration, onNewRequest }: CredentialsViewProps) {
  const [timeRemaining, setTimeRemaining] = useState('')

  useEffect(() => {
    const updateTimer = () => {
      const now = new Date()
      const exp = new Date(credentials.expiration)
      const diff = exp.getTime() - now.getTime()

      if (diff <= 0) {
        setTimeRemaining('Expired')
        return
      }

      const hours = Math.floor(diff / (1000 * 60 * 60))
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

      setTimeRemaining(`${hours}h ${minutes}m`)
    }

    updateTimer()
    const interval = setInterval(updateTimer, 60000)

    return () => clearInterval(interval)
  }, [credentials.expiration])

  const bashScript = `export AWS_ACCESS_KEY_ID="${credentials.access_key_id}"
export AWS_SECRET_ACCESS_KEY="${credentials.secret_access_key}"
export AWS_SESSION_TOKEN="${credentials.session_token}"
# Test your access:
# aws sts get-caller-identity`

  const psScript = `$Env:AWS_ACCESS_KEY_ID="${credentials.access_key_id}"
$Env:AWS_SECRET_ACCESS_KEY="${credentials.secret_access_key}"
$Env:AWS_SESSION_TOKEN="${credentials.session_token}"
# Test your access:
# aws sts get-caller-identity`

  const awsCli = `aws configure set aws_access_key_id ${credentials.access_key_id} --profile iam-session
aws configure set aws_secret_access_key ${credentials.secret_access_key} --profile iam-session
aws configure set aws_session_token ${credentials.session_token} --profile iam-session
# Test your access:
# aws sts get-caller-identity --profile iam-session`

  const downloadScript = () => {
    const blob = new Blob([bashScript], { type: 'text/x-shellscript' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `aws-credentials-${Date.now()}.sh`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const scriptTabs: Array<{ format: ScriptFormat; label: string; script: string }> = [
    { format: 'bash', label: 'Bash / Zsh', script: bashScript },
    { format: 'powershell', label: 'PowerShell', script: psScript },
    { format: 'aws-cli', label: 'AWS CLI', script: awsCli },
  ]

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Credentials Issued</h2>
        <p className="text-muted-foreground">
          Your temporary AWS credentials have been successfully issued.
        </p>
      </div>

      {/* Expiration Timer */}
      <Card className="shadow-card">
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Time Remaining</p>
              <p className="text-3xl font-bold tabular-nums">{timeRemaining}</p>
            </div>
            <Badge variant="outline" className="text-base">
              {duration} hour session
            </Badge>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Expires at {new Date(credentials.expiration).toLocaleString()}
          </p>
        </CardContent>
      </Card>

      {/* Credentials Display */}
      <Card>
        <CardHeader>
          <CardTitle>Your Temporary Credentials</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="bash">
            <TabsList className="grid w-full grid-cols-3">
              {scriptTabs.map(({ format, label }) => (
                <TabsTrigger key={format} value={format}>
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>

            {scriptTabs.map(({ format, label, script }) => (
              <TabsContent key={format} value={format} className="mt-4">
                <div className="relative">
                  <pre className="overflow-auto rounded-md bg-muted p-4 pr-24 font-mono text-sm">
                    {script}
                  </pre>
                  <CopyButton
                    value={script}
                    label="Copy"
                    className="absolute right-2 top-2"
                  />
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {label} export script — paste it into your terminal before running AWS commands.
                </p>
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex flex-col gap-4 sm:flex-row">
        <Button onClick={downloadScript} variant="outline" className="flex-1">
          <Download className="mr-2 h-4 w-4" />
          Download Script
        </Button>
        <Button onClick={onNewRequest} className="flex-1">
          <RotateCcw className="mr-2 h-4 w-4" />
          Start New Request
        </Button>
      </div>

      {/* Security Notice */}
      <Card className="border-warning/40 bg-warning/5">
        <CardContent className="flex items-start gap-3 pt-6">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
          <p className="text-sm text-foreground">
            <strong>Security Notice:</strong> These credentials will expire automatically. Never share
            your credentials or commit them to version control. All credential issuance is logged
            for audit purposes.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
