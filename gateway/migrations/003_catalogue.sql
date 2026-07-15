-- Specialist catalogue: a curated, versioned registry of known specialist
-- models. Node onboarding assigns from this catalogue based on hardware fit
-- and demand, instead of operators hand-declaring arbitrary generic models.

create table if not exists catalogue_models (
  id                text primary key,          -- e.g. 'qwen2.5-coder-7b'
  display_name      text not null,
  source            text not null,             -- 'ollama:qwen2.5-coder:7b' or 'api:cgla-legal'
  domain_tags       text[] not null,           -- e.g. {code, python}
  capability_text   text not null,             -- profile used for routing embedding
  params_b          numeric,                   -- parameter count in billions
  min_ram_gb        integer not null,
  min_vram_gb       integer default 0,         -- 0 = CPU-runnable
  needs_gpu         boolean default false,
  verified_in_lane  boolean default false,     -- did the v0.2 benchmark show it beats frontier
  lane_benchmark    jsonb,                      -- {benchmark, score, vs_frontier, date}
  licence           text,
  added_at          timestamptz default now()
);

-- Nodes now carry structured domain tags (assigned from the catalogue entry
-- they provisioned) in addition to the free-text capability_text they've
-- always had, plus a record of which catalogue entry they're running.
alter table nodes add column if not exists domain_tags text[];
alter table nodes add column if not exists catalogue_id text references catalogue_models(id);

-- Matched domain per decision, so routing feeds the demand signal that
-- assignment reads back out. Null when no domain tag matched confidently.
alter table decisions add column if not exists matched_domain text;
