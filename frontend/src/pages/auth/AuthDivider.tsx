export function AuthDivider() {
  return (
    <div className="my-5 flex items-center gap-3 text-xs text-[var(--text-tertiary)]" role="separator">
      <div className="h-px flex-1 bg-[var(--border)]" />
      or
      <div className="h-px flex-1 bg-[var(--border)]" />
    </div>
  )
}
