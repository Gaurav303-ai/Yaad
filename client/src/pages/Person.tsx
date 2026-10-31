import { format } from 'date-fns'
import { motion } from 'framer-motion'
import { ArrowUpRight, Check, Clock3, Gauge, UsersRound } from 'lucide-react'
import { useCallback, useEffect, useState, type JSX } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { apiRequest } from '@/lib/api'
import type { PersonDetail, PersonSummary } from '@/lib/types'

export function Person(): JSX.Element {
  const { personId } = useParams()
  const [people, setPeople] = useState<PersonSummary[]>([])
  const [profile, setProfile] = useState<PersonDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadPeople = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      if (personId) {
        setProfile(await apiRequest<PersonDetail>(`/api/people/${personId}`))
      } else {
        setPeople(await apiRequest<PersonSummary[]>('/api/people'))
      }
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Team profiles could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [personId])

  useEffect(() => {
    void loadPeople()
  }, [loadPeople])

  async function completeItem(itemId: string): Promise<void> {
    setError(null)
    try {
      await apiRequest<{ status: string }>(`/api/items/${itemId}/complete`, { method: 'POST' })
      await loadPeople()
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'The action could not be completed.')
    }
  }

  if (loading) {
    return <div aria-busy="true" className="h-72 animate-pulse rounded-2xl bg-muted" />
  }

  if (error) {
    return (
      <section className="rounded-2xl border border-destructive/20 p-7">
        <h1 className="page-title">People</h1>
        <p className="mt-3 text-sm text-destructive" role="alert">{error}</p>
        <Button className="mt-4" onClick={() => void loadPeople()} variant="outline">Try again</Button>
      </section>
    )
  }

  if (!personId) {
    return (
      <section className="space-y-6">
        <header>
          <p className="mb-2 text-sm font-medium text-primary">Team follow-through</p>
          <h1 className="page-title">People</h1>
          <p className="mt-2 text-sm text-muted-foreground">Open commitments and completion reliability, all in one place.</p>
        </header>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {people.map((person, index) => (
            <motion.div key={person.member_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }}>
              <Link className="block h-full" to={`/people/${person.member_id}`}>
                <Card className="h-full transition hover:-translate-y-0.5 hover:border-primary/30">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <CardTitle>{person.name}</CardTitle>
                        <p className="mt-1 text-sm text-muted-foreground">{person.role}</p>
                      </div>
                      <ArrowUpRight className="size-4 text-muted-foreground" />
                    </div>
                  </CardHeader>
                  <CardContent className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl bg-muted/50 p-3">
                      <p className="text-xs text-muted-foreground">Open actions</p>
                      <p className="mt-1 text-xl font-semibold">{person.open_actions}</p>
                    </div>
                    <div className="rounded-xl bg-muted/50 p-3">
                      <p className="text-xs text-muted-foreground">On-time rate</p>
                      <p className="mt-1 text-xl font-semibold">{person.on_time_rate === null ? '—' : `${Math.round(person.on_time_rate)}%`}</p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
          {people.length === 0 && <p className="text-sm text-muted-foreground">No team members are configured.</p>}
        </div>
      </section>
    )
  }

  if (!profile) return <p role="alert">This profile is unavailable.</p>
  const { summary } = profile

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link className="text-sm font-medium text-primary hover:underline" to="/people">← All people</Link>
          <p className="mb-2 mt-4 text-sm font-medium text-primary">Team profile</p>
          <h1 className="page-title">{summary.name}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{summary.role}</p>
        </div>
        <Badge variant="outline">{summary.completed} completed commitments</Badge>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-5">
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><Gauge className="size-4" /> Reliability</p>
            <p className="mt-3 text-3xl font-semibold">{summary.reliability_score === null ? '—' : `${Math.round(summary.reliability_score)}%`}</p>
            {summary.reliability_score !== null && <Progress className="mt-3" value={summary.reliability_score} />}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><Clock3 className="size-4" /> Average slip</p>
            <p className="mt-3 text-3xl font-semibold">{summary.avg_slip_days === null ? '—' : `${summary.avg_slip_days.toFixed(1)}d`}</p>
            <p className="mt-1 text-xs text-muted-foreground">Across completed commitments</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><UsersRound className="size-4" /> Open actions</p>
            <p className="mt-3 text-3xl font-semibold">{summary.open_actions}</p>
            <p className="mt-1 text-xs text-muted-foreground">Pending or approved</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Open actions</CardTitle>
          <p className="text-sm text-muted-foreground">Approved tasks can be marked complete here.</p>
        </CardHeader>
        <CardContent className="space-y-3">
          {profile.open_items.map((item) => (
            <article className="flex flex-wrap items-center justify-between gap-4 rounded-xl border p-4" key={item.id}>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={item.status === 'approved' ? 'default' : 'outline'}>{item.status}</Badge>
                  <p className="font-medium">{item.topic}</p>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{item.text}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {item.deadline ? `Due ${format(new Date(item.deadline), 'd MMM yyyy · HH:mm')}` : 'No deadline'}
                </p>
              </div>
              {item.status === 'approved' && item.tracker_ref && (
                <div className="flex items-center gap-2">
                  <a className="text-sm font-medium text-primary hover:underline" href={item.tracker_ref} rel="noreferrer" target="_blank">Open task</a>
                  <Button onClick={() => void completeItem(item.id)} size="sm"><Check className="mr-1.5 size-4" /> Done</Button>
                </div>
              )}
            </article>
          ))}
          {profile.open_items.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">No open actions assigned.</p>}
        </CardContent>
      </Card>
    </section>
  )
}
