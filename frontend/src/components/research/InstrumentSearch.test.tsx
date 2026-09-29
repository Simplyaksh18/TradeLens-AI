import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { InstrumentSearch } from './InstrumentSearch'
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

describe('InstrumentSearch', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('debounces search input before calling the API', async () => {
    const searchSpy = vi.spyOn(instrumentsApi, 'searchInstruments').mockResolvedValue({ results: [RELIANCE] })
    const user = userEvent.setup()

    render(<InstrumentSearch onSelect={vi.fn()} />)
    await user.type(screen.getByRole('combobox'), 'REL')

    // Immediately after typing, the debounce window (300ms) has not elapsed.
    expect(searchSpy).not.toHaveBeenCalled()

    await waitFor(() => expect(searchSpy).toHaveBeenCalledTimes(1), { timeout: 1000 })
    expect(searchSpy).toHaveBeenCalledWith('REL', expect.objectContaining({ limit: 20 }))
  })

  it('renders search results', async () => {
    vi.spyOn(instrumentsApi, 'searchInstruments').mockResolvedValue({ results: [RELIANCE] })
    const user = userEvent.setup()

    render(<InstrumentSearch onSelect={vi.fn()} />)
    await user.type(screen.getByRole('combobox'), 'REL')

    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByText('Reliance Industries Limited')).toBeInTheDocument()
  })

  it('calls onSelect with the actual instrument data when a result is chosen', async () => {
    vi.spyOn(instrumentsApi, 'searchInstruments').mockResolvedValue({ results: [RELIANCE] })
    const onSelect = vi.fn()
    const user = userEvent.setup()

    render(<InstrumentSearch onSelect={onSelect} />)
    await user.type(screen.getByRole('combobox'), 'REL')
    await waitFor(() => screen.getByText('RELIANCE'))
    await user.click(screen.getByText('RELIANCE'))

    expect(onSelect).toHaveBeenCalledWith(RELIANCE)
  })

  it('shows an empty state when no instruments match', async () => {
    vi.spyOn(instrumentsApi, 'searchInstruments').mockResolvedValue({ results: [] })
    const user = userEvent.setup()

    render(<InstrumentSearch onSelect={vi.fn()} />)
    await user.type(screen.getByRole('combobox'), 'ZZZ')

    await waitFor(() => expect(screen.getByText(/no matching instruments/i)).toBeInTheDocument())
  })

  it('shows an error state when the search fails', async () => {
    const { ApiError } = await import('../../api/client')
    vi.spyOn(instrumentsApi, 'searchInstruments').mockRejectedValue(new ApiError(503, 'PROVIDER_UNAVAILABLE', 'Down.'))
    const user = userEvent.setup()

    render(<InstrumentSearch onSelect={vi.fn()} />)
    await user.type(screen.getByRole('combobox'), 'REL')

    await waitFor(() => expect(screen.getByText('Down.')).toBeInTheDocument())
  })
})
