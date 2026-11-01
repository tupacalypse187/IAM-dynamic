import { useEffect, useState } from 'react'
import Editor, { DiffEditor, type OnMount, type BeforeMount } from '@monaco-editor/react'
import '@/lib/monaco'
import { useTheme } from '@/hooks/use-theme'
import { usePrefs } from '@/hooks/use-prefs'
import { CUSTOM_MONACO_THEMES, resolveCodeTheme } from '@/lib/code-themes'

/**
 * Lazy-loaded Monaco editors. Imported via React.lazy from the review
 * view so the ~1.3 MB (gz) Monaco payload only downloads when a policy
 * is actually being reviewed — never on first paint.
 */

/** Register custom JSON themes once per Monaco load (defineTheme is idempotent). */
const handleBeforeMount: BeforeMount = (monaco) => {
  for (const [id, data] of Object.entries(CUSTOM_MONACO_THEMES)) {
    monaco.editor.defineTheme(id, data)
  }
}

/** Resolve the stored code-theme pref against the effective app theme. */
function useMonacoTheme(): string {
  const { theme } = useTheme()
  const { prefs } = usePrefs()
  const [systemDark, setSystemDark] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setSystemDark(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  const appDark = theme === 'dark' || (theme === 'system' && systemDark)
  return resolveCodeTheme(prefs.codeTheme, appDark)
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
      beforeMount={handleBeforeMount}
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
      beforeMount={handleBeforeMount}
      original={original}
      modified={modified}
      options={{ readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 13 }}
    />
  )
}
