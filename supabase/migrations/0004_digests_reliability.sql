alter table public.items
    add column if not exists completed_at timestamptz;

create index if not exists items_owner_completed_idx
    on public.items (owner_id, completed_at);

create table if not exists public.digests (
    id uuid primary key default gen_random_uuid(),
    member_id uuid not null references public.members(id) on delete cascade,
    week_start date not null,
    subject text not null,
    body text not null,
    status text not null default 'pending'
        check (status in ('pending', 'approved', 'rejected', 'sent')),
    sent_at timestamptz,
    created_at timestamptz not null default now(),
    unique (member_id, week_start)
);

alter table public.digests enable row level security;

create or replace function public.record_commitment_completion()
returns trigger
language plpgsql
as $$
declare
    completion_slip numeric(8, 2);
    completed_on_time integer;
begin
    if old.status <> 'done'
       and new.status = 'done'
       and new.owner_id is not null
       and new.deadline is not null
       and new.completed_at is not null then
        completion_slip := greatest(
            extract(epoch from (new.completed_at - new.deadline)) / 86400,
            0
        );
        completed_on_time := case when new.completed_at <= new.deadline then 1 else 0 end;

        insert into public.commitment_stats (member_id, total, on_time, avg_slip_days)
        values (new.owner_id, 1, completed_on_time, completion_slip)
        on conflict (member_id) do update
        set total = commitment_stats.total + 1,
            on_time = commitment_stats.on_time + completed_on_time,
            avg_slip_days = (
                commitment_stats.avg_slip_days * commitment_stats.total + completion_slip
            ) / (commitment_stats.total + 1),
            updated_at = now();
    end if;
    return new;
end;
$$;

drop trigger if exists items_record_commitment_completion on public.items;
create trigger items_record_commitment_completion
after update of status on public.items
for each row
execute function public.record_commitment_completion();
