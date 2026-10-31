// TODO: Add transcript ingestion and processing flows in the next milestone.
import { useCallback, useEffect, useState, type FormEvent, type JSX } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { apiRequest } from '@/lib/api'
import type { Meeting } from '@/lib/types'

function todayAsDateInput(): string {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function Meetings(): JSX.Element {
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [title, setTitle] = useState('')
  const [meetingDate, setMeetingDate] = useState(todayAsDateInput)
  const [attendees, setAttendees] = useState('')
  const [transcript, setTranscript] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadMeetings = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      setMeetings(await apiRequest<Meeting[]>('/api/meetings'))
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Could not load meetings. Please try again.',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadMeetings()
  }, [loadMeetings])

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const meeting = await apiRequest<Meeting>('/api/meetings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          meeting_date: meetingDate,
          attendees: attendees
            .split(',')
            .map((name) => name.trim())
            .filter(Boolean),
          raw_transcript: transcript,
        }),
      })
      setMeetings((currentMeetings) =>
        [meeting, ...currentMeetings].sort((first, second) =>
          second.meeting_date.localeCompare(first.meeting_date),
        ),
      )
      setTitle('')
      setAttendees('')
      setTranscript('')
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Could not save this meeting. Please try again.',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-sm font-medium text-muted-foreground">Your team workspace</p>
          <h1 className="page-title">Meetings</h1>
          <p className="coming-soon">Add a meeting transcript to start building your team memory.</p>
        </div>
        <Badge variant="secondary">M1 · Meeting records</Badge>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Recent meetings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <p className="text-sm text-muted-foreground" role="status">Loading meetings…</p>
            ) : meetings.length === 0 ? (
              <p className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
                No meetings yet. Add the first transcript to your workspace.
              </p>
            ) : (
              meetings.map((meeting) => (
                <Link
                  className="block rounded-lg border p-4 transition-colors hover:border-primary/50 hover:bg-muted/40"
                  key={meeting.id}
                  to={`/meetings/${meeting.id}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className="font-semibold">{meeting.title}</h2>
                    <Badge variant="outline">{meeting.status}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {new Date(`${meeting.meeting_date}T00:00:00`).toLocaleDateString()} ·{' '}
                    {meeting.attendees.length > 0
                      ? meeting.attendees.join(', ')
                      : 'No attendees added'}
                  </p>
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Add a meeting</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
              <label className="block space-y-2 text-sm font-medium">
                Meeting title
                <Input
                  maxLength={200}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Weekly product sync"
                  required
                  value={title}
                />
              </label>
              <label className="block space-y-2 text-sm font-medium">
                Meeting date
                <Input
                  onChange={(event) => setMeetingDate(event.target.value)}
                  required
                  type="date"
                  value={meetingDate}
                />
              </label>
              <label className="block space-y-2 text-sm font-medium">
                Attendees
                <Input
                  onChange={(event) => setAttendees(event.target.value)}
                  placeholder="Priya, Rahul"
                  value={attendees}
                />
                <span className="block font-normal text-muted-foreground">
                  Use team member names, separated by commas.
                </span>
              </label>
              <label className="block space-y-2 text-sm font-medium">
                Labelled transcript
                <Textarea
                  className="min-h-36 resize-y"
                  onChange={(event) => setTranscript(event.target.value)}
                  placeholder={'Priya: Aaj ka agenda…\nRahul: Main update share karta hoon…'}
                  required
                  value={transcript}
                />
              </label>
              {error && (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              )}
              <Button className="w-full" disabled={saving} type="submit">
                {saving ? 'Saving meeting…' : 'Save meeting'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
