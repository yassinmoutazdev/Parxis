// Mastery Breakdown Chart - shows category-level mastery bars

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Card, CardContent, CardHeader } from '../../../shared/components/Card'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { EmptyState } from '../../../shared/components/EmptyState'
import type { CategoryMastery } from '../../../api/types'

interface MasteryBreakdownChartProps {
  data?: CategoryMastery[]
  isLoading: boolean
  error?: Error | null
}

// Single mastery color gradient per PRD Section 20.3
const COLORS = ['#ea580c', '#d97706', '#0284c7', '#4f46e5'] // orange-600, amber-600, blue-600, indigo-600

function getBarColor(masteryScore: number): string {
  if (masteryScore < 0.3) return COLORS[0] // orange
  if (masteryScore < 0.5) return COLORS[1] // amber
  if (masteryScore < 0.7) return COLORS[2] // blue
  return COLORS[3] // indigo
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
          <h2 className="text-lg font-semibold text-gray-900">Mastery by Category</h2>
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
          <h2 className="text-lg font-semibold text-gray-900">Mastery by Category</h2>
        </CardHeader>
        <CardContent>
          <p className="text-red-600">Failed to load mastery data</p>
        </CardContent>
      </Card>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Mastery by Category</h2>
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
        <h2 className="text-lg font-semibold text-gray-900">Mastery by Category</h2>
        <p className="text-sm text-gray-500">
          Weighted by review count, decayed
        </p>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 80, bottom: 5 }}>
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
              <YAxis type="category" dataKey="name" width={70} tick={{ fontSize: 12 }} />
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
                    <div className="bg-white p-3 border border-gray-200 rounded shadow-sm">
                      <p className="font-medium">{data.name}</p>
                      <p className="text-sm text-gray-500">Mastery: {data.mastery.toFixed(1)}%</p>
                      <p className="text-sm text-gray-500">Items: {data.count}</p>
                      <p className="text-sm text-gray-500">Reviews: {data.reviews}</p>
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
        <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-orange-600" />
            <span>0-30%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-amber-600" />
            <span>30-50%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-blue-600" />
            <span>50-70%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-indigo-600" />
            <span>70-100%</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}