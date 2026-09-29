import type { StrategyEvaluation } from '../api/types'

/**
 * Chart marker visualization policy (presentation-only, not a new backend
 * decision): TradeLens's Trend + Momentum v1 evaluates STRATEGY STATE, not
 * ENTRY EVENTS — every date whose conditions are satisfied returns `BUY`
 * independently (see backend `evaluate_trend_momentum_v1`; verified live
 * against SBICARD/RELIANCE, e.g. SBICARD 2026-07-17 through 2026-08-12 is
 * 19 consecutive genuine BUY evaluations from a sustained uptrend, not a
 * bug). Rendering one "BUY" label per qualifying day makes long BUY runs
 * overlap and obscure the chart.
 *
 * This function derives "BUY state begins" markers: one marker per
 * transition into BUY (the first day of each consecutive BUY run), never
 * one per qualifying day. It does NOT invent a new decision type, does NOT
 * change which dates are BUY, and does NOT affect the Historical
 * Evaluations table or Evidence Inspector, which continue to show the
 * backend's true per-date decision unchanged.
 */
export interface BuyTransitionMarker {
  date: string
  runLength: number
}

export function deriveBuyTransitionMarkers(evaluations: StrategyEvaluation[]): BuyTransitionMarker[] {
  const markers: BuyTransitionMarker[] = []
  let previousWasBuy = false
  let currentRunLength = 0

  for (const evaluation of evaluations) {
    const isBuy = evaluation.decision === 'BUY'
    if (isBuy && !previousWasBuy) {
      markers.push({ date: evaluation.date, runLength: 0 })
    }
    if (isBuy) {
      currentRunLength += 1
      markers[markers.length - 1].runLength = currentRunLength
    } else {
      currentRunLength = 0
    }
    previousWasBuy = isBuy
  }

  return markers
}
