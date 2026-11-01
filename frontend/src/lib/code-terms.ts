/**
 * Wrap AWS technical terms (IAM actions, ARNs) in markdown code spans so
 * they stand out in rendered prose. Segments already inside backticks are
 * left alone; plain English (including words like "Note:") is untouched.
 */
const TERM_RE =
  /\b(arn:[^\s,;)]*[^\s,;).]|[a-z0-9]+:(?:[A-Za-z][A-Za-z0-9]*\*?|\*))(?![\w*])/g

export function highlightTechnicalTerms(text: string): string {
  if (!text.includes(':')) return text
  return text
    .split(/(`[^`]*`)/g)
    .map((segment, i) =>
      i % 2 === 1 ? segment : segment.replace(TERM_RE, '`$1`'),
    )
    .join('')
}
