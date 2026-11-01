/**
 * Wrap AWS technical terms (IAM actions, ARNs) in markdown code spans so
 * they stand out in rendered prose. Segments already inside backticks are
 * left alone; plain English (including words like "Note:") is untouched.
 */
const TERM_RE =
  /\b(arn:[^\s,;)]*[^\s,;).]|[a-z0-9]+:(?:[A-Za-z][A-Za-z0-9]*\*?|\*))(?![\w*])/g

export function highlightTechnicalTerms(text: string): string {
  if (!text.includes(':')) return text
  // The model sometimes emits quote-wrapped terms (`'s3:GetObject'`
  // or `'s3:GetObject`'); quotes are never part of the term, so drop
  // them from around code spans. Quotes must hug a complete span on
  // both sides, so ordinary prose quoting is never touched.
  return text
    .replace(/`'([^']+)'`/g, '`$1`')
    .replace(/`"([^"]+)"`/g, '`$1`')
    .replace(/`'([^'`]+)`'/g, '`$1`')
    .replace(/`"([^"`]+)`"/g, '`$1`')
    .split(/(`[^`]*`)/g)
    .map((segment, i) =>
      i % 2 === 1 ? segment : segment.replace(TERM_RE, '`$1`'),
    )
    .join('')
}
