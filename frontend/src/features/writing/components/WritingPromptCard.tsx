import type { WritingPrompt } from '../../../api/types'

interface WritingPromptCardProps {
  prompt: WritingPrompt
}

export default function WritingPromptCard({ prompt }: WritingPromptCardProps) {
  return (
    <div className="p-6 bg-blue-50 border border-blue-200 rounded-lg">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-medium uppercase tracking-wide text-blue-600">
          {prompt.prompt_type} Writing
        </span>
      </div>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">
        {prompt.topic}
      </h2>
      <p className="text-sm text-gray-500">
        Take your time to write a thoughtful response.
      </p>
    </div>
  )
}