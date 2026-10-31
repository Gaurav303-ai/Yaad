import { format } from 'date-fns'
import { motion } from 'framer-motion'
import { CalendarDays, Search, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent, type JSX } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { apiRequest } from '@/lib/api'
import type { MemoryDecision } from '@/lib/types'

export function Memory(): JSX.Element {
  const [decisions, setDecisions] = useState<MemoryDecision[]>([])
  const [query, setQuery] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadMemory = useCallback(async (term: string): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const search = term.trim() ? `?query=${encodeURIComponent(term.trim())}` : ''
      setDecisions(await apiRequest<MemoryDecision[]>(`/api/memory${search}`))
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Decision memory could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadMemory(activeQuery)
  }, [activeQuery, loadMemory])

  function handleSearch(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    setActiveQuery(query)
  }

  const grouped = decisions.reduce<Record<string, MemoryDecision[]>>((groups, decision) => {
    const key = format(new Date(`${decision.meeting_date}T00:00:00`), 'MMMM yyyy')
    groups[key] ??= []
    groups[key].push(decision)
    return groups
  }, {})

  return (
    <section className="space-y-7">
      <header>
        <p className="mb-2 text-sm font-medium text-primary">What your team has agreed</p>
        <h1 className="page-title">Decision memory</h1>
        <p className="mt-2 text-sm text-muted-foreground">A searchable timeline of source-backed decisions, not a pile of transcripts.</p>
      </header>

      <Card>
        <CardContent className="p-4">
          <form className="flex flex-col gap-3 sm:flex-row" onSubmit={handleSearch}>
            <label className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="Search decision topics"
                className="pl-9"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search a topic, phrase, or speaker…"
                value={query}
              />
            </label>
            <Button type="submit"><Search className="mr-2 size-4" /> Search memory</Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-xl border border-destructive/20 p-5">
          <p className="text-sm text-destructive" role="alert">{error}</p>
          <Button className="mt-3" onClick={() => void loadMemory(activeQuery)} variant="outline">Try again</Button>
        </div>
      )}

      {loading ? (
        <div className="space-y-4" aria-busy="true">
          {Array.from({ length: 3 }, (_, index) => <div className="h-48 animate-pulse rounded-2xl bg-muted" key={index} />)}
        </div>
      ) : decisions.length === 0 && !error ? (
        <Card>
          <CardContent className="px-6 py-16 text-center">
            <Sparkles className="mx-auto size-8 text-primary" />
            <h2 className="mt-4 text-lg font-semibold">{activeQuery ? 'No matching decisions' : 'Memory is ready to grow'}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {activeQuery ? 'Try another phrase or clear your search.' : 'Replay a meeting to add its confirmed decisions to the timeline.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-8">
          {Object.entries(grouped).map(([month, entries]) => (
            <section key={month}>
              <div className="mb-4 flex items-center gap-3">
                <h2 className="text-sm font-semibold">{month}</h2>
                <span className="h-px flex-1 bg-border" />
                <Badge variant="outline">{entries.length}</Badge>
              </div>
              <div className="space-y-3">
                {entries.map((decision) => (
                  <motion.article key={decision.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                    <Card>
                      <CardContent className="grid gap-4 p-5 sm:grid-cols-[minmax(0,1fr)_auto]">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="secondary">{decision.topic}</Badge>
                            <span className="text-xs text-muted-foreground">{decision.speaker}</span>
                          </div>
                          <p className="mt-3 font-medium leading-6">{decision.statement}</p>
                          <blockquote className="mt-3 border-l-2 border-primary/40 pl-3 text-sm leading-6 text-muted-foreground">
                            “{decision.source_quote}”
                          </blockquote>
                        </div>
                        <div className="flex items-start gap-2 text-xs text-muted-foreground sm:justify-end">
                          <CalendarDays className="mt-0.5 size-3.5" />
                          {format(new Date(`${decision.meeting_date}T00:00:00`), 'd MMM yyyy')}
                        </div>
                      </CardContent>
                    </Card>
                  </motion.article>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </section>
  )
}
