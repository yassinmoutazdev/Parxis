// Item browser hook - for searching and filtering learning items

import { useQuery } from '@tanstack/react-query'
import { getItems } from '../../../api/client'
import type { LearningItemBrowser } from '../../../api/types'

const ITEMS_QUERY_KEY = ['dashboard', 'items']

interface UseItemsOptions {
  search?: string
  itemType?: string
  tag?: string
  minMastery?: number
  maxMastery?: number
  limit?: number
  offset?: number
}

export function useItems(options: UseItemsOptions = {}) {
  const {
    search,
    itemType,
    tag,
    minMastery,
    maxMastery,
    limit = 50,
    offset = 0,
  } = options

  return useQuery({
    queryKey: [...ITEMS_QUERY_KEY, search, itemType, tag, minMastery, maxMastery, limit, offset],
    queryFn: async (): Promise<{ items: LearningItemBrowser[]; total: number }> => {
      return getItems(search, itemType, tag, minMastery, maxMastery, limit, offset)
    },
  })
}