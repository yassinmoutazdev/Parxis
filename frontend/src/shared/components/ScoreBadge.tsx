interface ScoreBadgeProps {
  score: number // 0-1 for mastery, 0-100 for writing scores
  type: 'mastery' | 'writing'
  showLabel?: boolean
}

export function ScoreBadge({ score, type, showLabel = true }: ScoreBadgeProps) {
  const percentage = type === 'mastery' ? Math.round(score * 100) : Math.round(score)

  // Color gradient based on score
  const getColor = () => {
    if (type === 'mastery') {
      if (score >= 0.8) return 'bg-green-100 text-green-800'
      if (score >= 0.5) return 'bg-yellow-100 text-yellow-800'
      return 'bg-red-100 text-red-800'
    } else {
      if (score >= 80) return 'bg-green-100 text-green-800'
      if (score >= 50) return 'bg-yellow-100 text-yellow-800'
      return 'bg-red-100 text-red-800'
    }
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getColor()}`}>
      {percentage}%
      {showLabel && (
        <span className="ml-1">
          {type === 'mastery' ? 'mastery' : 'score'}
        </span>
      )}
    </span>
  )
}