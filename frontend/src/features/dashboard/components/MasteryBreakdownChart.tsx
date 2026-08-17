// Mastery Breakdown Chart - shows category-level mastery bars

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Card, CardContent, CardHeader } from '../../../shared/components/Card'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { EmptyState } from '../../../shared/components/EmptyState'
import { masteryStop } from '../../../shared/utils/masteryColor'
import type { CategoryMastery } from '../../../api/types'

interface MasteryBreakdownChartProps {
  data?: CategoryMastery[]
  isLoading: boolean
  error?: Error | null
}

// PRD Section 20.3: single mastery color gradient, not a categorical palette
function getBarColor(masteryScore: number): string {
  return masteryStop(masteryScore).hex
}

function formatCategory(category: string): string {
  // Convert COLLOCATION -> Collocation, etc.
  return category.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase())
}

export function MasteryBreakdownChart({ data, isLoading, error }: MasteryBreakdownChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <h2 className="font-serif text-lg text-ink">Mastery by Category</h2>
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
          <h2 className="font-serif text-lg text-ink">Mastery by Category</h2>
        </CardHeader>
        <CardContent>
          <p className="text-danger-text">Failed to load mastery data</p>
        </CardContent>
      </Card>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <h2 className="font-serif text-lg text-ink">Mastery by Category</h2>
        </CardHeader>
        <CardContent>
          <EmptyState
            title="No items yet"
            description="Start learning to see your mastery breakdown"
          />
        </CardContent>
      </Card>
    )
  }

  const chartData = data.map(item => ({
    name: formatCategory(item.category),
    mastery: item.mastery_score * 100, // Convert to percentage
    count: item.item_count,
    reviews: item.total_reviews,
    fill: getBarColor(item.mastery_score),
  }))

  return (
    <Card>
      <CardHeader>
        <h2 className="font-serif text-lg text-ink">Mastery by Category</h2>
        <p className="text-sm text-ink-muted">
          Weighted by review count, decayed
        </p>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 80, bottom: 5 }}>
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fill: '#ACA99F' }} />
              <YAxis type="category" dataKey="name" width={70} tick={{ fontSize: 12, fill: "#ACA99F" }} />
              <Tooltip
                formatter={(value) => {
                  const num = typeof value === 'number' ? value : 0
                  return [`${num.toFixed(1)}%`, 'Mastery']
                }}
                labelFormatter={(label) => String(label)}
                content={({ payload }) => {
                  if (!payload || payload.length === 0) return null
                  const data = payload[0].payload
                  return (
                    <div className="bg-surface p-3 border border-border rounded-lg">
                      <p className="font-medium">{data.name}</p>
                      <p className="text-sm text-ink-muted">Mastery: {data.mastery.toFixed(1)}%</p>
                      <p className="text-sm text-ink-muted">Items: {data.count}</p>
                      <p className="text-sm text-ink-muted">Reviews: {data.reviews}</p>
                    </div>
                  )
                }}
              />
              <Bar dataKey="mastery" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className="mt-4 flex items-center gap-4 text-sm text-ink-muted">
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded" style={{ backgroundColor: getBarColor(0.15) }} />
            <span>0-33%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded" style={{ backgroundColor: getBarColor(0.5) }} />
            <span>33-67%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded" style={{ backgroundColor: getBarColor(0.85) }} />
            <span>67-100%</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}