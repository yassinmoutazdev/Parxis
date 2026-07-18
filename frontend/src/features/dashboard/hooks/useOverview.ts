// Dashboard overview hook - independently fetched

import { useQuery } from '@tanstack/react-query'
import { getDashboardOverview } from '../../../api/client'
import type { DashboardOverview } from '../../../api/types'

const OVERVIEW_QUERY_KEY = ['dashboard', 'overview']

export function useOverview() {
  return useQuery({
    queryKey: OVERVIEW_QUERY_KEY,
    queryFn: (): Promise<DashboardOverview> => getDashboardOverview(),
    refetchInterval: 60000, // Refresh every minute
  })
}