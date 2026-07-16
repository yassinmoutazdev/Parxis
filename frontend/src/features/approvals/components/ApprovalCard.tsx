import { useState } from 'react'
import type { ApprovalQueueItem } from '../../../api/types'
import { useApproveItem, useRejectItem } from '../hooks'

interface ApprovalCardProps {
  item: ApprovalQueueItem
}

export function ApprovalCard({ item }: ApprovalCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState({
    extracted_text: item.extracted_text,
    explanation: item.explanation || '',
    example_sentence: item.example_sentence || '',
  })

  const approveMutation = useApproveItem()
  const rejectMutation = useRejectItem()

  const handleApprove = () => {
    if (isEditing) {
      approveMutation.mutate({
        id: item.id,
        editedPayload: editForm,
      })
    } else {
      approveMutation.mutate({ id: item.id })
    }
    setIsEditing(false)
  }

  const handleReject = () => {
    rejectMutation.mutate(item.id)
  }

  const isLoading = approveMutation.isPending || rejectMutation.isPending

  return (
    <div className="border rounded-lg p-4 mb-4 bg-white shadow-sm">
      {/* Duplicate warning banner */}
      {item.possible_duplicate_of && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-2 mb-3 text-sm text-yellow-800">
          ⚠️ Possible duplicate of learning item #{item.possible_duplicate_of}
        </div>
      )}

      {/* Item type badge */}
      <div className="mb-2">
        <span className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
          {item.item_type}
        </span>
      </div>

      {/* Extracted text */}
      <h3 className="font-medium text-lg mb-2">
        {item.extracted_text}
      </h3>

      {/* Explanation */}
      {item.explanation && (
        <div className="mb-2">
          <span className="text-sm text-gray-600">Explanation: </span>
          <span className="text-sm">{item.explanation}</span>
        </div>
      )}

      {/* Example sentence */}
      {item.example_sentence && (
        <div className="mb-2">
          <span className="text-sm text-gray-600">Example: </span>
          <span className="text-sm italic">"{item.example_sentence}"</span>
        </div>
      )}

      {/* Source excerpt */}
      <div className="mt-3 pt-3 border-t text-sm text-gray-500">
        <span className="block mb-1">Source excerpt:</span>
        <blockquote className="border-l-2 border-gray-300 pl-2 italic">
          {item.source_context}
        </blockquote>
      </div>

      {/* Edit form (expandable) */}
      {isEditing && (
        <div className="mt-4 p-3 bg-gray-50 rounded">
          <h4 className="font-medium mb-2">Edit Approval</h4>
          <div className="mb-2">
            <label className="block text-sm text-gray-600 mb-1">Text</label>
            <input
              type="text"
              className="w-full border rounded px-2 py-1"
              value={editForm.extracted_text}
              onChange={(e) => setEditForm({ ...editForm, extracted_text: e.target.value })}
            />
          </div>
          <div className="mb-2">
            <label className="block text-sm text-gray-600 mb-1">Explanation</label>
            <textarea
              className="w-full border rounded px-2 py-1"
              value={editForm.explanation}
              onChange={(e) => setEditForm({ ...editForm, explanation: e.target.value })}
            />
          </div>
          <div className="mb-2">
            <label className="block text-sm text-gray-600 mb-1">Example Sentence</label>
            <input
              type="text"
              className="w-full border rounded px-2 py-1"
              value={editForm.example_sentence}
              onChange={(e) => setEditForm({ ...editForm, example_sentence: e.target.value })}
            />
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-4 flex gap-2">
        {!isEditing ? (
          <>
            <button
              onClick={handleApprove}
              disabled={isLoading}
              className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => setIsEditing(true)}
              disabled={isLoading}
              className="bg-gray-200 text-gray-800 px-4 py-2 rounded hover:bg-gray-300 disabled:opacity-50"
            >
              Edit
            </button>
            <button
              onClick={handleReject}
              disabled={isLoading}
              className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 disabled:opacity-50"
            >
              Reject
            </button>
          </>
        ) : (
          <>
            <button
              onClick={handleApprove}
              disabled={isLoading}
              className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50"
            >
              Save & Approve
            </button>
            <button
              onClick={() => setIsEditing(false)}
              disabled={isLoading}
              className="bg-gray-200 text-gray-800 px-4 py-2 rounded hover:bg-gray-300 disabled:opacity-50"
            >
              Cancel
            </button>
          </>
        )}
      </div>

      {/* Error message */}
      {(approveMutation.error || rejectMutation.error) && (
        <div className="mt-2 text-red-600 text-sm">
          Error: {(approveMutation.error || rejectMutation.error)?.message}
        </div>
      )}
    </div>
  )
}