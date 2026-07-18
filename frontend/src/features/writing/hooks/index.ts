import { useState, useCallback } from 'react'
import {
  createMiniPrompt,
  createWeeklyPrompt,
  submitWriting,
  retryWritingEvaluation,
} from '../../../api/client'
import type { WritingPrompt, WritingSubmission, WritingEvaluation } from '../../../api/types'

export interface MiniTaskState {
  prompt: WritingPrompt | null
  submission: WritingSubmission | null
  evaluation: WritingEvaluation | null
}

export interface WeeklyAssessmentState {
  prompt: WritingPrompt | null
  submission: WritingSubmission | null
  evaluation: WritingEvaluation | null
}

export function useMiniTask() {
  const [prompt, setPrompt] = useState<WritingPrompt | null>(null)
  const [submission, setSubmission] = useState<WritingSubmission | null>(null)
  const [evaluation, setEvaluation] = useState<WritingEvaluation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startMiniTask = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const newPrompt = await createMiniPrompt()
      setPrompt(newPrompt)
      return newPrompt
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to start mini task'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const submitMiniTask = useCallback(async (promptId: number, text: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await submitWriting(promptId, text)
      setSubmission(result.submission)
      setEvaluation(result.evaluation)
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to submit mini task'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const retryEvaluation = useCallback(async (submissionId: number) => {
    setLoading(true)
    setError(null)
    try {
      const result = await retryWritingEvaluation(submissionId)
      setSubmission(result.submission)
      setEvaluation(result.evaluation)
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to retry evaluation'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setPrompt(null)
    setSubmission(null)
    setEvaluation(null)
    setError(null)
  }, [])

  return {
    prompt,
    submission,
    evaluation,
    loading,
    error,
    startMiniTask,
    submitMiniTask,
    retryEvaluation,
    reset,
  }
}

export function useWeeklyAssessment() {
  const [prompt, setPrompt] = useState<WritingPrompt | null>(null)
  const [submission, setSubmission] = useState<WritingSubmission | null>(null)
  const [evaluation, setEvaluation] = useState<WritingEvaluation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startWeeklyAssessment = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const newPrompt = await createWeeklyPrompt()
      setPrompt(newPrompt)
      return newPrompt
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to start weekly assessment'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const submitWeeklyAssessment = useCallback(async (promptId: number, text: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await submitWriting(promptId, text)
      setSubmission(result.submission)
      setEvaluation(result.evaluation)
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to submit weekly assessment'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const retryEvaluation = useCallback(async (submissionId: number) => {
    setLoading(true)
    setError(null)
    try {
      const result = await retryWritingEvaluation(submissionId)
      setSubmission(result.submission)
      setEvaluation(result.evaluation)
      return result
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to retry evaluation'
      setError(message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setPrompt(null)
    setSubmission(null)
    setEvaluation(null)
    setError(null)
  }, [])

  return {
    prompt,
    submission,
    evaluation,
    loading,
    error,
    startWeeklyAssessment,
    submitWeeklyAssessment,
    retryEvaluation,
    reset,
  }
}