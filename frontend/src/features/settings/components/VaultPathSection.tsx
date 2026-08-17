import { useEffect, useState } from 'react'
import { Card, CardHeader, CardContent } from '../../../shared/components/Card'
import { Button } from '../../../shared/components/Button'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { useConfig, useSetVaultPath } from '../hooks'

export function VaultPathSection() {
  const { data: config, isLoading, error } = useConfig()
  const setVaultPathMutation = useSetVaultPath()

  const [currentPath, setCurrentPath] = useState('')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const value = config?.vault_path?.value
    if (typeof value === 'string') setCurrentPath(value)
  }, [config])

  async function browseAndSave() {
    setMessage(null)

    // Use File System Access API if available (Chrome/Edge on secure contexts)
    if ('showDirectoryPicker' in window) {
      try {
        // @ts-expect-error - showDirectoryPicker is not in standard TypeScript lib yet
        const dirHandle = await window.showDirectoryPicker()
        // The File System Access API returns a handle, not a path string.
        // We need to send a path string to the backend.
        // For now, we use the name as a hint; the backend will validate.
        // Note: Full path is not exposed by the browser for security.
        const pathString = dirHandle.name
        await setVaultPathMutation.mutateAsync(pathString)
        setCurrentPath(pathString)
        setMessage(`Folder selected: ${pathString}`)
      } catch (e) {
        if (e instanceof Error && e.name !== 'AbortError') {
          setMessage('Could not select folder')
        }
      }
    } else {
      // Fallback: use hidden file input with webkitdirectory
      const input = document.createElement('input')
      input.type = 'file'
      input.webkitdirectory = true
      input.style.display = 'none'
      input.onchange = async () => {
        if (input.files && input.files.length > 0) {
          // Get the directory path from the first file
          const path = input.files[0].webkitRelativePath
          const dirName = path.split('/')[0]
          try {
            await setVaultPathMutation.mutateAsync(dirName)
            setCurrentPath(dirName)
            setMessage(`Folder selected: ${dirName}`)
          } catch (e) {
            setMessage(e instanceof Error ? e.message : 'Could not update vault path')
          }
        }
      }
      document.body.appendChild(input)
      input.click()
      document.body.removeChild(input)
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

        {error && <p className="text-sm text-danger-text">Failed to load current folder.</p>}

        {!isLoading && !error && (
          <div className="flex flex-col items-start gap-3">
            <div className="flex items-center gap-2">
              <span className="bg-cream-100 border border-border rounded-lg px-3 py-1.5 text-sm text-ink font-mono flex-1 min-w-0">
                {currentPath || <span className="text-ink-muted">No folder selected</span>}
              </span>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={browseAndSave}
                disabled={setVaultPathMutation.isPending}
              >
                {setVaultPathMutation.isPending ? 'Saving…' : 'Choose Folder…'}
              </Button>
            </div>
            {message && <p className="text-sm text-ink-muted">{message}</p>}
          </div>
        )}
      </CardContent>
    </Card>
  )
}