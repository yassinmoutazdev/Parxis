import { usePendingApprovals, useApproveItem, useRejectItem, ApprovalQueueItem } from './hooks'
import { ApprovalCard } from './components/ApprovalCard'

interface ApprovalGroup {
  sourceType: string
  sourceId: number
  items: ApprovalQueueItem[]
}

export default function ApprovalsPage() {
  const { data: approvals, isLoading, error } = usePendingApprovals()
  const approveMutation = useApproveItem()
  const rejectMutation = useRejectItem()

  // Group pending items by source_type + source_id (oldest-first)
  const groupedApprovals = (() => {
    if (!approvals) return []

    const groups = new Map<string, ApprovalGroup>()

    for (const item of approvals) {
      const key = `${item.source_type}-${item.source_id}`
      if (!groups.has(key)) {
        groups.set(key, {
          sourceType: item.source_type,
          sourceId: item.source_id,
          items: [],
        })
      }
      groups.get(key)!.items.push(item)
    }

    // Sort groups by oldest item's created_at (oldest-first)
    const sortedGroups = Array.from(groups.values()).sort((a, b) => {
      const aOldest = Math.min(...a.items.map((i) => new Date(i.created_at).getTime()))
      const bOldest = Math.min(...b.items.map((i) => new Date(i.created_at).getTime()))
      return aOldest - bOldest
    })

    // Sort items within each group by created_at (oldest-first)
    for (const group of sortedGroups) {
      group.items.sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      )
    }

    return sortedGroups
  })()

  const handleBatchApprove = (group: ApprovalGroup) => {
    for (const item of group.items) {
      approveMutation.mutate({ id: item.id })
    }
  }

  const handleBatchReject = (group: ApprovalGroup) => {
    for (const item of group.items) {
      rejectMutation.mutate(item.id)
    }
  }

  if (isLoading) {
    return (
      <div className="px-4 py-6 sm:px-0">
        <h1 className="text-2xl font-bold mb-6">Pending Approvals</h1>
        <div className="flex items-center justify-center h-64">
          <p className="text-ink-muted">Loading...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 py-6 sm:px-0">
        <h1 className="text-2xl font-bold mb-6">Pending Approvals</h1>
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
          Error loading approvals: {(error as Error).message}
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 py-6 sm:px-0">
      <h1 className="text-2xl font-bold mb-6">Pending Approvals</h1>

      {groupedApprovals.length === 0 ? (
        <div className="border-4 border-dashed border-border-strong rounded-lg h-64 flex items-center justify-center">
          <p className="text-ink-muted text-lg">No pending approvals</p>
        </div>
      ) : (
        <div className="space-y-8">
          {groupedApprovals.map((group) => (
            <div key={`${group.sourceType}-${group.sourceId}`} className="border rounded-lg p-4">
              {/* Group header */}
              <div className="flex items-center justify-between mb-4 pb-2 border-b">
                <div>
                  <span className="text-sm text-ink-muted">
                    Source: {group.sourceType} #{group.sourceId}
                  </span>
                  <span className="ml-2 text-sm text-ink-faint">
                    ({group.items.length} item{group.items.length !== 1 ? 's' : ''})
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleBatchApprove(group)}
                    disabled={approveMutation.isPending}
                    className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700 disabled:opacity-50"
                  >
                    Approve All
                  </button>
                  <button
                    onClick={() => handleBatchReject(group)}
                    disabled={rejectMutation.isPending}
                    className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700 disabled:opacity-50"
                  >
                    Reject All
                  </button>
                </div>
              </div>

              {/* Items in group */}
              <div className="space-y-4">
                {group.items.map((item) => (
                  <ApprovalCard key={item.id} item={item} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}