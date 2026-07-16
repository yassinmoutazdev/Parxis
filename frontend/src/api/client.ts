// API client - thin fetch wrapper

import type {
  Note,
  ApprovalQueueItem,
  LearningItem,
  QuizSession,
  QuizQuestion,
  WritingPrompt,
  WritingSubmission,
  WritingEvaluation,
  WeeklyReport,
  DashboardOverview,
  CategoryMastery,
  TrendPoint,
} from './types'

const API_BASE = '/api'

// Normalize error shape
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    let message = `HTTP ${response.status}`
    let code: string | undefined

    try {
      const body = await response.json()
      message = body.detail || body.message || message
      code = body.code
    } catch {
      // Response wasn't JSON
    }

    throw new ApiError(message, response.status, code)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

// Health
export async function getHealth(): Promise<{
  status: string
  database: string
  integrity_check?: string
}> {
  return request('/health')
}

// Dashboard
export async function getDashboardOverview(): Promise<DashboardOverview> {
  return request('/dashboard/overview')
}

export async function getMasteryBreakdown(): Promise<CategoryMastery[]> {
  return request('/dashboard/mastery-breakdown')
}

export async function getTrends(range: string = '90d'): Promise<TrendPoint[]> {
  return request(`/dashboard/trends?range=${range}`)
}

// Approvals
export async function getPendingApprovals(): Promise<ApprovalQueueItem[]> {
  return request('/approvals?status=PENDING')
}

export async function getApprovalItem(id: number): Promise<ApprovalQueueItem> {
  return request(`/approvals?id=${id}`)
}

export async function approveItem(
  id: number,
  editedPayload?: Record<string, unknown>
): Promise<{ learning_item_id: number | null; message: string }> {
  if (editedPayload && Object.keys(editedPayload).length > 0) {
    return request(`/approvals/${id}/approve-edited`, {
      method: 'POST',
      body: JSON.stringify(editedPayload),
    })
  }
  return request(`/approvals/${id}/approve`, {
    method: 'POST',
  })
}

export async function rejectItem(id: number): Promise<{ learning_item_id: number | null; message: string }> {
  return request(`/approvals/${id}/reject`, {
    method: 'POST',
  })
}

export async function getPendingCount(): Promise<{ count: number }> {
  return request('/approvals/pending-count')
}

// Learning Items
export async function getLearningItems(): Promise<LearningItem[]> {
  return request('/items')
}

export async function getLearningItem(id: number): Promise<LearningItem> {
  return request(`/items/${id}`)
}

// Quizzes
export async function startQuiz(
  mode: string,
  size: number
): Promise<QuizSession & { questions: QuizQuestion[] }> {
  return request('/quizzes', {
    method: 'POST',
    body: JSON.stringify({ mode, size }),
  })
}

export async function submitQuizAnswers(
  sessionId: number,
  answers: Record<number, string>  // question_id -> user_answer
): Promise<QuizSession & { questions: QuizQuestion[]; correct_count: number; incorrect_count: number; total_questions: number }> {
  return request(`/quizzes/${sessionId}/answers`, {
    method: 'POST',
    body: JSON.stringify({ answers }),
  })
}

export async function getQuizSession(
  sessionId: number
): Promise<QuizSession & { questions: QuizQuestion[]; correct_count: number; incorrect_count: number; total_questions: number }> {
  return request(`/quizzes/${sessionId}`)
}

// Writing
export async function getWritingPrompt(
  type: string
): Promise<WritingPrompt> {
  return request(`/writing/prompt`, {
    method: 'POST',
    body: JSON.stringify({ prompt_type: type }),
  })
}

export async function submitWriting(
  promptId: number,
  text: string,
  type: string
): Promise<WritingSubmission & { evaluation: WritingEvaluation }> {
  return request('/writing/submissions', {
    method: 'POST',
    body: JSON.stringify({ prompt_id: promptId, text, submission_type: type }),
  })
}

// Reports
export async function getWeeklyReports(): Promise<WeeklyReport[]> {
  return request('/reports/weekly')
}

export async function getWeeklyReport(id: number): Promise<WeeklyReport> {
  return request(`/reports/weekly/${id}`)
}

export async function startWeeklyReview(): Promise<{
  week_start: string
  week_end: string
}> {
  return request('/reports/weekly/start', {
    method: 'POST',
  })
}

// Notes
export async function getNotes(): Promise<Note[]> {
  return request('/notes')
}

// Tags
export async function getTags(): Promise<Array<{ id: number; name: string }>> {
  return request('/tags')
}