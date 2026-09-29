export function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] bg-[var(--surface-1)] px-4 py-2.5 text-xs text-[var(--text-tertiary)]">
      <span>
        © {year} TradeLens AI · research &amp; education only, not investment advice
      </span>
      <span>Built with curiosity, data &amp; code by Akshi 👩‍💻</span>
    </footer>
  )
}
