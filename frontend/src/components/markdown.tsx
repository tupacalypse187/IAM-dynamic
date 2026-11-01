import { useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { CopyButton } from './copy-button'

function MarkdownPre({ children, ...props }: React.ComponentPropsWithoutRef<'pre'>) {
  const preRef = useRef<HTMLPreElement>(null)
  return (
    <div className="group relative">
      <CopyButton
        value={() => preRef.current?.textContent ?? ''}
        label="Copy"
        variant="secondary"
        className="absolute right-2 top-2 opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
      />
      <pre ref={preRef} {...props}>
        {children}
      </pre>
    </div>
  )
}

/**
 * The one markdown renderer for AI-generated content: GFM tables/lists,
 * code highlighting with per-block copy, theme-aware prose. Every view
 * that shows model output goes through here so formatting is consistent
 * and dark mode always works.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose max-w-none dark:prose-invert prose-custom">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{ pre: MarkdownPre }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
