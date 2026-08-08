// Settings env-info hook - read-only infra config (.env / pydantic-settings)

import { useQuery } from '@tanstack/react-query'
import { getEnvInfo } from '../../../api/client'
import type { EnvInfo } from '../../../api/types'

const ENV_INFO_QUERY_KEY = ['settings', 'env-info']

export function useEnvInfo() {
  return useQuery({
    queryKey: ENV_INFO_QUERY_KEY,
    queryFn: (): Promise<EnvInfo> => getEnvInfo(),
  })
}
