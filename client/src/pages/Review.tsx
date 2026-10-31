import { format } from 'date-fns'
import { motion } from 'framer-motion'
import { Check, CircleHelp, Pencil, ShieldCheck, TriangleAlert, X } from 'lucide-react'
import { useCallback, useEffect, useState, type JSX } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import { apiRequest } from '@/lib/api'
import type { PersonSummary, ProcessedItem } from '@/lib/types'

export function Review(): JSX.Element {
  const [items, setItems] = useState<ProcessedItem[]>([])
  const [people, setPeople] = useState<PersonSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState({ text: '', owner: '', deadline: '' })

  const loadItems = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const [nextItems, nextPeople] = await Promise.all([
        apiRequest<ProcessedItem[]>('/api/items?status=pending'),
        apiRequest<PersonSummary[]>('/api/people'),
      ])
      setItems(nextItems)
      setPeople(nextPeople)
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Review items could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [])

  async function approveItem(item: ProcessedItem): Promise<void> {
    setError(null)
    try {
      await apiRequest<{ status: string }>(`/api/items/${item.id}/approve`, { method: 'POST' })
      await loadItems()
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'The item could not be approved.')
    }
  }

  async function rejectItem(item: ProcessedItem): Promise<void> {
    setError(null)
    try {
      await apiRequest<{ status: string }>(`/api/items/${item.id}/reject`, { method: 'POST' })
      await loadItems()
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'The item could not be rejected.')
    }
  }

  async function approveAll(): Promise<void> {
    setError(null)
    try {
      await apiRequest<Array<{ status: string }>>('/api/items/approve-all', { method: 'POST' })
      await loadItems()
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Pending actions could not be approved.')
    }
  }

  function startEditing(item: ProcessedItem): void {
    setEditingId(item.id)
    setDraft({
      text: item.text,
      owner: item.owner_name ?? '',
      deadline: item.deadline ? format(new Date(item.deadline), "yyyy-MM-dd'T'HH:mm") : '',
    })
  }

  async function saveEdit(item: ProcessedItem): Promise<void> {
    setError(null)
    try {
      await apiRequest<ProcessedItem>(`/api/items/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: draft.text,
          owner_name: draft.owner.trim() || null,
          deadline: draft.deadline ? new Date(draft.deadline).toISOString() : null,
        }),
      })
      setEditingId(null)
      await loadItems()
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'The item could not be edited.')
    }
  }

  useEffect(() => {
    void loadItems()
  }, [loadItems])

  const pendingActions = items.filter((item) => item.type === 'action')
  const intents = items.filter((item) => item.type === 'intent')
  const decisions = items.filter((item) => item.type === 'decision')

  return (
    <section className="space-y-7">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-sm font-medium text-primary">Human confirmation</p>
          <h1 className="page-title">Review & confirm</h1>
          <p className="mt-2 text-sm text-muted-foreground">Check every owner, deadline, and source before an action leaves Yaad.</p>
        </div>
        <Button disabled={pendingActions.length === 0 || loading} onClick={() => void approveAll()}>
          <Check className="mr-2 size-4" /> Approve all actions
        </Button>
      </header>

      <div className="flex flex-wrap gap-2">
        <Badge variant="default">{pendingActions.length} actions</Badge>
        <Badge variant="secondary">{decisions.length} decisions</Badge>
        <Badge variant="outline">{intents.length} intents · never sent to tracker</Badge>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/[0.035] p-4 text-sm">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
        <p><span className="font-medium">Actions are posted only after approval.</span> Rejected items are removed from the review queue, and intents never create tracker tasks.</p>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/20 p-5">
          <p className="text-sm text-destructive" role="alert">{error}</p>
          <Button className="mt-3" onClick={() => void loadItems()} variant="outline">Try again</Button>
        </div>
      )}

      {loading ? (
        <div className="space-y-3" aria-busy="true">
          {Array.from({ length: 3 }, (_, index) => <div className="h-52 animate-pulse rounded-2xl bg-muted" key={index} />)}
        </div>
      ) : items.length === 0 && !error ? (
        <Card>
          <CardContent className="px-6 py-14 text-center">
            <Check className="mx-auto size-8 rounded-full bg-primary/10 p-1.5 text-primary" />
            <h2 className="mt-4 text-lg font-semibold">Review queue is clear</h2>
            <p className="mt-1 text-sm text-muted-foreground">Run a meeting replay to bring new decisions and actions here.</p>
            <Button className="mt-5" variant="outline" render={<Link to="/meetings" />}>Open meetings</Button>
          </CardContent>
        </Card>
      ) : (
        <motion.div className="space-y-4" initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}>
          {items.map((item) => (
            <motion.article key={item.id} variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}>
              <Card>
                <CardHeader className="flex-row items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={item.type === 'action' ? 'default' : 'secondary'}>{item.type}</Badge>
                      <CardTitle>{item.topic}</CardTitle>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.text}</p>
                  </div>
                  <Badge variant="outline">{item.status}</Badge>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-xl bg-muted/50 p-3">
                      <p className="text-xs text-muted-foreground">Owner</p>
                      <p className="mt-1 text-sm font-medium">{item.owner_name ?? 'Unassigned'}</p>
                    </div>
                    {item.deadline && item.owner_name && people.some((person) =>
                      person.name === item.owner_name &&
                      ((person.on_time_rate !== null && person.on_time_rate < 60) ||
                        (person.avg_slip_days !== null && person.avg_slip_days > 3))
                    ) && (
                      <p className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/[0.05] p-3 text-sm text-amber-800 dark:text-amber-200">
                        <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                        {item.owner_name} has a history of slipping deadlines. Consider confirming this date before approval.
                      </p>
                    )}
                    <div className="rounded-xl bg-muted/50 p-3">
                      <p className="text-xs text-muted-foreground">Deadline</p>
                      <p className="mt-1 text-sm font-medium">
                        {item.deadline ? format(new Date(item.deadline), 'EEE, d MMM yyyy · HH:mm') : 'No date stated'}
                      </p>
                    </div>
                    <div className="rounded-xl bg-muted/50 p-3">
                      <div className="flex justify-between gap-2 text-xs">
                        <span className="text-muted-foreground">Confidence</span>
                        <span className="font-medium">{item.confidence === null ? '—' : `${Math.round(item.confidence * 100)}%`}</span>
                      </div>
                      {item.confidence !== null && <Progress className="mt-2 h-1.5" value={item.confidence * 100} />}
                    </div>
                  </div>
                  <blockquote className="rounded-xl border-l-2 border-primary/50 bg-muted/40 px-4 py-3 text-sm leading-6">
                    <p className="text-xs font-medium text-muted-foreground">{item.speaker ?? 'Speaker'} · source quote</p>
                    <p className="mt-1">“{item.source_quote}”</p>
                  </blockquote>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Link className="text-sm font-medium text-primary hover:underline" to={`/meetings/${item.meeting_id}`}>
                      Open source meeting →
                    </Link>
                    <div className="flex gap-2">
                      <Button onClick={() => startEditing(item)} size="sm" variant="outline"><Pencil className="mr-1.5 size-3.5" /> Edit</Button>
                      <Button onClick={() => void rejectItem(item)} size="sm" variant="outline"><X className="mr-1.5 size-3.5" /> Reject</Button>
                      <Button disabled={item.type === 'intent'} onClick={() => void approveItem(item)} size="sm">
                        <Check className="mr-1.5 size-3.5" />
                        {item.status === 'approved' ? 'Retry tracker' : 'Approve'}
                      </Button>
                    </div>
                  </div>
                  {editingId === item.id && (
                    <div className="grid gap-3 rounded-xl border bg-muted/20 p-4">
                      <Textarea
                        aria-label="Edited item text"
                        onChange={(event) => setDraft((current) => ({ ...current, text: event.target.value }))}
                        value={draft.text}
                      />
                      <div className="grid gap-3 sm:grid-cols-2">
                        <Input
                          aria-label="Owner name"
                          onChange={(event) => setDraft((current) => ({ ...current, owner: event.target.value }))}
                          placeholder="Owner name"
                          value={draft.owner}
                        />
                        <Input
                          aria-label="Deadline"
                          onChange={(event) => setDraft((current) => ({ ...current, deadline: event.target.value }))}
                          type="datetime-local"
                          value={draft.deadline}
                        />
                      </div>
                      <div className="flex justify-end gap-2">
                        <Button onClick={() => setEditingId(null)} size="sm" variant="ghost">Cancel</Button>
                        <Button disabled={!draft.text.trim()} onClick={() => void saveEdit(item)} size="sm">Save edits</Button>
                      </div>
                    </div>
                  )}
                  {item.type === 'intent' && (
                    <p className="flex items-center gap-2 text-xs text-muted-foreground"><CircleHelp className="size-3.5" /> Tentative discussion only; it will not become a task.</p>
                  )}
                </CardContent>
              </Card>
            </motion.article>
          ))}
        </motion.div>
      )}
    </section>
  )
}
