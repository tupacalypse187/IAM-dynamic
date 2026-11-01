/**
 * JSON preview themes for the Monaco policy viewer. Monaco-free: this module
 * is pure data plus a resolver so node tests can import it. Registration
 * against a real monaco instance happens in policy-editor.tsx.
 */

export interface CodeThemeOption {
  /** Monaco theme id ('match' follows the app theme). */
  id: string
  label: string
  /** Whether the theme is a dark one (used to group the picker). */
  dark: boolean
}

export const MATCH_CODE_THEME = 'match'

export const CODE_THEMES: CodeThemeOption[] = [
  { id: 'match', label: 'Match app theme', dark: true },
  { id: 'vs-dark', label: 'VS Code Dark', dark: true },
  { id: 'iam-one-dark', label: 'One Dark', dark: true },
  { id: 'iam-github-dark', label: 'GitHub Dark', dark: true },
  { id: 'iam-solarized-dark', label: 'Solarized Dark', dark: true },
  { id: 'vs', label: 'VS Code Light', dark: false },
  { id: 'iam-github-light', label: 'GitHub Light', dark: false },
  { id: 'iam-solarized-light', label: 'Solarized Light', dark: false },
]

export interface MonacoThemeRule {
  token: string
  foreground?: string
  fontStyle?: string
}

export interface MonacoThemeData {
  base: 'vs' | 'vs-dark'
  inherit: boolean
  rules: MonacoThemeRule[]
  colors: Record<string, string>
}

/**
 * Custom themes registered via monaco.editor.defineTheme. Stock 'vs' and
 * 'vs-dark' are built in and need no entry. Each palette gives JSON keys,
 * strings, numbers, and keywords distinct hues — no brown-on-black.
 */
export const CUSTOM_MONACO_THEMES: Record<string, MonacoThemeData> = {
  'iam-one-dark': {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'string.key', foreground: 'e06c75' },
      { token: 'string.value', foreground: '98c379' },
      { token: 'string', foreground: '98c379' },
      { token: 'number', foreground: 'd19a66' },
      { token: 'keyword', foreground: 'c678dd' },
      { token: 'comment', foreground: '5c6370' },
    ],
    colors: { 'editor.background': '#282c34', 'editor.foreground': '#abb2bf' },
  },
  'iam-github-dark': {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'string.key', foreground: '79c0ff' },
      { token: 'string.value', foreground: 'a5d6ff' },
      { token: 'string', foreground: 'a5d6ff' },
      { token: 'number', foreground: '79c0ff' },
      { token: 'keyword', foreground: 'ff7b72' },
      { token: 'comment', foreground: '8b949e' },
    ],
    colors: { 'editor.background': '#0d1117', 'editor.foreground': '#e6edf3' },
  },
  'iam-solarized-dark': {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'string.key', foreground: '268bd2' },
      { token: 'string.value', foreground: '2aa198' },
      { token: 'string', foreground: '2aa198' },
      { token: 'number', foreground: 'd33682' },
      { token: 'keyword', foreground: '859900' },
      { token: 'comment', foreground: '586e75' },
    ],
    colors: { 'editor.background': '#002b36', 'editor.foreground': '#839496' },
  },
  'iam-github-light': {
    base: 'vs',
    inherit: true,
    rules: [
      { token: 'string.key', foreground: '0550ae' },
      { token: 'string.value', foreground: '0a3069' },
      { token: 'string', foreground: '0a3069' },
      { token: 'number', foreground: '0550ae' },
      { token: 'keyword', foreground: 'cf222e' },
      { token: 'comment', foreground: '59636e' },
    ],
    colors: { 'editor.background': '#ffffff', 'editor.foreground': '#1f2328' },
  },
  'iam-solarized-light': {
    base: 'vs',
    inherit: true,
    rules: [
      { token: 'string.key', foreground: '268bd2' },
      { token: 'string.value', foreground: '2aa198' },
      { token: 'string', foreground: '2aa198' },
      { token: 'number', foreground: 'd33682' },
      { token: 'keyword', foreground: '859900' },
      { token: 'comment', foreground: '93a1a1' },
    ],
    colors: { 'editor.background': '#fdf6e3', 'editor.foreground': '#657b83' },
  },
}

/**
 * Resolve a stored code-theme pref to a Monaco theme id. Unknown ids fall
 * back to following the app theme so a stale pref never breaks the viewer.
 */
export function resolveCodeTheme(pref: string, appDark: boolean): string {
  if (pref === MATCH_CODE_THEME || !CODE_THEMES.some((t) => t.id === pref)) {
    return appDark ? 'vs-dark' : 'vs'
  }
  return pref
}
