// Static, display-only strategy metadata for the Strategy Auditor's "About
// this strategy" disclosure. This is explanatory copy, never a calculation
// -- the actual decision/conditions always come from the Phase 3D API
// response (see components/research/EvidenceInspector.tsx). Keyed by
// strategy_id so a future strategy can add its own entry here without
// touching the Strategy Auditor page itself; this is deliberately a plain
// lookup object, not a registry/plugin framework, per CLAUDE.md Phase 3E's
// "avoid overengineering" guidance.

export interface StrategyMetadata {
  strategyId: string
  strategyName: string
  summary: string
  // Exactly the accepted BUY conditions, in order -- see CLAUDE.md's
  // "Current Approved Quantitative Decisions" for trend_momentum_v1.
  conditions: string[]
  semantics: string[]
}

export const STRATEGY_METADATA: Record<string, StrategyMetadata> = {
  trend_momentum_v1: {
    strategyId: 'trend_momentum_v1',
    strategyName: 'Trend + Momentum v1',
    summary: 'A deterministic long-signal strategy combining trend alignment with RSI momentum.',
    conditions: ['Close > SMA20', 'SMA20 > SMA50', '40 <= RSI(14) <= 70'],
    semantics: [
      'Close > SMA20 is strict.',
      'SMA20 > SMA50 is strict.',
      'The RSI14 lower and upper bounds (40 and 70) are inclusive.',
      'If sufficient indicator history exists but any condition fails, the decision is NO_SIGNAL.',
      'If required indicator history is unavailable, the decision is INSUFFICIENT_DATA.',
      'Evaluated on daily bars using raw Close, never adjusted close.',
      'No SELL signal exists in v1.',
    ],
  },
}

export function getStrategyMetadata(strategyId: string): StrategyMetadata | undefined {
  return STRATEGY_METADATA[strategyId]
}
