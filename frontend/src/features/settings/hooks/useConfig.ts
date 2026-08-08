// Settings config hooks - runtime-adjustable scheduler/mastery/retrieval params

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getConfig, setConfig } from '../../../api/client'
import type { ConfigMap } from '../../../api/types'

const CONFIG_QUERY_KEY = ['settings', 'config']

export function useConfig() {
  return useQuery({
    queryKey: CONFIG_QUERY_KEY,
    queryFn: (): Promise<ConfigMap> => getConfig(),
  })
}

export function useSetConfig() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      key,
      value,
    }: {
      key: string
      value: number | string | boolean | Record<string, number>
    }) => setConfig(key, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONFIG_QUERY_KEY })
    },
  })
}
