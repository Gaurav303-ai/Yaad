export interface Meeting {
  id: string
  title: string
  meeting_date: string
  attendees: string[]
  raw_transcript: string
  status: string
  created_at: string
}

export type ItemType = 'decision' | 'action' | 'intent'

export interface TranscriptSegment {
  speaker: string
  text: string
  order: number
}

export interface MeetingItem {
  id: string
  type: ItemType
  topic: string
  text: string
  owner_name: string | null
  deadline: string | null
  confidence: number | null
  source_quote: string
  speaker: string | null
  status: string
}

export interface MeetingDetail {
  meeting: Meeting
  segments: TranscriptSegment[]
  items: MeetingItem[]
}

export interface ProcessedItem extends MeetingItem {
  meeting_id: string
}

export interface ConflictSource {
  topic: string
  statement: string
  speaker: string | null
  source_quote: string
  meeting_date: string
}

export interface MeetingConflict {
  id: string
  label: 'contradiction' | 'update' | 'duplicate'
  explanation: string
  resolution: string | null
  new: ConflictSource
  old: ConflictSource
}

export interface ConflictSummary {
  label: 'contradiction' | 'update' | 'duplicate'
  explanation: string
}

export interface MemoryDecision {
  id: string
  meeting_id: string
  topic: string
  statement: string
  meeting_date: string
  deadline: string | null
  source_quote: string
  speaker: string
  status: string
}

export interface MeetingProcessResult {
  meeting_id: string
  meeting_date: string
  segments: TranscriptSegment[]
  items: ProcessedItem[]
  conflicts: ConflictSummary[]
}

export interface PersonSummary {
  member_id: string
  name: string
  role: string
  open_actions: number
  completed: number
  on_time_rate: number | null
  avg_slip_days: number | null
  reliability_score: number | null
}

export interface PersonDetail {
  summary: PersonSummary
  open_items: Array<{
    id: string
    topic: string
    text: string
    deadline: string | null
    status: string
    tracker_ref: string | null
  }>
}

export interface DigestPreview {
  id: string
  member_id: string
  member_name: string
  week_start: string
  subject: string
  body: string
  status: string
  sent_at: string | null
}
