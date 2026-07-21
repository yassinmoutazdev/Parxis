// TypeScript types mirroring backend Pydantic/SQLModel schemas

// Enums
export type NoteStatus = 'NEW' | 'PARSING' | 'PENDING_APPROVAL' | 'PROCESSED' | 'PARSE_FAILED'

export type ApprovalSourceType = 'NOTE_PARSE' | 'WRITING_FEEDBACK' | 'QUIZ_FEEDBACK'
export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'EDITED_APPROVED' | 'REJECTED'

export type ItemType = 'COLLOCATION' | 'IDIOM' | 'PHRASAL_VERB' | 'GRAMMAR_NOTE' | 'PERSONAL_EXAMPLE'

export type QuizScope = 'AD_HOC' | 'WEEKLY_REVIEW'
export type QuizMode = 'RECALL' | 'FILL_BLANK' | 'MULTIPLE_CHOICE' | 'ERROR_CORRECTION' | 'REWRITE_NATURALLY' | 'CONVERSATION' | 'MINI_ESSAY' | 'RANDOM'
export type GradedBy = 'DETERMINISTIC' | 'LLM'

export type WritingPromptType = 'MINI' | 'WEEKLY'
export type WritingSubmissionType = 'MINI' | 'WEEKLY'

// Source & Lesson
export interface Source {
  id: number
  title: string
  author: string | null
  source_type: 'BOOK' | 'OTHER'
  created_at: string
}

export interface Lesson {
  id: number
  source_id: number | null
  title: string
  order_index: number | null
  created_at: string
}

// Note
export interface Note {
  id: number
  vault_path: string
  content_hash: string
  lesson_id: number | null
  status: NoteStatus
  changed_since_processed: boolean
  created_at: string
  processed_at: string | null
}

// Approval Queue
export interface ApprovalQueueItem {
  id: number
  source_type: ApprovalSourceType
  source_id: number
  item_type: string
  extracted_text: string
  explanation: string | null
  example_sentence: string | null
  source_context: string
  possible_duplicate_of: number | null
  status: ApprovalStatus
  reviewed_payload: Record<string, unknown> | null
  created_at: string
  reviewed_at: string | null
}

// Learning Item
export interface LearningItem {
  id: number
  item_type: ItemType
  text: string
  definition: string | null
  example_sentence: string | null
  source_note_id: number | null
  source_approval_id: number
  mastery_score: number
  review_count: number
  correct_count: number
  incorrect_count: number
  last_reviewed_at: string | null
  next_review_due: string | null
  ease_factor: number
  interval_days: number
  suspended: boolean
  created_at: string
}

// Learning Correction
export interface LearningCorrection {
  id: number
  wrong_form: string
  correct_form: string
  explanation: string | null
  example_sentence: string | null
  source_note_id: number | null
  source_writing_evaluation_id: number | null
  source_approval_id: number
  created_at: string
}

// Quiz Session
export interface QuizSession {
  id: number
  quiz_scope: QuizScope
  quiz_mode: QuizMode
  started_at: string
  completed_at: string | null
  week_id: number | null
}

export interface QuizQuestion {
  id: number
  quiz_session_id: number
  learning_item_id: number | null
  question_type: QuizMode
  prompt: string
  correct_answer: string | null
  distractors: string[] | null
  user_answer: string | null
  is_correct: boolean | null
  score: number | null
  feedback: string | null
  graded_by: GradedBy | null
  evaluator_provider: string | null
  evaluator_model: string | null
  prompt_version: string | null
  rubric_version: string | null
  created_at: string
}

// Writing
export interface WritingPrompt {
  id: number
  prompt_type: WritingPromptType
  topic: string
  used_at: string
  week_id: number | null
}

export interface WritingSubmission {
  id: number
  prompt_id: number
  submission_type: WritingSubmissionType
  submitted_text: string
  word_count: number
  created_at: string
}

export interface WritingEvaluation {
  id: number
  submission_id: number
  grammar_score: number | null
  naturalness_score: number | null
  vocabulary_score: number | null
  coherence_score: number | null
  overall_score: number | null
  feedback_json: Record<string, unknown> | null
  suggested_items_json: unknown[] | null
  evaluator_provider: string | null
  evaluator_model: string | null
  prompt_version: string | null
  rubric_version: string | null
  created_at: string
}

// Weekly Report
export interface WeeklyReport {
  id: number
  week_start: string
  week_end: string
  items_studied_count: number
  quiz_summary_json: Record<string, unknown> | null
  mini_writing_summary_json: Record<string, unknown> | null
  weekly_writing_evaluation_id: number | null
  mastery_snapshot_json: Record<string, unknown> | null
  narrative_report: string | null
  created_at: string
}

// Dashboard Types
export interface DashboardOverview {
  proficiency: number | null
  category_mastery_avg: number | null
  writing_performance_avg: number | null
  pending_approvals_count: number
  week_snapshot: {
    items_studied: number
    quiz_sessions: number
    writing_submissions: number
  }
  health: {
    status: string
    vault_watcher: string
    vault_path: string | null
  }
}

export interface CategoryMastery {
  category: string
  mastery_score: number
  item_count: number
  total_reviews: number
}

export interface TrendPoint {
  week_start: string
  accuracy: number | null
  total_questions: number
}

export interface WritingScorePoint {
  week_start: string
  grammar: number | null
  naturalness: number | null
  vocabulary: number | null
  coherence: number | null
  overall: number | null
}

export interface ItemsLearnedPoint {
  week_start: string
  count: number
}

export interface TrendData {
  quiz_accuracy: TrendPoint[]
  writing_scores: WritingScorePoint[]
  items_learned: ItemsLearnedPoint[]
  range_days: number
}

export interface LearningItemBrowser extends LearningItem {
  decayed_mastery_score: number
  tags: string[]
}