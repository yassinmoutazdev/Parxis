import { useState, useCallback } from 'react'
import { startQuiz, submitQuizAnswers, getQuizSession } from '../../../api/client'
import type { QuizMode } from '../../../api/types'

export interface QuizQuestionState {
  id: number
  question_type: QuizMode
  prompt: string
  correct_answer: string | null
  options: string[] | null
}

export interface QuizSessionState {
  id: number
  quiz_scope: string
  quiz_mode: QuizMode
  started_at: string
  completed_at: string | null
  questions: QuizQuestionState[]
}

export interface GradedQuestion {
  id: number
  question_type: QuizMode
  prompt: string
  user_answer: string | null
  is_correct: boolean | null
  score: number | null
  feedback: string | null
  graded_by: string | null
}

export interface QuizResultState {
  id: number
  quiz_scope: string
  quiz_mode: QuizMode
  started_at: string
  completed_at: string | null
  total_questions: number
  correct_count: number
  incorrect_count: number
  questions: GradedQuestion[]
}

export function useStartQuiz() {
  const [session, setSession] = useState<QuizSessionState | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(async (mode: QuizMode, size: number = 10) => {
    setLoading(true)
    setError(null)
    try {
      const result = await startQuiz(mode, size)
      setSession(result)
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to start quiz'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setSession(null)
    setError(null)
  }, [])

  return {
    session,
    loading,
    error,
    start,
    reset,
  }
}

export function useSubmitAnswer() {
  const [result, setResult] = useState<QuizResultState | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = useCallback(async (
    sessionId: number,
    answers: Record<number, string>
  ) => {
    setLoading(true)
    setError(null)
    try {
      const gradedResult = await submitQuizAnswers(sessionId, answers)
      setResult(gradedResult)
      return gradedResult
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to submit answers'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchSession = useCallback(async (sessionId: number) => {
    setLoading(true)
    setError(null)
    try {
      const sessionResult = await getQuizSession(sessionId)
      setResult(sessionResult)
      return sessionResult
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to fetch session'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setResult(null)
    setError(null)
  }, [])

  return {
    result,
    loading,
    error,
    submit,
    fetchSession,
    reset,
  }
}