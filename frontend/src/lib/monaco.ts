import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'

/**
 * Bundle Monaco locally instead of the @monaco-editor/react default CDN.
 * Required for desktop/offline use and reproducible builds — the editor
 * must never depend on a third-party CDN at runtime.
 */
loader.config({ monaco })

export { monaco }
