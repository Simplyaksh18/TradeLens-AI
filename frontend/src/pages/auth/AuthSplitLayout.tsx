import type { ReactNode } from 'react'
import { Database, GitBranch, LineChart, ShieldCheck } from 'lucide-react'
import { Footer } from '../../components/layout/Footer'

const PIPELINE = [
  { icon: Database, label: 'Historical Market Data' },
  { icon: LineChart, label: 'Technical Indicators' },
  { icon: GitBranch, label: 'Strategy Logic' },
  { icon: ShieldCheck, label: 'Explainable Decisions' },
]

/** Purely decorative, abstract motion line — NOT real market data (no axis,
 * no price values, no candles). Gives the product panel some visual weight
 * beyond plain text rows without faking a real chart's precision. */
function AbstractMotionLine() {
  return (
    <svg
      viewBox="0 0 400 120"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-0 bottom-0 h-28 w-full text-[var(--accent)] opacity-[0.12]"
    >
      <path
        d="M0 90 L40 78 L80 85 L120 55 L160 62 L200 30 L240 42 L280 18 L320 26 L360 8 L400 15"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function AuthSplitLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--surface-0)]">
      <div className="flex flex-1 flex-col lg:flex-row">
        <div
          className="relative flex flex-1 flex-col justify-center gap-9 overflow-hidden border-b border-[var(--border)] bg-[var(--surface-1)] px-8 py-12 lg:border-b-0 lg:border-r lg:px-16"
          style={{
            backgroundImage:
              'radial-gradient(var(--border) 1px, transparent 1px)',
            backgroundSize: '22px 22px',
            backgroundPosition: '-11px -11px',
          }}
        >
          <div className="relative z-10 flex flex-col gap-9">
            <div>
              <span className="text-xl font-semibold tracking-tight text-[var(--text-primary)]">TradeLens</span>
              <span className="ml-1 text-xl font-semibold tracking-tight text-[var(--accent)]">AI</span>
            </div>

            <div className="space-y-1">
              <h1 className="text-3xl font-semibold leading-tight tracking-tight text-[var(--text-primary)]">
                Research strategies.
              </h1>
              <h1 className="text-3xl font-semibold leading-tight tracking-tight text-[var(--text-primary)]">
                Inspect evidence.
              </h1>
              <h1 className="text-3xl font-semibold leading-tight tracking-tight text-[var(--text-primary)]">
                Validate decisions.
              </h1>
            </div>

            <div className="space-y-0">
              {PIPELINE.map((step, i) => (
                <div key={step.label} className="flex items-center gap-3">
                  <div className="flex flex-col items-center">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--surface-2)]">
                      <step.icon size={16} className="text-[var(--accent)]" aria-hidden="true" />
                    </div>
                    {i < PIPELINE.length - 1 && <div className="h-5 w-px bg-[var(--border-strong)]" aria-hidden="true" />}
                  </div>
                  <span className="pb-5 text-sm text-[var(--text-secondary)]">{step.label}</span>
                </div>
              ))}
            </div>

            <div className="max-w-md rounded-md border border-[var(--warning)]/30 bg-[var(--warning-soft)] p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--warning)]">
                Research &amp; Education Only
              </p>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
                TradeLens is designed for studying historical market data, testing deterministic strategy
                logic and understanding why signals occurred. It is not a brokerage service and does not
                provide personalized investment advice.
              </p>
            </div>
          </div>

          <AbstractMotionLine />
        </div>

        <div className="flex flex-1 items-center justify-center px-6 py-12">
          <div className="w-full max-w-sm motion-safe:animate-[auth-fade-in_0.35s_ease-out]">{children}</div>
        </div>
      </div>

      <Footer />
    </div>
  )
}
