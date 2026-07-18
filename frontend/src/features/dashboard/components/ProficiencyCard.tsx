// Proficiency Card - displays overall estimated proficiency

import { Card, CardContent, CardHeader } from '../../../shared/components/Card'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import type { DashboardOverview } from '../../../api/types'

interface ProficiencyCardProps {
  data?: DashboardOverview
  isLoading: boolean
  error?: Error | null
}

// Single mastery color gradient: low (warm/neutral) to high (cool/blue)
// PRD Section 20.3: "single mastery/score gradient (not stoplight red/yellow/green)"
function getMasteryColor(score: number | null): string {
  if (score === null) return 'text-gray-400'

  // Gradient from warm (0.0) to cool blue (1.0)
  // Using a neutral-to-blue gradient that doesn't imply "pass/fail"
  if (score < 0.3) return 'text-orange-600'
  if (score < 0.5) return 'text-amber-600'
  if (score < 0.7) return 'text-blue-500'
  return 'text-indigo-600'
}

function formatProficiency(score: number | null): string {
  if (score === null) return '--'

  // Convert to 0-100 scale for display
  const percentage = Math.round(score * 100)
  return `${percentage}%`
}

export function ProficiencyCard({ data, isLoading, error }: ProficiencyCardProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Estimated Proficiency</h2>
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
          <h2 className="text-lg font-semibold text-gray-900">Estimated Proficiency</h2>
        </CardHeader>
        <CardContent>
          <p className="text-red-600">Failed to load proficiency data</p>
        </CardContent>
      </Card>
    )
  }

  const proficiency = data?.proficiency ?? null

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Estimated Proficiency</h2>
        <p className="text-sm text-gray-500">
          40% item mastery / 60% writing performance
        </p>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <span className={`text-5xl font-bold ${getMasteryColor(proficiency)}`}>
            {formatProficiency(proficiency)}
          </span>
        </div>

        {/* Week snapshot */}
        {data?.week_snapshot && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm font-medium text-gray-700 mb-2">This Week</p>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Items Studied</p>
                <p className="font-medium">{data.week_snapshot.items_studied}</p>
              </div>
              <div>
                <p className="text-gray-500">Quiz Sessions</p>
                <p className="font-medium">{data.week_snapshot.quiz_sessions}</p>
              </div>
              <div>
                <p className="text-gray-500">Writing</p>
                <p className="font-medium">{data.week_snapshot.writing_submissions}</p>
              </div>
            </div>
          </div>
        )}

        {/* Health status */}
        {data?.health && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  data.health.status === 'ok' ? 'bg-green-500' : 'bg-yellow-500'
                }`}
              />
              <span className="text-sm text-gray-500">
                Vault Watcher: {data.health.vault_watcher}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}