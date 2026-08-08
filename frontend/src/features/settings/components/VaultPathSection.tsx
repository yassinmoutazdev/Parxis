import { useEffect, useState } from 'react'
import { Card, CardHeader, CardContent } from '../../../shared/components/Card'
import { Button } from '../../../shared/components/Button'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { useConfig, useSetVaultPath } from '../hooks'

export function VaultPathSection() {
  const { data: config, isLoading, error } = useConfig()
  const setVaultPathMutation = useSetVaultPath()

  const [draft, setDraft] = useState('')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const value = config?.vault_path?.value
    if (typeof value === 'string') setDraft(value)
  }, [config])

  const currentPath = typeof config?.vault_path?.value === 'string' ? config.vault_path.value : ''
  const isDirty = draft.trim() !== '' && draft !== currentPath

  async function save() {
    setMessage(null)
    try {
      const result = await setVaultPathMutation.mutateAsync(draft.trim())
      setMessage(result.message)
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Could not update vault path')
    }
  }

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

        {error && <p className="text-sm text-red-400">Failed to load current folder.</p>}

        {!isLoading && !error && (
          <div className="flex items-center gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="/path/to/your/notes"
              className="flex-1 bg-cream-100 border border-border rounded-lg px-3 py-1.5 text-sm text-ink font-mono focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <Button
              size="sm"
              variant="secondary"
              onClick={save}
              disabled={!isDirty || setVaultPathMutation.isPending}
            >
              {setVaultPathMutation.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        )}

        {message && <p className="text-sm text-ink-muted mt-3">{message}</p>}
      </CardContent>
    </Card>
  )
}