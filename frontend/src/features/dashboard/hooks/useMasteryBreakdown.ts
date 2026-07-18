// Dashboard mastery breakdown hook - independently fetched

import { useQuery } from '@tanstack/react-query'
import { getMasteryBreakdown } from '../../../api/client'
import type { CategoryMastery } from '../../../api/types'

const MASTERY_QUERY_KEY = ['dashboard', 'mastery-breakdown']

export function useMasteryBreakdown() {
  return useQuery({
    queryKey: MASTERY_QUERY_KEY,
    queryFn: async (): Promise<CategoryMastery[]> => {
      const response = await getMasteryBreakdown()
      return response.categories
    },
    refetchInterval: 60000, // Refresh every minute
  })
}