import { format } from 'date-fns'
import { motion } from 'framer-motion'
import { Check, CircleHelp, Pencil, ShieldCheck, X } from 'lucide-react'
import { useCallback, useEffect, useState, type JSX } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { apiRequest } from '@/lib/api'
import type { ProcessedItem } from '@/lib/types'

export function Review(): JSX.Element {
  const [items, setItems] = useState<ProcessedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadItems = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      setItems(await apiRequest<ProcessedItem[]>('/api/items?status=pending'))
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Review items could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [])

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
        <Button disabled title="Approval actions are added in milestone M5">
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
        <p><span className="font-medium">Nothing is posted from this screen yet.</span> Approve, edit, and reject controls activate with the gated action workflow in M5.</p>
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
                      <Button disabled size="sm" title="Available in milestone M5" variant="outline"><Pencil className="mr-1.5 size-3.5" /> Edit</Button>
                      <Button disabled size="sm" title="Available in milestone M5" variant="outline"><X className="mr-1.5 size-3.5" /> Reject</Button>
                      <Button disabled size="sm" title="Available in milestone M5"><Check className="mr-1.5 size-3.5" /> Approve</Button>
                    </div>
                  </div>
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
