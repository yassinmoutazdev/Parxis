import { useState, useCallback } from 'react'

interface WritingEditorProps {
  onSubmit: (text: string) => void
  disabled?: boolean
  placeholder?: string
  minLength?: number
}

export default function WritingEditor({
  onSubmit,
  disabled = false,
  placeholder = 'Start writing...',
  minLength = 10,
}: WritingEditorProps) {
  const [text, setText] = useState('')

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0
  const charCount = text.length
  const canSubmit = text.trim().length >= minLength

  const handleSubmit = useCallback(() => {
    if (canSubmit && !disabled) {
      onSubmit(text.trim())
    }
  }, [text, canSubmit, disabled, onSubmit])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit]
  )

  return (
    <div className="space-y-4">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        onKeyDown={handleKeyDown}
        className="w-full h-64 p-4 bg-surface text-ink placeholder:text-ink-faint border border-border-strong rounded-lg resize-none focus:ring-2 focus:ring-accent focus:border-transparent disabled:bg-cream-100 disabled:cursor-not-allowed"
        aria-label="Writing editor"
      />

      <div className="flex items-center justify-between">
        <div className="text-sm text-ink-muted">
          <span>{wordCount} words</span>
          <span className="mx-2">·</span>
          <span>{charCount} characters</span>
          <span className="mx-2">·</span>
          <span className="text-ink-faint">Ctrl+Enter to submit</span>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!canSubmit || disabled}
          className="px-6 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover disabled:bg-border-strong disabled:cursor-not-allowed transition-colors"
        >
          {disabled ? 'Submitting...' : 'Submit'}
        </button>
      </div>
    </div>
  )
}