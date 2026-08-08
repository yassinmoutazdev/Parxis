// Settings backups hooks - list + manual, confirmed restore (ARCHITECTURE Section 13.5)

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getBackups, restoreBackup } from '../../../api/client'
import type { BackupInfo } from '../../../api/types'

const BACKUPS_QUERY_KEY = ['settings', 'backups']

export function useBackups() {
  return useQuery({
    queryKey: BACKUPS_QUERY_KEY,
    queryFn: (): Promise<BackupInfo[]> => getBackups(),
  })
}

export function useRestoreBackup() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (name: string) => restoreBackup(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BACKUPS_QUERY_KEY })
    },
  })
}
