import { useState } from 'react'
import { PageHeader } from '../components/layout/PageHeader'
import { InvestigationControls, type InvestigationSelection } from '../components/research/InvestigationControls'
import { HowThisInvestigationWorks } from '../components/research/HowThisInvestigationWorks'
import { InvestigationMethodology } from '../components/research/InvestigationMethodology'
import { InvestigationPopulation } from '../components/research/InvestigationPopulation'
import { OutcomeComparison } from '../components/research/OutcomeComparison'
import { ContextComparison } from '../components/research/ContextComparison'
import { SignalEvidenceTable } from '../components/tables/SignalEvidenceTable'
import { Card, SectionLabel } from '../components/ui/Card'
import { ApiErrorState, LoadingSkeleton, NothingSelectedState } from '../components/ui/States'
import { useStrategyFailureInvestigation } from '../hooks/useStrategyFailureInvestigation'

/** Phase 4F: the Strategy Failure Investigator workspace. Pure display
 * over the accepted Phase 4E `GET /investigations/trend-momentum-v1/
 * {symbol}` response -- every number rendered comes verbatim from that
 * response (see CLAUDE.md Phase 4E/4F). This is retrospective descriptive
 * research over a POPULATION of historical BUY signals, distinct from the
 * Strategy Auditor (which investigates one historical decision/date): no
 * causal, predictive, confidence, or strategy-optimization language
 * anywhere on this page. */
export default function FailureInvestigatorPage() {
  const [selection, setSelection] = useState<InvestigationSelection | null>(null)

  const symbol = selection?.instrument.symbol ?? null
  const start = selection?.start ?? ''
  const end = selection?.end ?? ''

  const investigation = useStrategyFailureInvestigation(symbol, start, end)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Strategy Failure Investigator"
        description="Compare failed and non-failed historical BUY signals using retrospective outcomes and the market context that existed when each signal fired."
      />

      <HowThisInvestigationWorks />

      <InvestigationControls onRun={setSelection} />

      <InvestigationMethodology />

      {!selection && (
        <NothingSelectedState message="Select an instrument and historical date range to run a strategy failure investigation." />
      )}

      {selection && investigation.loading && (
        <Card className="p-6">
          <LoadingSkeleton lines={5} />
        </Card>
      )}

      {selection && !investigation.loading && investigation.error && <ApiErrorState error={investigation.error} />}

      {selection && !investigation.loading && !investigation.error && investigation.data && (
        <div className="space-y-4">
          <div>
            <SectionLabel>Population Overview</SectionLabel>
            <div className="mt-2">
              <InvestigationPopulation investigation={investigation.data} />
            </div>
          </div>

          {investigation.data.total_signal_count === 0 ? (
            <Card className="p-6">
              <p className="text-sm text-[var(--text-secondary)]">
                No historical BUY signals were found for this symbol in the selected research window.
              </p>
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                <OutcomeComparison comparison={investigation.data.outcome_comparison} />
                <ContextComparison context={investigation.data.context_analysis} />
              </div>

              <Card className="p-4">
                <SectionLabel>Historical Signal Evidence</SectionLabel>
                <div className="mt-2">
                  <SignalEvidenceTable observations={investigation.data.context_analysis.observations} />
                </div>
              </Card>
            </>
          )}
        </div>
      )}
    </div>
  )
}
