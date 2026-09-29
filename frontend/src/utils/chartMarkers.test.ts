import { describe, expect, it } from 'vitest'
import { deriveBuyTransitionMarkers } from './chartMarkers'
import type { StrategyEvaluation } from '../api/types'

function evaluation(date: string, decision: StrategyEvaluation['decision']): StrategyEvaluation {
  return {
    date,
    strategy_id: 'trend_momentum_v1',
    strategy_name: 'Trend + Momentum v1',
    decision,
    conditions: [],
    missing_inputs: decision === 'INSUFFICIENT_DATA' ? ['sma50'] : [],
  }
}

describe('deriveBuyTransitionMarkers', () => {
  it('marks only the first day of each consecutive BUY run', () => {
    // NO_SIGNAL, BUY, BUY, BUY, NO_SIGNAL, BUY -- from the task specification
    const evaluations = [
      evaluation('2026-01-01', 'NO_SIGNAL'),
      evaluation('2026-01-02', 'BUY'),
      evaluation('2026-01-03', 'BUY'),
      evaluation('2026-01-04', 'BUY'),
      evaluation('2026-01-05', 'NO_SIGNAL'),
      evaluation('2026-01-06', 'BUY'),
    ]

    const markers = deriveBuyTransitionMarkers(evaluations)

    expect(markers.map((m) => m.date)).toEqual(['2026-01-02', '2026-01-06'])
    expect(markers[0].runLength).toBe(3)
    expect(markers[1].runLength).toBe(1)
  })

  it('is deterministic and does not mutate the input evaluations', () => {
    const evaluations = [
      evaluation('2026-01-01', 'BUY'),
      evaluation('2026-01-02', 'BUY'),
      evaluation('2026-01-03', 'NO_SIGNAL'),
    ]
    const snapshot = JSON.parse(JSON.stringify(evaluations))

    const first = deriveBuyTransitionMarkers(evaluations)
    const second = deriveBuyTransitionMarkers(evaluations)

    expect(first).toEqual(second)
    expect(evaluations).toEqual(snapshot)
  })

  it('treats INSUFFICIENT_DATA the same as NO_SIGNAL for run-breaking purposes', () => {
    const evaluations = [
      evaluation('2026-01-01', 'INSUFFICIENT_DATA'),
      evaluation('2026-01-02', 'BUY'),
      evaluation('2026-01-03', 'INSUFFICIENT_DATA'),
      evaluation('2026-01-04', 'BUY'),
    ]

    const markers = deriveBuyTransitionMarkers(evaluations)

    expect(markers.map((m) => m.date)).toEqual(['2026-01-02', '2026-01-04'])
  })

  it('produces one marker for a run that starts at the very first evaluation', () => {
    const evaluations = [evaluation('2026-01-01', 'BUY'), evaluation('2026-01-02', 'BUY')]
    const markers = deriveBuyTransitionMarkers(evaluations)
    expect(markers.map((m) => m.date)).toEqual(['2026-01-01'])
    expect(markers[0].runLength).toBe(2)
  })

  it('produces no markers when there are no BUY evaluations', () => {
    const evaluations = [evaluation('2026-01-01', 'NO_SIGNAL'), evaluation('2026-01-02', 'INSUFFICIENT_DATA')]
    expect(deriveBuyTransitionMarkers(evaluations)).toEqual([])
  })

  it('matches the real SBICARD-shaped case: a single 19-day BUY run produces exactly one marker', () => {
    const evaluations = [
      evaluation('2026-07-16', 'NO_SIGNAL'),
      ...Array.from({ length: 19 }, (_, i) => evaluation(`run-day-${i}`, 'BUY')),
      evaluation('2026-08-13', 'NO_SIGNAL'),
    ]
    const markers = deriveBuyTransitionMarkers(evaluations)
    expect(markers).toHaveLength(1)
    expect(markers[0].runLength).toBe(19)
  })
})
