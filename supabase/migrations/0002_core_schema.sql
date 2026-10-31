create table if not exists public.members (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    role text not null,
    aliases text[] not null default '{}',
    telegram_id text,
    email text,
    created_at timestamptz not null default now()
);

create table if not exists public.meetings (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    meeting_date date not null,
    attendees uuid[] not null default '{}',
    raw_transcript text not null,
    status text not null default 'ingested'
        check (status in ('ingested', 'processing', 'review', 'complete')),
    created_at timestamptz not null default now()
);

create table if not exists public.segments (
    id uuid primary key default gen_random_uuid(),
    meeting_id uuid not null references public.meetings(id) on delete cascade,
    speaker text not null,
    text text not null,
    segment_order integer not null,
    ts timestamptz,
    created_at timestamptz not null default now(),
    unique (meeting_id, segment_order)
);

create table if not exists public.items (
    id uuid primary key default gen_random_uuid(),
    meeting_id uuid not null references public.meetings(id) on delete cascade,
    type text not null check (type in ('decision', 'action', 'intent')),
    text text not null,
    owner_id uuid references public.members(id) on delete set null,
    deadline timestamptz,
    confidence numeric(4, 3) check (confidence between 0 and 1),
    source_quote text not null,
    speaker text,
    status text not null default 'pending'
        check (status in ('pending', 'approved', 'rejected', 'done')),
    tracker_ref text,
    created_at timestamptz not null default now()
);

create table if not exists public.decisions (
    id uuid primary key default gen_random_uuid(),
    topic text not null,
    statement text not null,
    embedding vector,
    meeting_id uuid not null references public.meetings(id) on delete cascade,
    supersedes_id uuid references public.decisions(id) on delete set null,
    status text not null default 'active'
        check (status in ('active', 'superseded', 'rejected')),
    created_at timestamptz not null default now()
);

create table if not exists public.conflicts (
    id uuid primary key default gen_random_uuid(),
    new_item_id uuid not null references public.items(id) on delete cascade,
    old_decision_id uuid not null references public.decisions(id) on delete cascade,
    label text not null check (label in ('contradiction', 'update', 'duplicate')),
    explanation text not null,
    resolution text,
    created_at timestamptz not null default now()
);

create table if not exists public.reminders (
    id uuid primary key default gen_random_uuid(),
    item_id uuid not null references public.items(id) on delete cascade,
    send_at timestamptz not null,
    channel text not null,
    sent boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists public.commitment_stats (
    member_id uuid primary key references public.members(id) on delete cascade,
    total integer not null default 0 check (total >= 0),
    on_time integer not null default 0 check (on_time >= 0 and on_time <= total),
    avg_slip_days numeric(8, 2) not null default 0 check (avg_slip_days >= 0),
    updated_at timestamptz not null default now()
);

create index if not exists meetings_meeting_date_idx
    on public.meetings (meeting_date desc);
create index if not exists segments_meeting_order_idx
    on public.segments (meeting_id, segment_order);
create index if not exists items_meeting_status_idx
    on public.items (meeting_id, status);
create index if not exists items_owner_deadline_idx
    on public.items (owner_id, deadline);
create index if not exists decisions_topic_idx
    on public.decisions (topic);

alter table public.members enable row level security;
alter table public.meetings enable row level security;
alter table public.segments enable row level security;
alter table public.items enable row level security;
alter table public.decisions enable row level security;
alter table public.conflicts enable row level security;
alter table public.reminders enable row level security;
alter table public.commitment_stats enable row level security;

insert into public.members (name, role, aliases)
values
    ('Priya', 'Product Lead', array['Priya']),
    ('Rahul', 'Finance/Ops', array['Rahul']),
    ('Amit', 'Engineering', array['Amit']),
    ('Neha', 'Marketing', array['Neha'])
on conflict (name) do update
set role = excluded.role,
    aliases = excluded.aliases;
