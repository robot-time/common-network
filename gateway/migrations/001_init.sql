create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists nodes (
  id                uuid primary key default gen_random_uuid(),
  name              text not null unique,
  operator          text,
  endpoint_url      text not null,
  model_name        text not null,
  api_key_ref       text,
  capability_text   text not null,
  capability_embed  vector(384),
  region            text,
  cost_per_1k       numeric default 0,
  avg_latency_ms    integer default 0,
  healthy           boolean default true,
  last_heartbeat    timestamptz,
  created_at        timestamptz default now()
);

create table if not exists decisions (
  id                uuid primary key default gen_random_uuid(),
  request_embed     vector(384),
  chosen_node       uuid references nodes(id),
  score             numeric,
  runner_up         uuid references nodes(id),
  latency_ms        integer,
  ok                boolean,
  created_at        timestamptz default now()
);

create index if not exists idx_decisions_created_at on decisions (created_at desc);
