import { FormEvent, useState } from 'react'
import { Card, CardHeader, CardContent } from '../../../shared/components/Card'
import { Button } from '../../../shared/components/Button'
import { PasswordInput } from '../../../shared/components/PasswordInput'
import { ApiError, setOllamaKey } from '../../../api/client'

interface ConnectScreenProps {
  onConnected: () => void
}

export function ConnectScreen({ onConnected }: ConnectScreenProps) {
  const [keyInput, setKeyInput] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()

    const trimmed = keyInput.trim()
    if (!trimmed) {
      setError('Enter an API key to continue.')
      return
    }

    setIsSaving(true)
    setError(null)
    try {
      await setOllamaKey(trimmed)
      onConnected()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to save key. Try again.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <h1 className="font-serif text-2xl text-ink">Connect to Ollama Cloud</h1>
          <p className="text-sm text-ink-muted mt-2">
            Praxis needs an Ollama Cloud API key to generate quizzes, evaluate writing,
            and power the chat coach.
          </p>
        </div>

        <Card>
          <CardHeader>
            <h2 className="font-serif text-lg text-ink">API key</h2>
            <p className="text-sm text-ink-muted mt-1">
              You can find or create a key at{' '}
              <a
                href="https://ollama.com/settings/keys"
                target="_blank"
                rel="noreferrer"
                className="text-accent hover:underline"
              >
                ollama.com/settings/keys
              </a>
              .
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <PasswordInput
                autoFocus
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="Paste your Ollama Cloud API key"
                inputClassName="bg-cream-100 border border-border rounded-lg px-3 py-2 text-sm text-ink font-mono focus:outline-none focus:ring-2 focus:ring-accent"
                disabled={isSaving}
              />

              {error && <p className="text-sm text-danger-text">{error}</p>}

              <Button type="submit" disabled={isSaving} className="w-full">
                {isSaving ? 'Verifying…' : 'Connect'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-xs text-ink-faint text-center mt-4">
          Your key is stored locally and never leaves your machine except to call Ollama.
        </p>
      </div>
    </div>
  )
}
