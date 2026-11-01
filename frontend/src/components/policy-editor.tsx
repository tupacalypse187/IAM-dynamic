import { useEffect, useState } from 'react'
import Editor, { DiffEditor, type OnMount } from '@monaco-editor/react'
import '@/lib/monaco'
import { useTheme } from '@/hooks/use-theme'

/**
 * Lazy-loaded Monaco editors. Imported via React.lazy from the review
 * view so the ~1.3 MB (gz) Monaco payload only downloads when a policy
 * is actually being reviewed — never on first paint.
 */

/** Follow the app theme: Monaco's stock dark theme for dark/system-dark. */
function useMonacoTheme(): 'light' | 'vs-dark' {
  const { theme } = useTheme()
  const [systemDark, setSystemDark] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setSystemDark(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return theme === 'dark' || (theme === 'system' && systemDark) ? 'vs-dark' : 'light'
}

interface ViewerProps {
  json: string
  riskyLines: number[]
}

export function PolicyJsonViewer({ json, riskyLines }: ViewerProps) {
  const monacoTheme = useMonacoTheme()
  const handleMount: OnMount = (editor, monaco) => {
    if (riskyLines.length === 0) return
    editor.deltaDecorations(
      [],
      riskyLines.map((line) => ({
        range: new monaco.Range(line, 1, line, 1),
        options: {
          isWholeLine: true,
          className: 'iam-risk-line',
          glyphMarginClassName: 'iam-risk-glyph',
          hoverMessage: { value: 'Wildcard detected — verify this scope is intentional.' },
        },
      })),
    )
  }

  return (
    <Editor
      height="420px"
      language="json"
      theme={monacoTheme}
      value={json}
      onMount={handleMount}
      options={{
        readOnly: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 13,
        glyphMargin: riskyLines.length > 0,
      }}
    />
  )
}

export function PolicyDiffViewer({ original, modified }: { original: string; modified: string }) {
  const monacoTheme = useMonacoTheme()
  return (
    <DiffEditor
      height="420px"
      language="json"
      theme={monacoTheme}
      original={original}
      modified={modified}
      options={{ readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 13 }}
    />
  )
}
