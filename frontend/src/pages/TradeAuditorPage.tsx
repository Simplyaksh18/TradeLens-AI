import { useState } from 'react'
import { PageHeader } from '../components/layout/PageHeader'
import { AuditControls, type AuditSelection } from '../components/research/AuditControls'
import { AuditDecisionHeader } from '../components/research/AuditDecisionHeader'
import { EvidenceInspector } from '../components/research/EvidenceInspector'
import { MarketContext } from '../components/research/MarketContext'
import { PriorSignalEvidence } from '../components/research/PriorSignalEvidence'
import { HistoricalSignalRisk } from '../components/research/HistoricalSignalRisk'
import { RetrospectiveOutcome } from '../components/research/RetrospectiveOutcome'
import { HowThisAuditWorks } from '../components/research/HowThisAuditWorks'
import { StrategyRulesDisclosure } from '../components/research/StrategyRulesDisclosure'
import { Card } from '../components/ui/Card'
import { ApiErrorState, LoadingSkeleton, NothingSelectedState } from '../components/ui/States'
import { useStrategyAudit } from '../hooks/useStrategyAudit'
import { STRATEGY_METADATA } from '../utils/strategyMetadata'

const TREND_MOMENTUM_V1_METADATA = STRATEGY_METADATA.trend_momentum_v1

/** Phase 3E: the Strategy Auditor workspace. Pure display over the accepted
 * Phase 3D `GET /audits/trend-momentum-v1/{symbol}` response -- every
 * number rendered comes verbatim from that response (see CLAUDE.md Phase
 * 3D/3E). This is an auditor, not a chatbot/recommendation/prediction
 * page: no confidence scores, no "Strong Buy"/"Good Trade" language, no
 * similarity/nearest-neighbor matching. */
export default function TradeAuditorPage() {
  const [selection, setSelection] = useState<AuditSelection | null>(null)

  const symbol = selection?.instrument.symbol ?? null
  const start = selection?.evidenceStart ?? ''
  const end = selection?.end ?? ''
  const auditDate = selection?.auditDate ?? ''

  const audit = useStrategyAudit(symbol, start, end, auditDate)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Strategy Auditor"
        description={
          <>
            <p>Audit a strategy decision as it looked on that day.</p>
            <p className="mt-2">
              Select a stock and historical date to see whether the strategy generated a BUY signal, the exact
              conditions behind that decision, the market regime and risk at the time, and how earlier signals from
              the same strategy performed. TradeLens separately shows what happened after the selected date as
              hindsight, so future information is never mixed with the original decision.
            </p>
          </>
        }
      />

      <HowThisAuditWorks />

      <AuditControls onRun={setSelection} />

      {TREND_MOMENTUM_V1_METADATA && <StrategyRulesDisclosure metadata={TREND_MOMENTUM_V1_METADATA} />}

      {!selection && (
        <NothingSelectedState message="Select an instrument, audit date, and evidence start date to run a strategy audit." />
      )}

      {selection && audit.loading && (
        <Card className="p-6">
          <LoadingSkeleton lines={5} />
        </Card>
      )}

      {selection && !audit.loading && audit.error && <ApiErrorState error={audit.error} />}

      {selection && !audit.loading && !audit.error && audit.data && (
        <div className="space-y-4">
          <AuditDecisionHeader audit={audit.data} />

          <Card className="p-4">
            <EvidenceInspector evaluation={audit.data.evaluation} />
          </Card>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <MarketContext context={audit.data.risk_market_context} />
            <HistoricalSignalRisk risk={audit.data.historical_signal_risk} />
          </div>

          <PriorSignalEvidence evidence={audit.data.historical_evidence} />

          <div className="border-t border-[var(--border)] pt-4">
            <RetrospectiveOutcome outcome={audit.data.retrospective_outcome} decision={audit.data.evaluation.decision} />
          </div>
        </div>
      )}
    </div>
  )
}
