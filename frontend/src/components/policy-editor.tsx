import Editor, { DiffEditor, type OnMount } from '@monaco-editor/react'
import '@/lib/monaco'

/**
 * Lazy-loaded Monaco editors. Imported via React.lazy from the review
 * view so the ~1.3 MB (gz) Monaco payload only downloads when a policy
 * is actually being reviewed — never on first paint.
 */

interface ViewerProps {
  json: string
  riskyLines: number[]
}

export function PolicyJsonViewer({ json, riskyLines }: ViewerProps) {
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
  return (
    <DiffEditor
      height="420px"
      language="json"
      original={original}
      modified={modified}
      options={{ readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 13 }}
    />
  )
}
