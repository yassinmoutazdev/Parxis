// TypeScript types mirroring backend Pydantic/SQLModel schemas

// Enums
export type NoteStatus = 'NEW' | 'PARSING' | 'PROCESSED' | 'PARSE_FAILED'
export type NoteSource = 'vault' | 'chat'

export type ItemType = 'COLLOCATION' | 'IDIOM' | 'PHRASAL_VERB' | 'GRAMMAR_NOTE' | 'PERSONAL_EXAMPLE'

export type QuizScope = 'AD_HOC' | 'WEEKLY_REVIEW'
export type QuizMode = 'MULTIPLE_CHOICE'
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
  source: NoteSource
  vault_path: string | null
  content: string | null
  content_hash: string
  lesson_id: number | null
  status: NoteStatus
  changed_since_processed: boolean
  created_at: string
  processed_at: string | null
}

// Learning Item
export interface LearningItem {
  id: number
  item_type: ItemType
  text: string
  definition: string | null
  example_sentence: string | null
  source_note_id: number | null
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
  options: string[] | null
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
  // CEFR band (Part B - weekly evaluations only)
  cefr_band: CefrBand
  cefr_justification: string | null
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
  // CEFR band from weekly writing evaluation (Part B)
  weekly_cefr_band: CefrBand
  weekly_cefr_justification: string | null
  mastery_snapshot_json: Record<string, unknown> | null
  narrative_report: string | null
  created_at: string
}

// Dashboard Types
export type CefrBand = 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2' | null
export type CefrTrend = 'up' | 'down' | 'steady'

export interface ProficiencyBand {
  band: CefrBand
  trend: CefrTrend
  last_eval_week_start: string | null
}

export interface DashboardOverview {
  proficiency: ProficiencyBand | null
  mastery_index: number | null
  category_mastery_avg: number | null
  writing_performance_avg: number | null
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

// Chat Types
export type ChatRole = 'USER' | 'ASSISTANT' | 'SYSTEM'
export type ChatActionType = 'NONE' | 'QUIZ' | 'WRITING'

export interface ChatThread {
  id: number
  title: string | null
  last_message_preview: string | null
  updated_at: string
}

export interface ChatMessage {
  id: number
  thread_id: number
  role: ChatRole
  content: string
  action_type: ChatActionType
  action_ref_id: number | null
  created_at: string
  attachments?: ChatAttachment[] | null
}

export type ChatAttachmentKind = 'text' | 'image'

export interface ChatAttachment {
  id: number
  filename: string
  kind: ChatAttachmentKind
  mime_type: string
  context_truncated: boolean
}

export interface ChatThreadDetail extends ChatThread {
  created_at: string
  messages: ChatMessage[]
}

// Settings Types
export interface ConfigFieldValue {
  value: number | string | boolean | Record<string, number>
  type: 'float' | 'int' | 'bool' | 'json'
  min: number | null
  max: number | null
  default: number | string | boolean | Record<string, number>
  description: string
}

export type ConfigMap = Record<string, ConfigFieldValue>

export interface BackupInfo {
  name: string
  path: string
  created_at: string
  size_bytes: number
}

export interface BackupRestoreResult {
  status: string
  message: string
  safety_backup: string | null
}

export interface EnvInfo {
  ollama_host: string
  ollama_model: string
  ollama_api_key_set: boolean
  vault_path: string
  db_path: string
  backup_dir: string
}

export interface VaultPathSetResult {
  vault_path: string
  watcher_started: boolean
  message: string
}