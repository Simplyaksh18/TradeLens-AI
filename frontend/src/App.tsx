import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { ProtectedRoute } from './auth/ProtectedRoute'
import OverviewPage from './pages/OverviewPage'
import DataExplorerPage from './pages/DataExplorerPage'
import StrategyLabPage from './pages/StrategyLabPage'
import BacktestsPage from './pages/BacktestsPage'
import TradeAuditorPage from './pages/TradeAuditorPage'
import FailureInvestigatorPage from './pages/FailureInvestigatorPage'
import ResearchPage from './pages/ResearchPage'
import SettingsPage from './pages/SettingsPage'
import DocumentationPage from './pages/DocumentationPage'
import NotFoundPage from './pages/NotFoundPage'
import LoginPage from './pages/auth/LoginPage'
import SignupPage from './pages/auth/SignupPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<OverviewPage />} />
        <Route path="/data-explorer" element={<DataExplorerPage />} />
        <Route path="/strategy-lab" element={<StrategyLabPage />} />
        <Route path="/backtests" element={<BacktestsPage />} />
        <Route path="/trade-auditor" element={<TradeAuditorPage />} />
        <Route path="/failure-investigator" element={<FailureInvestigatorPage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/docs" element={<DocumentationPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
