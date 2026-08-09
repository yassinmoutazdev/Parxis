// Proficiency Card - displays CEFR band as headline metric

import { Card, CardContent, CardHeader } from '../../../shared/components/Card'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { masteryStop } from '../../../shared/utils/masteryColor'
import type { DashboardOverview, CefrBand, CefrTrend } from '../../../api/types'

// CEFR band colors (consistent gradient approach, not stoplight)
function getCefrColor(band: CefrBand): string {
  if (!band) return '#6B6963' // ink-faint
  const colors: Record<Exclude<CefrBand, null>, string> = {
    'A1': '#8B5CF6',  // purple
    'A2': '#3B82F6',  // blue
    'B1': '#10B981',  // emerald
    'B2': '#F59E0B',  // amber
    'C1': '#EF4444',  // red
    'C2': '#EC4899',  // pink
  }
  return colors[band]
}

function getTrendIcon(trend: CefrTrend): string {
  switch (trend) {
    case 'up': return '↑'
    case 'down': return '↓'
    default: return '→'
  }
}

function getTrendColor(trend: CefrTrend): string {
  switch (trend) {
    case 'up': return 'text-accent'
    case 'down': return 'text-red-500'
    default: return 'text-ink-muted'
  }
}

interface ProficiencyCardProps {
  data?: DashboardOverview
  isLoading: boolean
  error?: Error | null
}

export function ProficiencyCard({ data, isLoading, error }: ProficiencyCardProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <h2 className="font-serif text-lg text-ink">CEFR Proficiency</h2>
        </CardHeader>
        <CardContent>
          <LoadingSpinner />
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <h2 className="font-serif text-lg text-ink">CEFR Proficiency</h2>
        </CardHeader>
        <CardContent>
          <p className="text-red-600">Failed to load proficiency data</p>
        </CardContent>
      </Card>
    )
  }

  const proficiency = data?.proficiency
  const masteryIndex = data?.mastery_index

  return (
    <Card>
      <CardHeader>
        <h2 className="font-serif text-lg text-ink">CEFR Proficiency</h2>
        <p className="text-sm text-ink-muted">
          Based on weekly writing evaluations with hysteresis
        </p>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4">
          {proficiency?.band ? (
            <div className="flex items-center gap-2">
              <span
                className="text-5xl font-medium"
                style={{ color: getCefrColor(proficiency.band) }}
              >
                {proficiency.band}
              </span>
              <span
                className={`text-xl font-medium ${getTrendColor(proficiency.trend)}`}
              >
                {getTrendIcon(proficiency.trend)}
              </span>
            </div>
          ) : (
            <span className="text-5xl font-medium text-ink-muted">—</span>
          )}

          {proficiency?.last_eval_week_start && (
            <span className="text-sm text-ink-muted ml-auto">
              Last eval: {proficiency.last_eval_week_start}
            </span>
          )}
        </div>

        {/* Mastery index (legacy blended metric) */}
        {masteryIndex !== null && masteryIndex !== undefined && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-sm text-ink-muted mb-1">Mastery Index (legacy)</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-medium" style={{ color: masteryStop(masteryIndex).hex }}>
                {Math.round(masteryIndex * 100)}%
              </span>
            </div>
          </div>
        )}

        {/* Week snapshot */}
        {data?.week_snapshot && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-sm font-medium text-ink mb-2">This Week</p>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-ink-muted">Items Studied</p>
                <p className="font-medium">{data.week_snapshot.items_studied}</p>
              </div>
              <div>
                <p className="text-ink-muted">Quiz Sessions</p>
                <p className="font-medium">{data.week_snapshot.quiz_sessions}</p>
              </div>
              <div>
                <p className="text-ink-muted">Writing</p>
                <p className="font-medium">{data.week_snapshot.writing_submissions}</p>
              </div>
            </div>
          </div>
        )}

        {/* Health status */}
        {data?.health && (
          <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  data.health.status === 'ok' ? 'bg-accent' : 'bg-amber-500'
                }`}
              />
              <span className="text-sm text-ink-muted">
                Vault Watcher: {data.health.vault_watcher}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}