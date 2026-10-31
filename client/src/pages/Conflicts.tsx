import { format } from 'date-fns'
import { motion } from 'framer-motion'
import { ArrowLeftRight, Check, GitMerge, History, LoaderCircle, ShieldAlert, X } from 'lucide-react'
import { useCallback, useEffect, useState, type JSX } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { apiRequest } from '@/lib/api'
import type { MeetingConflict } from '@/lib/types'

type Resolution = 'keep_new' | 'keep_old' | 'merge'

const labelName: Record<MeetingConflict['label'], string> = {
  contradiction: 'Contradiction',
  update: 'Explicit update',
  duplicate: 'Possible duplicate',
}

export function Conflicts(): JSX.Element {
  const [conflicts, setConflicts] = useState<MeetingConflict[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadConflicts = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      setConflicts(await apiRequest<MeetingConflict[]>('/api/conflicts'))
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Conflicts could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadConflicts()
  }, [loadConflicts])

  async function resolveConflict(conflictId: string, resolution: Resolution): Promise<void> {
    setSavingId(conflictId)
    try {
      await apiRequest<{ id: string; resolution: Resolution }>(`/api/conflicts/${conflictId}/resolution`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution }),
      })
      setConflicts((current) =>
        current.map((conflict) => conflict.id === conflictId ? { ...conflict, resolution } : conflict),
      )
      toast.success('Conflict decision saved.')
    } catch (requestError: unknown) {
      toast.error(requestError instanceof Error ? requestError.message : 'Could not save your decision.')
    } finally {
      setSavingId(null)
    }
  }

  const pendingCount = conflicts.filter((conflict) => conflict.resolution === null).length

  return (
    <section className="space-y-7">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-sm font-medium text-primary">Decision memory</p>
          <h1 className="page-title">Conflicts</h1>
          <p className="mt-2 text-sm text-muted-foreground">Compare what was said then and now. You make the final call.</p>
        </div>
        <Badge variant={pendingCount > 0 ? 'destructive' : 'secondary'}>{pendingCount} need review</Badge>
      </header>

      {error && (
        <div className="rounded-xl border border-destructive/20 p-5">
          <p className="text-sm text-destructive" role="alert">{error}</p>
          <Button className="mt-3" onClick={() => void loadConflicts()} variant="outline">Try again</Button>
        </div>
      )}

      {loading ? (
        <div className="space-y-4" aria-busy="true">
          {Array.from({ length: 2 }, (_, index) => <div className="h-96 animate-pulse rounded-2xl bg-muted" key={index} />)}
        </div>
      ) : conflicts.length === 0 && !error ? (
        <Card>
          <CardContent className="px-6 py-16 text-center">
            <ShieldAlert className="mx-auto size-8 text-primary" />
            <h2 className="mt-4 text-lg font-semibold">No conflicts to resolve</h2>
            <p className="mt-1 text-sm text-muted-foreground">New decisions are checked against active team memory after each meeting replay.</p>
          </CardContent>
        </Card>
      ) : (
        <motion.div className="space-y-5" initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.08 } } }}>
          {conflicts.map((conflict) => (
            <motion.article key={conflict.id} variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }}>
              <Card className="overflow-hidden">
                <CardHeader className="flex-row flex-wrap items-center justify-between gap-3 border-b bg-muted/25">
                  <div className="flex items-center gap-2">
                    <Badge variant={conflict.label === 'contradiction' ? 'destructive' : 'secondary'}>{labelName[conflict.label]}</Badge>
                    <span className="text-sm font-medium">{conflict.new.topic}</span>
                  </div>
                  {conflict.resolution ? (
                    <Badge variant="outline">Resolved · {conflict.resolution.replace('_', ' ')}</Badge>
                  ) : (
                    <Badge variant="outline">Human review</Badge>
                  )}
                </CardHeader>
                <CardContent className="space-y-5 p-5">
                  <div className="grid gap-4 lg:grid-cols-2">
                    <DecisionSide label="Earlier decision" source={conflict.old} tone="muted" />
                    <DecisionSide label="New decision" source={conflict.new} tone="primary" />
                  </div>
                  <div className="flex items-start gap-3 rounded-xl bg-muted/50 p-4">
                    <History className="mt-0.5 size-4 shrink-0 text-primary" />
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Why this was flagged</p>
                      <p className="mt-1 text-sm leading-6">{conflict.explanation}</p>
                    </div>
                  </div>
                  {conflict.resolution === null && (
                    <div className="flex flex-wrap justify-end gap-2 border-t pt-4">
                      <Button disabled={savingId === conflict.id} onClick={() => void resolveConflict(conflict.id, 'keep_old')} variant="outline">
                        {savingId === conflict.id ? <LoaderCircle className="mr-2 size-4 animate-spin" /> : <X className="mr-2 size-4" />}
                        Keep old
                      </Button>
                      <Button disabled={savingId === conflict.id} onClick={() => void resolveConflict(conflict.id, 'merge')} variant="outline">
                        <GitMerge className="mr-2 size-4" /> Merge
                      </Button>
                      <Button disabled={savingId === conflict.id} onClick={() => void resolveConflict(conflict.id, 'keep_new')}>
                        <Check className="mr-2 size-4" /> Keep new
                      </Button>
                    </div>
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

function DecisionSide({
  label,
  source,
  tone,
}: {
  label: string
  source: MeetingConflict['new']
  tone: 'muted' | 'primary'
}): JSX.Element {
  return (
    <article className={`rounded-xl border p-4 ${tone === 'primary' ? 'border-primary/20 bg-primary/[0.035]' : 'bg-muted/25'}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">{label}</h2>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <ArrowLeftRight className="size-3.5" /> {format(new Date(`${source.meeting_date}T00:00:00`), 'd MMM yyyy')}
        </span>
      </div>
      <p className="mt-3 font-medium">{source.statement}</p>
      <p className="mt-1 text-xs text-muted-foreground">Speaker: {source.speaker ?? 'Unknown'}</p>
      <blockquote className="mt-4 rounded-lg bg-background/80 p-3 text-sm leading-6 text-muted-foreground">
        “{source.source_quote}”
      </blockquote>
    </article>
  )
}
