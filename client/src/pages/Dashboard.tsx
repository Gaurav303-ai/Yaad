import { format, formatDistanceToNow, isBefore, addDays, startOfDay } from 'date-fns'
import { motion } from 'framer-motion'
import { ArrowDownRight, ArrowUpRight, ArrowUpRightFromSquare, CalendarClock, CircleCheck, Clock3, Plus, TriangleAlert } from 'lucide-react'
import { useCallback, useEffect, useState, type JSX } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { apiRequest } from '@/lib/api'
import type { Meeting, MeetingConflict, ProcessedItem } from '@/lib/types'

interface DashboardData {
  meetings: Meeting[]
  items: ProcessedItem[]
  conflicts: MeetingConflict[]
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}

const rise = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.32 } },
}

export function Dashboard(): JSX.Element {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadDashboard = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const [meetings, items, conflicts] = await Promise.all([
        apiRequest<Meeting[]>('/api/meetings'),
        apiRequest<ProcessedItem[]>('/api/items?status=pending'),
        apiRequest<MeetingConflict[]>('/api/conflicts'),
      ])
      setData({ meetings, items, conflicts })
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Dashboard data could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadDashboard()
  }, [loadDashboard])

  if (loading) {
    return (
      <section className="space-y-8" aria-busy="true">
        <Skeleton className="h-28 w-full rounded-2xl" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => <Skeleton className="h-32 rounded-2xl" key={index} />)}
        </div>
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-72 rounded-2xl" />
          <Skeleton className="h-72 rounded-2xl" />
        </div>
      </section>
    )
  }

  if (error || !data) {
    return (
      <section className="rounded-2xl border border-destructive/20 bg-card p-8">
        <h1 className="page-title">Dashboard</h1>
        <p className="mt-3 text-sm text-destructive" role="alert">{error ?? 'Dashboard data is unavailable.'}</p>
        <Button className="mt-5" onClick={() => void loadDashboard()}>Try again</Button>
      </section>
    )
  }

  const today = startOfDay(new Date())
  const nextWeek = addDays(today, 7)
  const openItems = data.items.filter((item) => item.type === 'action')
  const dueItems = openItems
    .filter((item) => item.deadline !== null)
    .sort((first, second) => (first.deadline ?? '').localeCompare(second.deadline ?? ''))
  const upcoming = dueItems.filter((item) => {
    const deadline = new Date(item.deadline ?? '')
    return !isBefore(deadline, today) && isBefore(deadline, nextWeek)
  })
  const urgent = dueItems.filter((item) => {
    const deadline = new Date(item.deadline ?? '')
    return !isBefore(deadline, today) && isBefore(deadline, addDays(today, 2))
  })
  const pendingConflicts = data.conflicts.filter((conflict) => conflict.resolution === null)
  const stats = [
    { label: 'Open actions', value: openItems.length, icon: CircleCheck, note: 'Waiting for review' },
    { label: 'Due this week', value: upcoming.length, icon: CalendarClock, note: `${urgent.length} in the next 48 hours` },
    { label: 'Pending conflicts', value: pendingConflicts.length, icon: TriangleAlert, note: 'Need a decision' },
    { label: 'Meetings tracked', value: data.meetings.length, icon: Clock3, note: 'Across your team' },
  ]

  return (
    <motion.section className="space-y-8" variants={stagger} initial="hidden" animate="show">
      <motion.header variants={rise} className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="mb-2 text-sm font-medium text-primary">Your team workspace</p>
          <h1 className="page-title">Good morning, team <span aria-hidden="true">✦</span></h1>
          <p className="mt-2 text-sm text-muted-foreground">A clear view of what was decided — and what happens next.</p>
        </div>
        <Link className={buttonVariants()} to="/meetings">
          <Plus className="mr-2 size-4" /> New meeting
        </Link>
      </motion.header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, note }, index) => (
          <motion.div key={label} variants={rise}>
            <Card className="h-full overflow-hidden">
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <p className="text-sm text-muted-foreground">{label}</p>
                  <span className="rounded-xl bg-primary/10 p-2 text-primary"><Icon className="size-4" /></span>
                </div>
                <p className="mt-4 text-3xl font-semibold tracking-tight">{value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{note}</p>
                <div className={`mt-4 h-1 rounded-full ${index === 2 ? 'bg-amber-400/70' : 'bg-primary/20'}`} />
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <motion.div variants={rise}>
          <Card className="h-full">
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>Upcoming deadlines</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">Keep the next commitments in view.</p>
              </div>
              <Link className="text-sm font-medium text-primary hover:underline" to="/review">Review items <ArrowUpRight className="inline size-4" /></Link>
            </CardHeader>
            <CardContent className="space-y-3">
              {upcoming.length === 0 ? (
                <div className="rounded-xl border border-dashed p-6 text-center">
                  <CircleCheck className="mx-auto size-5 text-primary" />
                  <p className="mt-2 text-sm font-medium">You’re all clear this week</p>
                  <p className="mt-1 text-xs text-muted-foreground">New approved actions with deadlines will show here.</p>
                </div>
              ) : upcoming.slice(0, 5).map((item) => (
                <div className="flex items-center justify-between gap-4 rounded-xl border p-4" key={item.id}>
                  <div className="min-w-0">
                    <p className="truncate font-medium">{item.topic}</p>
                    <p className="mt-1 truncate text-sm text-muted-foreground">{item.owner_name ?? 'Owner unassigned'} · {item.text}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <Badge variant={urgent.some((candidate) => candidate.id === item.id) ? 'destructive' : 'secondary'}>
                      {format(new Date(item.deadline ?? ''), 'EEE, d MMM')}
                    </Badge>
                    <p className="mt-1 text-xs text-muted-foreground">{formatDistanceToNow(new Date(item.deadline ?? ''), { addSuffix: true })}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={rise}>
          <Card className="h-full">
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>Recent meetings</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">Decisions stay connected to their source.</p>
              </div>
              <Link className="text-sm font-medium text-primary hover:underline" to="/meetings">All <ArrowUpRightFromSquare className="inline size-3.5" /></Link>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.meetings.slice(0, 5).map((meeting) => (
                <Link
                  className="group flex items-center justify-between gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-muted/70"
                  key={meeting.id}
                  to={`/meetings/${meeting.id}`}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{meeting.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{format(new Date(`${meeting.meeting_date}T00:00:00`), 'd MMM yyyy')} · {meeting.attendees.join(', ') || 'Team sync'}</p>
                  </div>
                  <Badge variant="outline">{meeting.status}</Badge>
                </Link>
              ))}
              {data.meetings.length === 0 && (
                <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">No meetings yet.</p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {pendingConflicts.length > 0 && (
        <motion.div variants={rise}>
          <Card className="border-amber-500/30 bg-amber-500/[0.03]">
            <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
              <div className="flex items-start gap-3">
                <span className="rounded-xl bg-amber-500/10 p-2 text-amber-700 dark:text-amber-300"><TriangleAlert className="size-4" /></span>
                <div>
                  <p className="font-medium">{pendingConflicts.length} decision{pendingConflicts.length === 1 ? '' : 's'} need a human call</p>
                  <p className="mt-1 text-sm text-muted-foreground">The latest meeting may have changed something already agreed.</p>
                </div>
              </div>
              <Link className={buttonVariants({ variant: 'outline' })} to="/conflicts">
                Review conflicts <ArrowDownRight className="ml-2 size-4" />
              </Link>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </motion.section>
  )
}
