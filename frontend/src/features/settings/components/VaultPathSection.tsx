import { useEffect, useState } from 'react'
import { Card, CardHeader, CardContent } from '../../../shared/components/Card'
import { Button } from '../../../shared/components/Button'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { ApiError } from '../../../api/client'
import { useConfig, useSetVaultPath } from '../hooks'

export function VaultPathSection() {
  const { data: config, isLoading, error } = useConfig()
  const setVaultPathMutation = useSetVaultPath()

  const [savedPath, setSavedPath] = useState('')
  const [inputPath, setInputPath] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [messageIsError, setMessageIsError] = useState(false)

  useEffect(() => {
    const value = config?.vault_path?.value
    const path = typeof value === 'string' ? value : ''
    setSavedPath(path)
    setInputPath(path)
  }, [config])

  async function handleSave() {
    const trimmed = inputPath.trim()
    if (!trimmed) {
      setMessage('Enter a folder location first.')
      setMessageIsError(true)
      return
    }

    setMessage(null)
    try {
      await setVaultPathMutation.mutateAsync(trimmed)
      setSavedPath(trimmed)
      setMessage('Notes folder saved.')
      setMessageIsError(false)
    } catch (e) {
      // Show the backend's actual reason (e.g. "isn't a folder that
      // exists on this machine") instead of a generic failure message --
      // that detail is exactly what tells the person how to fix it.
      setMessage(e instanceof ApiError ? e.message : 'Could not save that folder.')
      setMessageIsError(true)
    }
  }

  const isDirty = inputPath.trim() !== savedPath

  return (
    <Card>
      <CardHeader>
        <h2 className="font-serif text-lg text-ink">Notes folder</h2>
        <p className="text-sm text-ink-muted mt-1">
          The folder Praxis watches for your notes. Changing this takes effect right
          away.
        </p>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="py-4">
            <LoadingSpinner />
          </div>
        )}

        {error && <p className="text-sm text-danger-text">Failed to load current folder.</p>}

        {!isLoading && !error && (
          <div className="flex flex-col items-start gap-3 w-full">
            {!savedPath && (
              <p className="text-sm text-ink-muted">
                Not set yet. Open the folder in File Explorer, copy its location from the
                address bar, and paste it below.
              </p>
            )}
            <div className="flex items-center gap-2 w-full">
              <input
                type="text"
                value={inputPath}
                onChange={(e) => setInputPath(e.target.value)}
                placeholder="e.g. C:\Users\You\Documents\EnglishNotes"
                className="bg-cream-100 border border-border rounded-lg px-3 py-1.5 text-sm text-ink font-mono flex-1 min-w-0 focus:outline-none focus:ring-2 focus:ring-accent"
                disabled={setVaultPathMutation.isPending}
              />
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={handleSave}
                disabled={setVaultPathMutation.isPending || !isDirty}
              >
                {setVaultPathMutation.isPending ? 'Saving…' : 'Save'}
              </Button>
            </div>
            {message && (
              <p className={`text-sm ${messageIsError ? 'text-danger-text' : 'text-ink-muted'}`}>
                {message}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}