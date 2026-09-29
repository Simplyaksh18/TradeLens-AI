import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DecisionChip } from './DecisionChip'
import type { StrategyDecision } from '../../api/types'

describe('DecisionChip', () => {
  it.each<[StrategyDecision, string]>([
    ['BUY', 'Buy'],
    ['NO_SIGNAL', 'No Signal'],
    ['INSUFFICIENT_DATA', 'Insufficient Data'],
  ])('renders the readable label for %s without changing its meaning', (decision, label) => {
    render(<DecisionChip decision={decision} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('exposes the exact backend decision value as a data attribute', () => {
    render(<DecisionChip decision="INSUFFICIENT_DATA" />)
    expect(screen.getByText('Insufficient Data').closest('[data-decision]')).toHaveAttribute(
      'data-decision',
      'INSUFFICIENT_DATA',
    )
  })

  it('never renders INSUFFICIENT_DATA as NO_SIGNAL', () => {
    render(<DecisionChip decision="INSUFFICIENT_DATA" />)
    expect(screen.queryByText('No Signal')).not.toBeInTheDocument()
  })

  it('never invents SELL, HOLD, or confidence-score language', () => {
    const { container } = render(
      <>
        <DecisionChip decision="BUY" />
        <DecisionChip decision="NO_SIGNAL" />
        <DecisionChip decision="INSUFFICIENT_DATA" />
      </>,
    )
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/sell/i)
    expect(text).not.toMatch(/hold/i)
    expect(text).not.toMatch(/confidence/i)
    expect(text).not.toMatch(/strong buy/i)
  })
})
