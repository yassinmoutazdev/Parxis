// Vault path hook - runtime-configurable, restarts the watcher on change

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { setVaultPath } from '../../../api/client'

export function useSetVaultPath() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (vaultPath: string) => setVaultPath(vaultPath),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'config'] })
      queryClient.invalidateQueries({ queryKey: ['settings', 'env-info'] })
    },
  })
}