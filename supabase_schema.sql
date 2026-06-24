create table if not exists public.readings (
    id bigserial primary key,
    device_id text not null,
    sequence bigint not null,
    device_timestamp timestamptz not null,
    vin double precision not null check (vin >= 0),
    vout double precision not null check (vout >= 0),
    iin double precision not null check (iin >= 0),
    iout double precision not null check (iout >= 0),
    load double precision not null check (load >= 0 and load <= 100),
    battery double precision not null check (battery >= 0),
    raw_payload jsonb not null,
    created_at timestamptz not null default now(),
    constraint readings_device_sequence_unique unique (device_id, sequence)
);

create index if not exists idx_readings_created_at
    on public.readings (created_at desc);

create index if not exists idx_readings_device_sequence
    on public.readings (device_id, sequence desc);

alter table public.readings enable row level security;

drop policy if exists "service role can manage readings" on public.readings;
create policy "service role can manage readings"
    on public.readings
    for all
    using (auth.role() = 'service_role')
    with check (auth.role() = 'service_role');
