import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** Renders Groq-generated synthesis text as safe Markdown. No raw-HTML
 * plugin (e.g. rehype-raw) is used, so any HTML/script markup embedded in
 * model output is displayed as inert plain text, never parsed or executed
 * -- this is react-markdown's default behavior, not an opt-in setting.
 * GFM (tables, strikethrough, task lists) is supported via remark-gfm.
 * Styling uses only existing TradeLens design-system CSS variables. */
const COMPONENTS: Components = {
  p: ({ children }) => <p className="text-sm leading-relaxed text-[var(--text-primary)]">{children}</p>,
  h1: ({ children }) => <h3 className="mt-3 text-sm font-semibold text-[var(--text-primary)]">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-3 text-sm font-semibold text-[var(--text-primary)]">{children}</h3>,
  h3: ({ children }) => <h4 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{children}</h4>,
  h4: ({ children }) => <h4 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{children}</h4>,
  strong: ({ children }) => <strong className="font-semibold text-[var(--text-primary)]">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-[var(--text-primary)]">{children}</ul>,
  ol: ({ children }) => <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-sm text-[var(--text-primary)]">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  code: ({ children }) => (
    <code className="rounded bg-[var(--surface-2)] px-1 py-0.5 font-mono-tabular text-[12px] text-[var(--text-primary)]">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="mt-2 overflow-x-auto rounded-md bg-[var(--surface-2)] p-2 text-[12px] text-[var(--text-primary)]">{children}</pre>
  ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer noopener" className="text-[var(--accent)] underline">
      {children}
    </a>
  ),
  // No `whitespace-nowrap` here -- a prose cell (e.g. a strategy-condition
  // description) previously never wrapped, forcing the whole table
  // absurdly wide with the browser stretching other columns to fill the
  // remaining space. Cells now wrap naturally with a sane per-cell max
  // width; `overflow-x-auto` on the wrapper remains a safety net only for
  // genuinely wide tables (many columns), not the normal case.
  table: ({ children }) => (
    <div className="mt-2 w-full overflow-x-auto rounded-md border border-[var(--border)]">
      <table className="w-full table-fixed border-collapse text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-[var(--surface-2)]">{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => <tr className="border-b border-[var(--border)] last:border-0">{children}</tr>,
  th: ({ children }) => (
    <th className="break-words px-2.5 py-1.5 text-left align-top font-semibold text-[var(--text-secondary)]">{children}</th>
  ),
  td: ({ children }) => (
    <td className="break-words px-2.5 py-1.5 text-left align-top text-[var(--text-primary)]">{children}</td>
  ),
}

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="space-y-1">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
