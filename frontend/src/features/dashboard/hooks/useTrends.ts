// Dashboard trends hook - independently fetched

import { useQuery } from '@tanstack/react-query'
import { getTrends } from '../../../api/client'
import type { TrendData } from '../../../api/types'

const TRENDS_QUERY_KEY = ['dashboard', 'trends']

export function useTrends(rangeDays: number = 90) {
  return useQuery({
    queryKey: [...TRENDS_QUERY_KEY, rangeDays],
    queryFn: (): Promise<TrendData> => getTrends(rangeDays),
    refetchInterval: 60000, // Refresh every minute
  })
}