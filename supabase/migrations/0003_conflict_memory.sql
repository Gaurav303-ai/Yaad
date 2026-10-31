alter table public.items
    add column if not exists topic text not null default 'General';

alter table public.decisions
    add column if not exists meeting_date date;

update public.decisions as decision
set meeting_date = meeting.meeting_date
from public.meetings as meeting
where decision.meeting_id = meeting.id
  and decision.meeting_date is null;

alter table public.decisions
    alter column meeting_date set not null,
    add column if not exists deadline timestamptz,
    add column if not exists source_quote text not null default '',
    add column if not exists speaker text not null default 'Unknown';

create index if not exists decisions_date_status_idx
    on public.decisions (meeting_date desc, status);

create or replace function public.match_decisions(
    query_embedding vector,
    before_date date,
    match_count integer default 10,
    exclude_meeting_id uuid default null
)
returns table (
    id uuid,
    topic text,
    statement text,
    meeting_id uuid,
    meeting_date date,
    deadline timestamptz,
    source_quote text,
    speaker text,
    similarity double precision
)
language sql
stable
as $$
    select
        decision.id,
        decision.topic,
        decision.statement,
        decision.meeting_id,
        decision.meeting_date,
        decision.deadline,
        decision.source_quote,
        decision.speaker,
        1 - (decision.embedding <=> query_embedding) as similarity
    from public.decisions as decision
    where decision.embedding is not null
      and decision.status = 'active'
      and decision.meeting_date < before_date
      and (exclude_meeting_id is null or decision.meeting_id <> exclude_meeting_id)
    order by decision.embedding <=> query_embedding
    limit greatest(match_count, 0);
$$;
