import { format } from 'date-fns'
import { motion } from 'framer-motion'
import { Activity, CalendarDays, CirclePlay, LoaderCircle, Quote, Sparkles, TriangleAlert } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type JSX } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { apiRequest, apiUrl } from '@/lib/api'
import type { ConflictSummary, MeetingDetail, MeetingItem, TranscriptSegment } from '@/lib/types'

const speakerColors = [
  'border-l-primary bg-primary/[0.04]',
  'border-l-sky-500 bg-sky-500/[0.04]',
  'border-l-violet-500 bg-violet-500/[0.04]',
  'border-l-amber-500 bg-amber-500/[0.04]',
]

function eventData<T>(event: MessageEvent<string>): T {
  return JSON.parse(event.data) as T
}

function speakerColor(speaker: string, names: string[]): string {
  const index = Math.max(names.indexOf(speaker), 0)
  return speakerColors[index % speakerColors.length]
}

export function MeetingRoom(): JSX.Element {
  const { meetingId } = useParams()
  const [detail, setDetail] = useState<MeetingDetail | null>(null)
  const [segments, setSegments] = useState<TranscriptSegment[]>([])
  const [items, setItems] = useState<MeetingItem[]>([])
  const [conflicts, setConflicts] = useState<ConflictSummary[]>([])
  const [activity, setActivity] = useState('Waiting to start')
  const [loading, setLoading] = useState(true)
  const [replaying, setReplaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const streamRef = useRef<EventSource | null>(null)
  const speakerNames = [...new Set(segments.map((segment) => segment.speaker))]

  const loadMeeting = useCallback(async (): Promise<void> => {
    if (!meetingId) {
      setError('Meeting ID is missing from this URL.')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const result = await apiRequest<MeetingDetail>(`/api/meetings/${meetingId}`)
      setDetail(result)
      setSegments(result.segments)
      setItems(result.items)
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Could not load this meeting.')
    } finally {
      setLoading(false)
    }
  }, [meetingId])

  useEffect(() => {
    void loadMeeting()
    return () => streamRef.current?.close()
  }, [loadMeeting])

  function startReplay(): void {
    if (!meetingId || replaying) return
    streamRef.current?.close()
    setSegments([])
    setItems([])
    setConflicts([])
    setError(null)
    setReplaying(true)
    setActivity('Opening live replay…')
    const stream = new EventSource(apiUrl(`/api/meetings/${meetingId}/replay`))
    streamRef.current = stream

    stream.addEventListener('agent', (event: MessageEvent<string>) => {
      const message = eventData<{ message: string }>(event).message
      setActivity(message)
    })
    stream.addEventListener('segment', (event: MessageEvent<string>) => {
      const segment = eventData<TranscriptSegment>(event)
      setSegments((current) => [...current, segment])
    })
    stream.addEventListener('item', (event: MessageEvent<string>) => {
      const item = eventData<MeetingItem>(event)
      setItems((current) => [...current, item])
      setActivity(`Verified “${item.topic}” with its source quote`)
    })
    stream.addEventListener('conflicts', (event: MessageEvent<string>) => {
      setConflicts(eventData<ConflictSummary[]>(event))
    })
    stream.addEventListener('error', (event: MessageEvent<string>) => {
      if (!event.data) return
      const message = eventData<{ message: string }>(event).message
      setError(message)
      setReplaying(false)
      stream.close()
    })
    stream.addEventListener('complete', () => {
      setActivity('Replay complete · extraction saved to the review queue')
      setReplaying(false)
      stream.close()
      void loadMeeting()
    })
    stream.onerror = () => {
      if (stream.readyState === EventSource.CLOSED) {
        setError('Live replay connection closed before completion. Try replaying again.')
        setReplaying(false)
      }
    }
  }

  if (loading) {
    return <div className="grid gap-5 lg:grid-cols-2" aria-busy="true"><div className="h-[620px] animate-pulse rounded-2xl bg-muted" /><div className="h-[620px] animate-pulse rounded-2xl bg-muted" /></div>
  }

  if (error && !detail) {
    return (
      <section className="rounded-2xl border border-destructive/20 bg-card p-8">
        <h1 className="page-title">Meeting room</h1>
        <p className="mt-3 text-sm text-destructive" role="alert">{error}</p>
        <Button className="mt-5" onClick={() => void loadMeeting()}>Try again</Button>
      </section>
    )
  }

  if (!detail) return <p role="alert">Meeting details are unavailable.</p>

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link className="text-sm font-medium text-primary hover:underline" to="/meetings">← All meetings</Link>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <h1 className="page-title">{detail.meeting.title}</h1>
            <Badge variant={detail.meeting.status === 'review' ? 'secondary' : 'outline'}>{detail.meeting.status}</Badge>
          </div>
          <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            <CalendarDays className="size-4" />
            {format(new Date(`${detail.meeting.meeting_date}T00:00:00`), 'EEEE, d MMMM yyyy')}
            <span>·</span>{detail.meeting.attendees.join(', ') || 'Team meeting'}
          </p>
        </div>
        <Button disabled={replaying} onClick={startReplay}>
          {replaying ? <LoaderCircle className="mr-2 size-4 animate-spin" /> : <CirclePlay className="mr-2 size-4" />}
          {replaying ? 'Replaying…' : 'Live replay'}
        </Button>
      </header>

      {error && <p className="rounded-xl border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{error}</p>}

      <Card className="border-primary/15 bg-primary/[0.035]">
        <CardContent className="flex items-center gap-3 p-4">
          <span className="rounded-xl bg-primary/10 p-2 text-primary"><Activity className="size-4" /></span>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Agent activity</p>
            <p aria-live="polite" className="mt-0.5 truncate text-sm">{activity}</p>
          </div>
          {replaying && <LoaderCircle className="ml-auto size-4 animate-spin text-primary" />}
        </CardContent>
      </Card>

      {conflicts.length > 0 && (
        <Link className="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/[0.04] p-4 text-sm" to="/conflicts">
          <TriangleAlert className="size-4 text-amber-600" />
          {conflicts.length} possible conflict{conflicts.length === 1 ? '' : 's'} found — review the earlier decision side by side.
          <span className="ml-auto text-primary">Review →</span>
        </Link>
      )}

      <div className="grid items-start gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><span className="size-2 rounded-full bg-primary" /> Transcript</CardTitle>
            <p className="text-sm text-muted-foreground">Speaker-labelled turns, streamed as they are replayed.</p>
          </CardHeader>
          <CardContent className="max-h-[70vh] space-y-3 overflow-y-auto">
            {segments.length === 0 ? (
              <div className="rounded-xl border border-dashed p-8 text-center">
                <Sparkles className="mx-auto size-5 text-primary" />
                <p className="mt-2 text-sm font-medium">Ready when you are</p>
                <p className="mt-1 text-xs text-muted-foreground">Start Live Replay to stream the transcript and run extraction.</p>
              </div>
            ) : segments.map((segment) => (
              <motion.article
                animate={{ opacity: 1, x: 0 }}
                className={`rounded-r-xl border-l-2 p-3 ${speakerColor(segment.speaker, speakerNames)}`}
                initial={{ opacity: 0, x: -8 }}
                key={`${segment.order}-${segment.speaker}`}
              >
                <p className="mb-1 text-xs font-semibold text-primary">{segment.speaker}</p>
                <p className="text-sm leading-6">{segment.text}</p>
              </motion.article>
            ))}
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="flex items-center gap-2"><Sparkles className="size-4 text-primary" /> Structured items</CardTitle>
              <Badge variant="outline">{items.length} found</Badge>
            </div>
            <p className="text-sm text-muted-foreground">Every item stays linked to the words that support it.</p>
          </CardHeader>
          <CardContent className="max-h-[70vh] space-y-3 overflow-y-auto">
            {items.length === 0 ? (
              <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                Extracted decisions, actions, and intents will appear here.
              </div>
            ) : items.map((item) => (
              <motion.article
                animate={{ opacity: 1, y: 0 }}
                className="rounded-xl border bg-background p-4"
                initial={{ opacity: 0, y: 10 }}
                key={item.id}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge variant={item.type === 'action' ? 'default' : 'secondary'}>{item.type}</Badge>
                    <h2 className="font-medium">{item.topic}</h2>
                  </div>
                  <Badge variant="outline">{item.confidence === null ? '—' : `${Math.round(item.confidence * 100)}% confidence`}</Badge>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.text}</p>
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>Owner: {item.owner_name ?? 'Unassigned'}</span>
                  <span>Due: {item.deadline ? format(new Date(item.deadline), 'd MMM yyyy') : item.type === 'intent' ? 'No commitment' : 'Not specified'}</span>
                </div>
                {item.confidence !== null && <Progress className="mt-3 h-1.5" value={item.confidence * 100} />}
                <blockquote className="mt-4 flex gap-2 rounded-lg bg-muted/60 p-3 text-xs leading-5 text-muted-foreground">
                  <Quote className="mt-0.5 size-3.5 shrink-0 text-primary" />
                  <span><span className="font-medium text-foreground">{item.speaker ?? 'Speaker'} said:</span> “{item.source_quote}”</span>
                </blockquote>
              </motion.article>
            ))}
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
