import { Card, CardHeader, CardContent } from '../../../shared/components/Card'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { useEnvInfo } from '../hooks'

export function EnvInfoSection() {
  const { data: envInfo, isLoading, error } = useEnvInfo()

  return (
    <Card>
      <CardHeader>
        <h2 className="font-serif text-lg text-ink">Environment</h2>
        <p className="text-sm text-ink-muted mt-1">
          Read-only. These come from your .env file - change and restart the app if you
          need to update them.
        </p>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="py-8">
            <LoadingSpinner />
          </div>
        )}

        {error && <p className="text-sm text-red-400">Failed to load environment info.</p>}

        {envInfo && (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
            <div>
              <dt className="text-xs text-ink-muted">Model provider host</dt>
              <dd className="text-sm text-ink font-mono break-all">{envInfo.ollama_host}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Model</dt>
              <dd className="text-sm text-ink font-mono break-all">{envInfo.ollama_model}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">API key</dt>
              <dd className="text-sm text-ink">
                {envInfo.ollama_api_key_set ? 'Set' : 'Not set (local Ollama)'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Vault path</dt>
              <dd className="text-sm text-ink font-mono break-all">{envInfo.vault_path}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Database path</dt>
              <dd className="text-sm text-ink font-mono break-all">{envInfo.db_path}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Backup directory</dt>
              <dd className="text-sm text-ink font-mono break-all">{envInfo.backup_dir}</dd>
            </div>
          </dl>
        )}
      </CardContent>
    </Card>
  )
}
