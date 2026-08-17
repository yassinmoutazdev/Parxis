// Trend Chart - multi-series showing quiz accuracy and writing scores over time

import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from 'recharts'
import { Card, CardContent, CardHeader } from '../../../shared/components/Card'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { EmptyState } from '../../../shared/components/EmptyState'
import type { TrendData } from '../../../api/types'

interface TrendChartProps {
  data?: TrendData
  isLoading: boolean
  error?: Error | null
}

type ChartTab = 'quiz' | 'writing'

// Writing dimensions are categorical (not a score gradient), so each gets
// its own hue - kept muted and warm rather than saturated primary colors.
const WRITING_COLORS = {
  grammar: '#7F77DD',     // purple
  naturalness: '#D85A30', // coral
  vocabulary: '#EF9F27',  // amber
  coherence: '#5DCAA5',   // teal
  overall: '#3D3929',     // ink - the summary line should read as "the answer"
}

const QUIZ_COLOR = '#D97757' // accent

function formatWeekLabel(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function TrendChart({ data, isLoading, error }: TrendChartProps) {
  const [activeTab, setActiveTab] = useState<ChartTab>('quiz')

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <h2 className="font-serif text-lg text-ink">Progress Trends</h2>
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
          <h2 className="font-serif text-lg text-ink">Progress Trends</h2>
        </CardHeader>
        <CardContent>
          <p className="text-danger-text">Failed to load trend data</p>
        </CardContent>
      </Card>
    )
  }

  if (!data || (data.quiz_accuracy.length === 0 && data.writing_scores.length === 0)) {
    return (
      <Card>
        <CardHeader>
          <h2 className="font-serif text-lg text-ink">Progress Trends</h2>
        </CardHeader>
        <CardContent>
          <EmptyState
            title="No trend data yet"
            description="Complete quizzes and writing tasks to see your progress"
          />
        </CardContent>
      </Card>
    )
  }

  const hasQuizData = data.quiz_accuracy.some(q => q.accuracy !== null)
  const hasWritingData = data.writing_scores.some(w => w.overall !== null)

  // Prepare chart data
  const quizChartData = data.quiz_accuracy.map(item => ({
    week: formatWeekLabel(item.week_start),
    accuracy: item.accuracy,
    questions: item.total_questions,
  }))

  const writingChartData = data.writing_scores.map((item, idx) => ({
    week: formatWeekLabel(item.week_start),
    grammar: item.grammar,
    naturalness: item.naturalness,
    vocabulary: item.vocabulary,
    coherence: item.coherence,
    overall: item.overall,
    // Also include quiz accuracy for comparison if available
    quizAccuracy: data.quiz_accuracy[idx]?.accuracy,
  }))

  return (
    <Card>
      <CardHeader>
        <h2 className="font-serif text-lg text-ink">Progress Trends</h2>

        {/* Tab selector */}
        <div className="mt-2 flex gap-2">
          <button
            onClick={() => setActiveTab('quiz')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              activeTab === 'quiz'
                ? 'bg-accent text-white'
                : 'bg-cream-100 text-ink-muted hover:text-ink'
            }`}
          >
            Quiz Accuracy
          </button>
          <button
            onClick={() => setActiveTab('writing')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              activeTab === 'writing'
                ? 'bg-accent text-white'
                : 'bg-cream-100 text-ink-muted hover:text-ink'
            }`}
          >
            Writing Scores
          </button>
        </div>
      </CardHeader>
      <CardContent>
        {activeTab === 'quiz' && (
          <div className="h-72">
            {hasQuizData ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={quizChartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3C3B37" />
                  <XAxis dataKey="week" tick={{ fontSize: 11, fill: "#ACA99F" }} />
                  <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: "#ACA99F" }} />
                  <Tooltip
                    formatter={(value) => {
                      const num = typeof value === 'number' ? value : 0
                      return [`${num?.toFixed(1)}%`, 'Accuracy']
                    }}
                    labelFormatter={(label) => `Week of ${label}`}
                    contentStyle={{ backgroundColor: '#30302E', border: '1px solid #3C3B37', borderRadius: 8 }}
                    labelStyle={{ color: '#ACA99F' }}
                    itemStyle={{ color: '#E8E6DC' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="accuracy"
                    stroke={QUIZ_COLOR}
                    strokeWidth={2}
                    dot={{ fill: QUIZ_COLOR, r: 4 }}
                    name="Quiz Accuracy"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState
                title="No quiz data"
                description="Complete a quiz to see your accuracy trends"
              />
            )}
          </div>
        )}

        {activeTab === 'writing' && (
          <div className="h-72">
            {hasWritingData ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={writingChartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3C3B37" />
                  <XAxis dataKey="week" tick={{ fontSize: 11, fill: "#ACA99F" }} />
                  <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}`} tick={{ fontSize: 11, fill: "#ACA99F" }} />
                  <Tooltip
                    formatter={(value, name) => {
                      const num = typeof value === 'number' ? value : null
                      return [num ? `${num.toFixed(0)}` : '--', String(name)]
                    }}
                    labelFormatter={(label) => `Week of ${label}`}
                    contentStyle={{ backgroundColor: '#30302E', border: '1px solid #3C3B37', borderRadius: 8 }}
                    labelStyle={{ color: '#ACA99F' }}
                    itemStyle={{ color: '#E8E6DC' }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="grammar"
                    stroke={WRITING_COLORS.grammar}
                    strokeWidth={2}
                    dot={false}
                    name="Grammar"
                  />
                  <Line
                    type="monotone"
                    dataKey="naturalness"
                    stroke={WRITING_COLORS.naturalness}
                    strokeWidth={2}
                    dot={false}
                    name="Naturalness"
                  />
                  <Line
                    type="monotone"
                    dataKey="vocabulary"
                    stroke={WRITING_COLORS.vocabulary}
                    strokeWidth={2}
                    dot={false}
                    name="Vocabulary"
                  />
                  <Line
                    type="monotone"
                    dataKey="coherence"
                    stroke={WRITING_COLORS.coherence}
                    strokeWidth={2}
                    dot={false}
                    name="Coherence"
                  />
                  <Line
                    type="monotone"
                    dataKey="overall"
                    stroke={WRITING_COLORS.overall}
                    strokeWidth={3}
                    dot={{ fill: WRITING_COLORS.overall, r: 4 }}
                    name="Overall"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState
                title="No writing data"
                description="Complete a weekly writing assessment to see your score trends"
              />
            )}
          </div>
        )}

        {/* Items learned bar chart summary */}
        <div className="mt-6 pt-4 border-t border-border">
          <h3 className="text-sm font-medium text-ink mb-3">Items Learned Per Week</h3>
          <div className="flex gap-1 h-8">
            {data.items_learned.slice(-8).map((item, idx) => {
              const maxCount = Math.max(...data.items_learned.map(i => i.count), 1)
              const height = Math.max((item.count / maxCount) * 100, 4)
              return (
                <div
                  key={idx}
                  className="flex-1 bg-accent-tint rounded-sm relative group"
                  style={{ height: `${height}%` }}
                  title={`${formatWeekLabel(item.week_start)}: ${item.count} items`}
                >
                  <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-xs text-ink-muted opacity-0 group-hover:opacity-100">
                    {item.count}
                  </div>
                </div>
              )
            })}
          </div>
          <p className="text-xs text-ink-muted mt-2">
            Last 8 weeks
          </p>
        </div>
      </CardContent>
    </Card>
  )
}