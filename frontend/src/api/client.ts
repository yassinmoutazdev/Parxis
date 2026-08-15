// API client - thin fetch wrapper

import type {
  Note,
  LearningItem,
  LearningItemBrowser,
  QuizSession,
  QuizQuestion,
  WritingPrompt,
  WritingSubmission,
  WritingEvaluation,
  WeeklyReport,
  DashboardOverview,
  CategoryMastery,
  TrendData,
  ConfigMap,
  BackupInfo,
  BackupRestoreResult,
  EnvInfo,
  VaultPathSetResult,
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

export async function getMasteryBreakdown(): Promise<{ categories: CategoryMastery[] }> {
  return request('/dashboard/mastery-breakdown')
}

export async function getTrends(rangeDays: number = 90): Promise<TrendData> {
  return request(`/dashboard/trends?range_days=${rangeDays}`)
}

export async function getItems(
  search?: string,
  itemType?: string,
  tag?: string,
  minMastery?: number,
  maxMastery?: number,
  limit: number = 50,
  offset: number = 0
): Promise<{ items: LearningItemBrowser[]; total: number }> {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (itemType) params.set('item_type', itemType)
  if (tag) params.set('tag', tag)
  if (minMastery !== undefined) params.set('min_mastery', minMastery.toString())
  if (maxMastery !== undefined) params.set('max_mastery', maxMastery.toString())
  params.set('limit', limit.toString())
  params.set('offset', offset.toString())
  return request(`/dashboard/items?${params.toString()}`)
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
  size: number
): Promise<QuizSession & { questions: QuizQuestion[] }> {
  return request('/quizzes', {
    method: 'POST',
    body: JSON.stringify({ size }),
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
export async function createMiniPrompt(): Promise<WritingPrompt> {
  return request('/writing/prompts/mini', {
    method: 'POST',
  })
}

export async function createWeeklyPrompt(): Promise<WritingPrompt> {
  return request('/writing/prompts/weekly', {
    method: 'POST',
  })
}

export async function getWritingPrompt(promptId: number): Promise<WritingPrompt> {
  return request(`/writing/prompts/${promptId}`)
}

export async function listWritingPrompts(
  promptType?: string,
  limit: number = 10
): Promise<{ prompts: WritingPrompt[] }> {
  const params = new URLSearchParams()
  if (promptType) params.set('prompt_type', promptType)
  params.set('limit', limit.toString())
  return request(`/writing/prompts?${params.toString()}`)
}

export async function submitWriting(
  promptId: number,
  text: string
): Promise<{ submission: WritingSubmission; evaluation: WritingEvaluation }> {
  return request('/writing/submissions', {
    method: 'POST',
    body: JSON.stringify({ prompt_id: promptId, text }),
  })
}

export async function retryWritingEvaluation(
  submissionId: number
): Promise<{ submission: WritingSubmission; evaluation: WritingEvaluation }> {
  return request(`/writing/submissions/${submissionId}/retry`, {
    method: 'POST',
  })
}

export async function getWritingSubmission(
  submissionId: number
): Promise<WritingSubmission> {
  return request(`/writing/submissions/${submissionId}`)
}

export async function getWritingEvaluation(
  evaluationId: number
): Promise<WritingEvaluation> {
  return request(`/writing/evaluations/${evaluationId}`)
}

// Reports
export async function listWeeklyReports(limit: number = 10): Promise<{ reports: WeeklyReport[] }> {
  return request(`/reports?limit=${limit}`)
}

export async function getWeeklyReport(id: number): Promise<WeeklyReport> {
  return request(`/reports/weekly/${id}`)
}

export async function startWeeklyReview(): Promise<{
  week_start: string
  week_end: string
  existing_report_id: number | null
}> {
  return request('/reports/weekly/start', {
    method: 'POST',
  })
}

export async function finalizeWeeklyReport(
  weekStart?: string,
  weekEnd?: string
): Promise<WeeklyReport> {
  return request('/reports/weekly/finalize', {
    method: 'POST',
    body: JSON.stringify({ week_start: weekStart, week_end: weekEnd }),
  })
}

export async function startWeeklyQuiz(): Promise<{
  session_id: number
  questions: Array<{ id: number; question_type: string; prompt: string }>
}> {
  return request('/reports/weekly/quiz', {
    method: 'POST',
  })
}

export async function createWeeklyWritingPrompt(): Promise<{
  id: number
  prompt_type: string
  topic: string
  used_at: string
}> {
  return request('/reports/weekly/writing-prompt', {
    method: 'POST',
  })
}

export async function submitWeeklyWriting(
  promptId: number,
  text: string
): Promise<{
  submission: WritingSubmission
  evaluation: WritingEvaluation
}> {
  return request('/reports/weekly/writing-submit', {
    method: 'POST',
    body: JSON.stringify({ prompt_id: promptId, text }),
  })
}

// Notes
export async function getNotes(): Promise<Note[]> {
  return request('/notes')
}

export async function saveNote(threadId: number, content: string): Promise<{
  id: number
  thread_id: number
  role: string
  content: string
  action_type: string
  action_ref_id: number | null
  created_at: string
}> {
  return request(`/chat/threads/${threadId}/notes`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

// Tags
export async function getTags(): Promise<Array<{ id: number; name: string }>> {
  return request('/tags')
}

// Settings
export async function getConfig(): Promise<ConfigMap> {
  const { config } = await request<{ config: ConfigMap }>('/settings/config')
  return config
}

export async function setConfig(
  key: string,
  value: number | string | boolean | Record<string, number>
): Promise<{ key: string; value: unknown; message: string }> {
  return request('/settings/config', {
    method: 'PUT',
    body: JSON.stringify({ key, value }),
  })
}

export async function getBackups(): Promise<BackupInfo[]> {
  const { backups } = await request<{ backups: BackupInfo[] }>('/settings/backups')
  return backups
}

export async function restoreBackup(name: string): Promise<BackupRestoreResult> {
  return request(`/settings/backups/${encodeURIComponent(name)}/restore`, {
    method: 'POST',
  })
}

export async function getEnvInfo(): Promise<EnvInfo> {
  return request('/settings/env-info')
}

export async function setVaultPath(vaultPath: string): Promise<VaultPathSetResult> {
  return request('/settings/vault-path', {
    method: 'PUT',
    body: JSON.stringify({ vault_path: vaultPath }),
  })
}

// Ollama API Key (Part F)
export interface OllamaKeyStatus {
  configured: boolean
}

export interface OllamaKeyMasked {
  masked: string | null
}

export interface OllamaKeySetResponse {
  masked: string
  message: string
}

export async function getOllamaKeyStatus(): Promise<OllamaKeyStatus> {
  return request('/settings/ollama-key-status')
}

export async function getOllamaKey(): Promise<OllamaKeyMasked> {
  return request('/settings/ollama-key')
}

export async function setOllamaKey(key: string): Promise<OllamaKeySetResponse> {
  return request('/settings/ollama-key', {
    method: 'PUT',
    body: JSON.stringify({ key }),
  })
}