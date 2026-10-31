// TODO: Define shared client API types.
export type ApiResponse<T> = T

export interface Meeting {
  id: string
  title: string
  meeting_date: string
  attendees: string[]
  raw_transcript: string
  status: string
  created_at: string
}
