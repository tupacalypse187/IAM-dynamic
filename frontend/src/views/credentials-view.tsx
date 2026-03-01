import { useState, useEffect } from 'react'
import { Copy, Check, Download, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'

interface CredentialsViewProps {
  credentials: {
    access_key_id: string
    secret_access_key: string
    session_token: string
    expiration: string
    region: string
  }
  duration: number
  onNewRequest: () => void
}

export default function CredentialsView({ credentials, duration, onNewRequest }: CredentialsViewProps) {
  const [copied, setCopied] = useState<'bash' | 'powershell' | 'aws-cli' | null>(null)
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

  const copyToClipboard = async (type: 'bash' | 'powershell' | 'aws-cli', text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(type)
      setTimeout(() => setCopied(null), 2000)
    } catch (error) {
      console.error('Failed to copy to clipboard:', error)
      // Optionally show user feedback about the failure
    }
  }

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

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Credentials Issued</h2>
        <p className="text-muted-foreground">
          Your temporary AWS credentials have been successfully issued.
        </p>
      </div>

      {/* Expiration Timer */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Time Remaining</p>
              <p className="text-3xl font-bold">{timeRemaining}</p>
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
              <TabsTrigger value="bash">Bash / Zsh</TabsTrigger>
              <TabsTrigger value="powershell">PowerShell</TabsTrigger>
              <TabsTrigger value="aws-cli">AWS CLI</TabsTrigger>
            </TabsList>

            <TabsContent value="bash" className="mt-4">
              <pre className="overflow-auto rounded-md bg-muted p-4 text-sm">
                {bashScript}
              </pre>
              <Button
                onClick={() => copyToClipboard('bash', bashScript)}
                variant="outline"
                className="mt-2"
              >
                {copied === 'bash' ? (
                  <>
                    <Check className="mr-2 h-4 w-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Copy to Clipboard
                  </>
                )}
              </Button>
            </TabsContent>

            <TabsContent value="powershell" className="mt-4">
              <pre className="overflow-auto rounded-md bg-muted p-4 text-sm">
                {psScript}
              </pre>
              <Button
                onClick={() => copyToClipboard('powershell', psScript)}
                variant="outline"
                className="mt-2"
              >
                {copied === 'powershell' ? (
                  <>
                    <Check className="mr-2 h-4 w-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Copy to Clipboard
                  </>
                )}
              </Button>
            </TabsContent>

            <TabsContent value="aws-cli" className="mt-4">
              <pre className="overflow-auto rounded-md bg-muted p-4 text-sm">
                {awsCli}
              </pre>
              <Button
                onClick={() => copyToClipboard('aws-cli', awsCli)}
                variant="outline"
                className="mt-2"
              >
                {copied === 'aws-cli' ? (
                  <>
                    <Check className="mr-2 h-4 w-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Copy to Clipboard
                  </>
                )}
              </Button>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-4">
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
      <Card className="border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950">
        <CardContent className="pt-6">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            <strong>Security Notice:</strong> These credentials will expire automatically. Never share
            your credentials or commit them to version control. All credential issuance is logged
            for audit purposes.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
