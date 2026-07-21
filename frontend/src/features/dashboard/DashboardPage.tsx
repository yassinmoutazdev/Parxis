// Dashboard Page - composes three independent hooks per ARCHITECTURE Section 6.6

import { useOverview, useMasteryBreakdown, useTrends } from './hooks'
import { ProficiencyCard, MasteryBreakdownChart, TrendChart } from './components'

export default function DashboardPage() {
  // Three independent queries - each resolves progressively as data arrives
  const { data: overviewData, isLoading: overviewLoading, error: overviewError } = useOverview()
  const { data: masteryData, isLoading: masteryLoading, error: masteryError } = useMasteryBreakdown()
  const { data: trendsData, isLoading: trendsLoading, error: trendsError } = useTrends(90)

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="mb-6">
        <h1 className="font-serif text-2xl text-ink">Dashboard</h1>
        <p className="text-ink-muted">Track your learning progress</p>
      </div>

      {/* Pending approvals badge */}
      {overviewData && overviewData.pending_approvals_count > 0 && (
        <div className="mb-4 p-3 bg-accent-tint border border-accent/30 rounded-lg">
          <p className="text-accent-text text-sm">
            You have{' '}
            <span className="font-semibold">{overviewData.pending_approvals_count}</span>
            {' '}items awaiting approval
          </p>
        </div>
      )}

      {/* Dashboard Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Proficiency Card - spans full width on mobile */}
        <div className="lg:col-span-2">
          <ProficiencyCard
            data={overviewData}
            isLoading={overviewLoading}
            error={overviewError}
          />
        </div>

        {/* Mastery Breakdown Chart */}
        <MasteryBreakdownChart
          data={masteryData}
          isLoading={masteryLoading}
          error={masteryError}
        />

        {/* Trend Chart */}
        <TrendChart
          data={trendsData}
          isLoading={trendsLoading}
          error={trendsError}
        />
      </div>
    </div>
  )
}