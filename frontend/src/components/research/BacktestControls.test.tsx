import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BacktestControls } from './BacktestControls'
import * as instrumentsApi from '../../api/instruments'
import type { Instrument } from '../../api/types'

const RELIANCE: Instrument = {
  symbol: 'RELIANCE',
  exchange: 'NSE',
  name: 'Reliance Industries Limited',
  provider_symbol: 'RELIANCE.NS',
  instrument_type: 'EQUITY',
  status: 'ACTIVE',
  isin: null,
  series: 'EQ',
}

async function selectReliance(user: ReturnType<typeof userEvent.setup>) {
  vi.spyOn(instrumentsApi, 'searchInstruments').mockResolvedValue({ results: [RELIANCE] })
  await user.type(screen.getByRole('combobox'), 'REL')
  const option = await screen.findByText('RELIANCE', {}, { timeout: 1000 })
  await user.click(option)
}

describe('BacktestControls', () => {
  it('does not expose transaction cost, slippage, or interval selection controls', () => {
    render(<BacktestControls onRun={vi.fn()} />)
    expect(screen.queryByLabelText(/transaction cost/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/slippage/i)).not.toBeInTheDocument()
    expect(screen.getByText('1D')).toBeInTheDocument() // fixed, not a selectable control
  })

  it('defaults initial capital to 100000', () => {
    render(<BacktestControls onRun={vi.fn()} />)
    expect(screen.getByLabelText(/Initial Capital/i)).toHaveValue(100000)
  })

  it('rejects running without an instrument selected', async () => {
    const onRun = vi.fn()
    const user = userEvent.setup()
    render(<BacktestControls onRun={onRun} />)

    await user.click(screen.getByRole('button', { name: 'Run Backtest' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/select an instrument/i)
    expect(onRun).not.toHaveBeenCalled()
  })

  it('rejects start date after end date', async () => {
    const onRun = vi.fn()
    const user = userEvent.setup()
    render(<BacktestControls onRun={onRun} />)

    await selectReliance(user)

    const startInput = document.getElementById('range-start') as HTMLInputElement
    const endInput = document.getElementById('range-end') as HTMLInputElement
    await user.clear(startInput)
    await user.type(startInput, '2024-12-31')
    await user.clear(endInput)
    await user.type(endInput, '2024-01-01')

    await user.click(screen.getByRole('button', { name: 'Run Backtest' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/on or before/i)
    expect(onRun).not.toHaveBeenCalled()
  })

  it('rejects non-finite or non-positive initial capital', async () => {
    const onRun = vi.fn()
    const user = userEvent.setup()
    render(<BacktestControls onRun={onRun} />)

    await selectReliance(user)
    const capitalInput = screen.getByLabelText(/Initial Capital/i)
    await user.clear(capitalInput)
    await user.type(capitalInput, '-5')

    await user.click(screen.getByRole('button', { name: 'Run Backtest' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/positive number/i)
    expect(onRun).not.toHaveBeenCalled()
  })

  it('calls onRun with the selected instrument, dates, and capital', async () => {
    const onRun = vi.fn()
    const user = userEvent.setup()
    render(<BacktestControls onRun={onRun} />)

    await selectReliance(user)

    await user.click(screen.getByRole('button', { name: 'Run Backtest' }))

    expect(onRun).toHaveBeenCalledTimes(1)
    const call = onRun.mock.calls[0][0]
    expect(call.instrument.symbol).toBe('RELIANCE')
    expect(call.initialCapital).toBe(100000)
    expect(call.interval).toBe('1d')
    expect(call.start <= call.end).toBe(true)
  })
})
