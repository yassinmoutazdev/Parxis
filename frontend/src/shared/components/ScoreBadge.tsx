import { masteryStop } from '../utils/masteryColor'

interface ScoreBadgeProps {
  score: number // 0-1 for mastery, 0-100 for writing scores
  type: 'mastery' | 'writing'
  showLabel?: boolean
}

export function ScoreBadge({ score, type, showLabel = true }: ScoreBadgeProps) {
  const fraction = type === 'mastery' ? score : score / 100
  const percentage = type === 'mastery' ? Math.round(score * 100) : Math.round(score)
  const { bg, text } = masteryStop(fraction)

  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
      style={{ backgroundColor: bg, color: text }}
    >
      {percentage}%
      {showLabel && (
        <span className="ml-1">
          {type === 'mastery' ? 'mastery' : 'score'}
        </span>
      )}
    </span>
  )
}
