import { useState, useCallback } from 'react'
import {
  startWeeklyReview,
  listWeeklyReports,
  finalizeWeeklyReport,
  getWeeklyReport,
  startWeeklyQuiz,
  createWeeklyWritingPrompt,
  submitWeeklyWriting,
} from '../../../api/client'
import type { WeeklyReport } from '../../../api/types'

export interface WeeklyReviewState {
  weekStart: string | null
  weekEnd: string | null
  existingReportId: number | null
}

export interface WeeklyQuizState {
  sessionId: number | null
  questions: Array<{
    id: number
    question_type: string
    prompt: string
  }>
}

export interface WeeklyWritingState {
  promptId: number | null
  promptTopic: string | null
  submissionId: number | null
  evaluation: {
    id: number
    grammar_score: number | null
    naturalness_score: number | null
    vocabulary_score: number | null
    coherence_score: number | null
    overall_score: number | null
  } | null
}

export function useStartWeeklyReview() {
  const [reviewState, setReviewState] = useState<WeeklyReviewState>({
    weekStart: null,
    weekEnd: null,
    existingReportId: null,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await startWeeklyReview()
      setReviewState({
        weekStart: result.week_start,
        weekEnd: result.week_end,
        existingReportId: result.existing_report_id,
      })
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to start weekly review'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setReviewState({ weekStart: null, weekEnd: null, existingReportId: null })
    setError(null)
  }, [])

  return {
    reviewState,
    loading,
    error,
    start,
    reset,
  }
}

export function useWeeklyQuiz() {
  const [quizState, setQuizState] = useState<WeeklyQuizState>({
    sessionId: null,
    questions: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startQuiz = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await startWeeklyQuiz()
      setQuizState({
        sessionId: result.session_id,
        questions: result.questions,
      })
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to start weekly quiz'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setQuizState({ sessionId: null, questions: [] })
    setError(null)
  }, [])

  return {
    quizState,
    loading,
    error,
    startQuiz,
    reset,
  }
}

export function useWeeklyWriting() {
  const [writingState, setWritingState] = useState<WeeklyWritingState>({
    promptId: null,
    promptTopic: null,
    submissionId: null,
    evaluation: null,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createPrompt = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await createWeeklyWritingPrompt()
      setWritingState({
        promptId: result.id,
        promptTopic: result.topic,
        submissionId: null,
        evaluation: null,
      })
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to create writing prompt'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const submitWriting = useCallback(async (promptId: number, text: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await submitWeeklyWriting(promptId, text)
      setWritingState((prev) => ({
        ...prev,
        submissionId: result.submission.id,
        evaluation: result.evaluation,
      }))
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to submit writing'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const finalizeReport = useCallback(async (weekStart?: string, weekEnd?: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await finalizeWeeklyReport(weekStart, weekEnd)
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to finalize report'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setWritingState({
      promptId: null,
      promptTopic: null,
      submissionId: null,
      evaluation: null,
    })
    setError(null)
  }, [])

  return {
    writingState,
    loading,
    error,
    createPrompt,
    submitWriting,
    finalizeReport,
    reset,
  }
}

export function useWeeklyReports() {
  const [reports, setReports] = useState<WeeklyReport[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchReports = useCallback(async (limit: number = 10) => {
    setLoading(true)
    setError(null)
    try {
      const result = await listWeeklyReports(limit)
      setReports(result.reports)
      return result.reports
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to fetch reports'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchReport = useCallback(async (reportId: number) => {
    setLoading(true)
    setError(null)
    try {
      const result = await getWeeklyReport(reportId)
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to fetch report'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    reports,
    loading,
    error,
    fetchReports,
    fetchReport,
  }
}