import { useState } from 'react'
import { Card, CardHeader, CardContent } from '../../../shared/components/Card'
import { Button } from '../../../shared/components/Button'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { EmptyState } from '../../../shared/components/EmptyState'
import { useBackups, useRestoreBackup } from '../hooks'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

export function BackupsSection() {
  const { data: backups, isLoading, error } = useBackups()
  const restoreMutation = useRestoreBackup()
  const [pendingRestore, setPendingRestore] = useState<string | null>(null)
  const [resultMessage, setResultMessage] = useState<string | null>(null)

  async function confirmRestore(name: string) {
    setResultMessage(null)
    try {
      const result = await restoreMutation.mutateAsync(name)
      setResultMessage(result.message)
    } catch (e) {
      setResultMessage(e instanceof Error ? e.message : 'Restore failed')
    } finally {
      setPendingRestore(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="font-serif text-lg text-ink">Backups</h2>
        <p className="text-sm text-ink-muted mt-1">
          Restore replaces the current database. A safety backup of the current state is
          taken first, and you'll be asked to confirm before anything happens.
        </p>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="py-8">
            <LoadingSpinner />
          </div>
        )}

        {error && <p className="text-sm text-danger-text">Failed to load backups.</p>}

        {!isLoading && !error && backups && backups.length === 0 && (
          <EmptyState
            title="No backups yet"
            description="Backups are created automatically on a schedule and will show up here."
          />
        )}

        {!isLoading && !error && backups && backups.length > 0 && (
          <ul className="divide-y divide-border">
            {backups.map((backup) => (
              <li
                key={backup.name}
                className="py-3 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <p className="text-sm text-ink truncate">{backup.name}</p>
                  <p className="text-xs text-ink-muted">
                    {formatDate(backup.created_at)} &middot; {formatSize(backup.size_bytes)}
                  </p>
                </div>

                {pendingRestore === backup.name ? (
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-ink-muted">Replace current database?</span>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => confirmRestore(backup.name)}
                      disabled={restoreMutation.isPending}
                    >
                      {restoreMutation.isPending ? 'Restoring…' : 'Confirm'}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setPendingRestore(null)}
                      disabled={restoreMutation.isPending}
                    >
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setPendingRestore(backup.name)}
                    className="shrink-0"
                  >
                    Restore
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}

        {resultMessage && (
          <p className="text-sm text-ink-muted mt-3 pt-3 border-t border-border">
            {resultMessage}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
