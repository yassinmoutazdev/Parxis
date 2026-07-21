import type { WritingPrompt } from '../../../api/types'

interface WritingPromptCardProps {
  prompt: WritingPrompt
}

export default function WritingPromptCard({ prompt }: WritingPromptCardProps) {
  return (
    <div className="p-6 bg-accent-tint border border-accent/30 rounded-lg">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-medium uppercase tracking-wide text-accent-text">
          {prompt.prompt_type} Writing
        </span>
      </div>
      <h2 className="text-xl font-semibold text-ink mb-2">
        {prompt.topic}
      </h2>
      <p className="text-sm text-ink-muted">
        Take your time to write a thoughtful response.
      </p>
    </div>
  )
}