import { format } from 'date-fns'
import { Check, MailCheck, RefreshCw, X } from 'lucide-react'
import { useEffect, useState, type JSX } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { apiRequest } from '@/lib/api'
import type { DigestPreview, PersonSummary } from '@/lib/types'

export function Digest(): JSX.Element {
  const [people, setPeople] = useState<PersonSummary[]>([])
  const [memberId, setMemberId] = useState('')
  const [digest, setDigest] = useState<DigestPreview | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void apiRequest<PersonSummary[]>('/api/people')
      .then((result) => {
        setPeople(result)
        if (result[0]) setMemberId(result[0].member_id)
      })
      .catch((requestError: unknown) => {
        setError(requestError instanceof Error ? requestError.message : 'Digest recipients could not be loaded.')
      })
      .finally(() => setLoading(false))
  }, [])

  async function createPreview(): Promise<void> {
    if (!memberId) return
    setSaving(true)
    setError(null)
    try {
      setDigest(await apiRequest<DigestPreview>('/api/digests/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ member_id: memberId }),
      }))
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'A digest preview could not be prepared.')
    } finally {
      setSaving(false)
    }
  }

  async function updateDigest(action: 'approve' | 'reject'): Promise<void> {
    if (!digest) return
    setSaving(true)
    setError(null)
    try {
      if (action === 'approve') {
        setDigest(await apiRequest<DigestPreview>(`/api/digests/${digest.id}/approve`, { method: 'POST' }))
      } else {
        await apiRequest<{ status: string }>(`/api/digests/${digest.id}/reject`, { method: 'POST' })
        setDigest(null)
      }
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'The digest action could not be completed.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="mx-auto max-w-4xl space-y-6">
      <header>
        <p className="mb-2 text-sm font-medium text-primary">Weekly, personal, and reviewable</p>
        <h1 className="page-title">Digest</h1>
        <p className="mt-2 text-sm text-muted-foreground">Each person sees their own approved work. Nothing is emailed until you approve the preview.</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Prepare a preview</CardTitle>
          <p className="text-sm text-muted-foreground">Choose a teammate to create their weekly draft.</p>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <select
            aria-label="Digest recipient"
            className="h-10 min-w-56 rounded-lg border bg-background px-3 text-sm"
            disabled={loading || people.length === 0}
            onChange={(event) => {
              setMemberId(event.target.value)
              setDigest(null)
            }}
            value={memberId}
          >
            {people.map((person) => <option key={person.member_id} value={person.member_id}>{person.name}</option>)}
          </select>
          <Button disabled={!memberId || saving} onClick={() => void createPreview()}>
            <RefreshCw className={`mr-2 size-4${saving ? ' animate-spin' : ''}`} /> Create preview
          </Button>
        </CardContent>
      </Card>

      {error && <p className="rounded-xl border border-destructive/20 p-4 text-sm text-destructive" role="alert">{error}</p>}

      {digest && (
        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle>{digest.member_name}</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Week of {format(new Date(`${digest.week_start}T00:00:00`), 'd MMM yyyy')} · {digest.subject}
              </p>
            </div>
            <Badge variant={digest.status === 'sent' ? 'default' : 'secondary'}>{digest.status}</Badge>
          </CardHeader>
          <CardContent className="space-y-5">
            <pre className="whitespace-pre-wrap rounded-xl bg-muted/40 p-5 font-sans text-sm leading-6">{digest.body}</pre>
            {digest.sent_at && <p className="text-xs text-muted-foreground">Sent {format(new Date(digest.sent_at), 'd MMM yyyy · HH:mm')}</p>}
            {digest.status !== 'sent' && digest.status !== 'rejected' && (
              <div className="flex flex-wrap justify-end gap-2">
                <Button disabled={saving} onClick={() => void updateDigest('reject')} variant="outline"><X className="mr-1.5 size-4" /> Reject</Button>
                <Button disabled={saving} onClick={() => void updateDigest('approve')}><MailCheck className="mr-1.5 size-4" /> Approve & send email</Button>
              </div>
            )}
            {digest.status === 'sent' && <p className="flex items-center gap-2 text-sm text-primary"><Check className="size-4" /> This approved digest was sent.</p>}
          </CardContent>
        </Card>
      )}
    </section>
  )
}
