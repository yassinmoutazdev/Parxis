import { useEffect, useState } from 'react'
import { Card, CardHeader, CardContent } from '../../../shared/components/Card'
import { Button } from '../../../shared/components/Button'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { ApiError, getOllamaKey, setOllamaKey } from '../../../api/client'

export function OllamaKeySection() {
  const [masked, setMasked] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [isEditing, setIsEditing] = useState(false)
  const [keyInput, setKeyInput] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  useEffect(() => {
    void loadKey()
  }, [])

  async function loadKey() {
    setIsLoading(true)
    setLoadError(null)
    try {
      const result = await getOllamaKey()
      setMasked(result.masked)
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : 'Failed to load key status.')
    } finally {
      setIsLoading(false)
    }
  }

  function startEditing() {
    setKeyInput('')
    setSaveError(null)
    setSuccessMessage(null)
    setIsEditing(true)
  }

  function cancelEditing() {
    setKeyInput('')
    setSaveError(null)
    setIsEditing(false)
  }

  async function handleSave() {
    const trimmed = keyInput.trim()
    if (!trimmed) {
      setSaveError('Enter an API key.')
      return
    }

    setIsSaving(true)
    setSaveError(null)
    try {
      const result = await setOllamaKey(trimmed)
      setMasked(result.masked)
      setSuccessMessage(result.message)
      setIsEditing(false)
      setKeyInput('')
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : 'Failed to save key.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="font-serif text-lg text-ink">Ollama Cloud API key</h2>
        <p className="text-sm text-ink-muted mt-1">
          Used to power quizzes, writing evaluation, and chat coaching.
        </p>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="py-4">
            <LoadingSpinner />
          </div>
        )}

        {!isLoading && loadError && (
          <p className="text-sm text-red-400">{loadError}</p>
        )}

        {!isLoading && !loadError && !isEditing && (
          <div className="flex items-center justify-between gap-3">
            <span className="bg-cream-100 border border-border rounded-lg px-3 py-1.5 text-sm text-ink font-mono flex-1 min-w-0">
              {masked || <span className="text-ink-muted">No key configured</span>}
            </span>
            <Button type="button" size="sm" variant="secondary" onClick={startEditing}>
              {masked ? 'Change key…' : 'Add key…'}
            </Button>
          </div>
        )}

        {!isLoading && !loadError && isEditing && (
          <div className="flex flex-col items-start gap-3">
            <input
              type="password"
              autoFocus
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              placeholder="Paste your Ollama Cloud API key"
              className="w-full bg-cream-100 border border-border rounded-lg px-3 py-1.5 text-sm text-ink font-mono focus:outline-none focus:ring-2 focus:ring-accent"
              disabled={isSaving}
            />
            <div className="flex items-center gap-2">
              <Button type="button" size="sm" onClick={handleSave} disabled={isSaving}>
                {isSaving ? 'Verifying…' : 'Save key'}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={cancelEditing}
                disabled={isSaving}
              >
                Cancel
              </Button>
            </div>
            {saveError && <p className="text-sm text-red-400">{saveError}</p>}
          </div>
        )}

        {successMessage && !isEditing && (
          <p className="text-sm text-ink-muted mt-2">{successMessage}</p>
        )}
      </CardContent>
    </Card>
  )
}
