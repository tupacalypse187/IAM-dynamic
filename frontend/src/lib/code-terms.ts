/**
 * Wrap AWS technical terms (IAM actions, ARNs) in markdown code spans so
 * they stand out in rendered prose. Segments already inside backticks are
 * left alone; plain English (including words like "Note:") is untouched.
 */
const TERM_RE =
  /\b(arn:[^\s,;)]*[^\s,;).]|[a-z0-9]+:(?:[A-Za-z][A-Za-z0-9]*\*?|\*))(?![\w*])/g

// A bare (non-backticked) AWS term wrapped in straight quotes, e.g.
// `'s3:GetObject'` or `"arn:aws:s3:::b/*"`. Quotes are never part of a
// term; ordinary quoted prose has no colon-term inside, so it never
// matches here. Quote chars are excluded from the term so trailing
// punctuation (`,`, `.`, `;`, `:`) and parens stay outside the span.
const QUOTED_TERM_RE =
  /(['"])(arn:[^\s,;)'"]*[^\s,;).'"]|[a-z0-9]+:(?:[A-Za-z][A-Za-z0-9]*\*?|\*))\1/g

export function highlightTechnicalTerms(text: string): string {
  if (!text.includes(':')) return text
  // The model sometimes emits typographic quotes; they are never part of
  // a term, so normalize them before matching (display-only, this text is
  // already rendered prose, not stored source).
  text = text
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
  // The model sometimes emits quote-wrapped terms (`'s3:GetObject'`,
  // `'s3:GetObject`', or '`s3:GetObject`'); quotes are never part of
  // the term, so drop them from around code spans. Quotes must hug a
  // complete span on both sides, so ordinary prose quoting is never
  // touched.
  return text
    .replace(/`'([^']+)'`/g, '`$1`')
    .replace(/`"([^"]+)"`/g, '`$1`')
    .replace(/`'([^'`]+)`'/g, '`$1`')
    .replace(/`"([^"`]+)`"/g, '`$1`')
    .replace(/'(`[^`]+`)'/g, '$1')
    .replace(/"(`[^`]+`)"/g, '$1')
    .split(/(`[^`]*`)/g)
    .map((segment, i) =>
      i % 2 === 1
        ? segment
        : // Strip quotes around bare terms first (turning them into code
          // spans), then wrap any remaining bare terms. The second split
          // keeps the plain-term wrapper from double-wrapping the spans
          // just inserted.
          segment
            .replace(QUOTED_TERM_RE, '`$2`')
            .split(/(`[^`]*`)/g)
            .map((sub, j) => (j % 2 === 1 ? sub : sub.replace(TERM_RE, '`$1`')))
            .join(''),
    )
    .join('')
}
