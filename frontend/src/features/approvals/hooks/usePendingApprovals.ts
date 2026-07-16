// TanStack Query hooks for approvals

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getPendingApprovals, getPendingCount, approveItem, rejectItem } from '../../../api/client'
import type { ApprovalQueueItem } from '../../../api/types'

const APPROVALS_QUERY_KEY = ['approvals', 'pending']
const COUNT_QUERY_KEY = ['approvals', 'count']
const ITEMS_QUERY_KEY = ['items']
const DASHBOARD_QUERY_KEY = ['dashboard']

export function usePendingApprovals() {
  return useQuery({
    queryKey: APPROVALS_QUERY_KEY,
    queryFn: getPendingApprovals,
    refetchInterval: 30000, // Poll every 30 seconds per ADR-08
  })
}

export function usePendingCount() {
  return useQuery({
    queryKey: COUNT_QUERY_KEY,
    queryFn: getPendingCount,
    refetchInterval: 30000,
  })
}

export function useApproveItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, editedPayload }: { id: number; editedPayload?: Record<string, unknown> }) =>
      approveItem(id, editedPayload),
    onSuccess: () => {
      // Invalidate queries per ARCHITECTURE Section 6.2
      queryClient.invalidateQueries({ queryKey: APPROVALS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: COUNT_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ITEMS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY })
    },
  })
}

export function useRejectItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: rejectItem,
    onSuccess: () => {
      // Invalidate queries per ARCHITECTURE Section 6.2
      queryClient.invalidateQueries({ queryKey: APPROVALS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: COUNT_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY })
    },
  })
}

export type { ApprovalQueueItem }