import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { usePendingApprovals, useApproveItem, useRejectItem } from '../usePendingApprovals'
import * as apiClient from '../../../../api/client'

// Mock the API client
vi.mock('../../../../api/client', () => ({
  getPendingApprovals: vi.fn(),
  approveItem: vi.fn(),
  rejectItem: vi.fn(),
  getPendingCount: vi.fn(),
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  })

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('usePendingApprovals', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch pending approvals', async () => {
    const mockApprovals = [
      {
        id: 1,
        source_type: 'NOTE_PARSE',
        source_id: 1,
        item_type: 'COLLOCATION',
        extracted_text: 'test collocation',
        explanation: 'test explanation',
        example_sentence: 'test example',
        source_context: 'source context',
        possible_duplicate_of: null,
        status: 'PENDING',
        reviewed_payload: null,
        created_at: '2024-01-01T00:00:00Z',
        reviewed_at: null,
      },
    ]

    ;(apiClient.getPendingApprovals as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockApprovals
    )

    const { result } = renderHook(() => usePendingApprovals(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockApprovals)
    expect(apiClient.getPendingApprovals).toHaveBeenCalledTimes(1)
  })

  it('should handle errors when fetching approvals', async () => {
    const error = new Error('Failed to fetch')
    ;(apiClient.getPendingApprovals as ReturnType<typeof vi.fn>).mockRejectedValue(error)

    const { result } = renderHook(() => usePendingApprovals(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.error).toEqual(error)
  })
})

describe('useApproveItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should approve an item', async () => {
    ;(apiClient.approveItem as ReturnType<typeof vi.fn>).mockResolvedValue({
      learning_item_id: 1,
      message: 'Item approved successfully',
    })

    const { result } = renderHook(() => useApproveItem(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({ id: 1 })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.approveItem).toHaveBeenCalledWith(1, undefined)
  })

  it('should approve an item with edited payload', async () => {
    const editedPayload = {
      extracted_text: 'edited text',
      explanation: 'edited explanation',
    }

    ;(apiClient.approveItem as ReturnType<typeof vi.fn>).mockResolvedValue({
      learning_item_id: 1,
      message: 'Item approved with edits',
    })

    const { result } = renderHook(() => useApproveItem(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({ id: 1, editedPayload })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.approveItem).toHaveBeenCalledWith(1, editedPayload)
  })
})

describe('useRejectItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should reject an item', async () => {
    ;(apiClient.rejectItem as ReturnType<typeof vi.fn>).mockResolvedValue({
      learning_item_id: null,
      message: 'Item rejected',
    })

    const { result } = renderHook(() => useRejectItem(), {
      wrapper: createWrapper(),
    })

    result.current.mutate(1)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.rejectItem).toHaveBeenCalledWith(1)
  })
})