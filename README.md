# Common Network

The AI intelligence layer is being enclosed by a handful of corporations — the
same way English common land was enclosed and privatised. **Common** is the
counter-enclosure: a permissionless network where anyone can contribute a
model as a node, and requests are routed to the best available node by
capability, not by a corporate gatekeeper.

Common speaks the OpenAI API. Point any existing OpenAI SDK client at the
gateway and it works unchanged — except every response tells you exactly
which node served it, and why it was chosen. The commons should be legible.

This is **v0.1**: a single gateway, a Postgres node registry, and a
heuristic router. No DHT, no token, no weight merging — see
[Scope](#scope-v01) below for what's deliberately not here yet.

## How it works

1. An operator registers a node — an OpenAI-compatible endpoint plus a short
   free-text capability profile ("Qwen2.5 7B, strong at code, hosted
   Adelaide, low cost").
2. A client sends a standard `POST /v1/chat/completions` request.
3. The gateway embeds the request, scores every healthy node against its
   capability profile (plus cost and latency), and forwards to the winner.
4. The response comes back unchanged, with `X-Common-Node` and
   `X-Common-Score` headers added so you can see where it went.
5. If the chosen node fails, the gateway falls back to the runner-up once.
6. Every routing decision (request embedding, chosen node, score) is logged
   — the seed of a future demand-analytics layer that can spot underserved
   regions of the request space and suggest where new capability is needed.

## Quickstart

Requirements: Python 3.11+, PostgreSQL with the `pgvector` extension.

```bash
cd gateway
uv venv --python 3.11 .venv          # or: python3.11 -m venv .venv
uv pip install -p .venv/bin/python -r requirements.txt

createdb common_network
psql -d common_network -c "create extension if not exists vector;"
psql -d common_network -f migrations/001_init.sql

cp .env.example .env                 # edit DATABASE_URL / REGISTRY_SECRET / OPENROUTER_API_KEY

.venv/bin/uvicorn app.main:app --reload
```

On startup the gateway seeds nodes from `nodes.seed.yaml` (edit the
`endpoint_url`/`model_name`/`api_key_ref` fields to point at real,
reachable nodes — a local Ollama instance, an OpenRouter-wrapped model,
or any other OpenAI-compatible endpoint).

Send a request:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "Explain recursion"}]}' \
  -i
```

Check the response headers for `X-Common-Node` / `X-Common-Score`, and:

```bash
curl http://localhost:8000/nodes
curl http://localhost:8000/decisions/recent
```

## Registering a node

```bash
curl -X POST http://localhost:8000/nodes \
  -H "X-Common-Secret: $REGISTRY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-qwen-node",
    "operator": "you",
    "endpoint_url": "http://localhost:11434/v1",
    "model_name": "qwen2.5:7b",
    "capability_text": "Qwen2.5 7B, strong at code and structured reasoning, self-hosted, low cost.",
    "region": "local",
    "cost_per_1k": 0
  }'
```

`X-Common-Secret` is a shared secret (`REGISTRY_SECRET` in `.env`) — this is
explicitly **not** production-grade auth, just enough friction for v0.1.

## Deploying (Railway)

1. Create a Railway project with a Postgres plugin, and enable `pgvector`
   (Railway's Postgres image supports it — run
   `CREATE EXTENSION vector;` via the Railway Postgres query console, or via
   `psql $DATABASE_URL -c "create extension vector;"`).
2. Deploy `gateway/` with the included `Dockerfile`.
3. Set `DATABASE_URL`, `REGISTRY_SECRET`, and any `*_API_KEY` env vars
   referenced by your nodes' `api_key_ref`.
4. Run the migration once against the Railway database:
   `DATABASE_URL=<railway-url> python -m app.migrate`
5. The gateway seeds `nodes.seed.yaml` on first boot (`SEED_ON_STARTUP=true`
   by default) — edit that file before deploying, or register nodes via the
   API afterwards.

## Scope (v0.1)

**In scope:** OpenAI-compatible gateway, Postgres node registry, heuristic
similarity/cost/latency routing, health checking, one fallback on failure,
a decisions log, full transparency headers.

**Explicitly out of scope** (see `TODO(v0.2)` comments in code where
relevant): no DHT/peer-to-peer/consensus, no token or incentive mechanism,
no weight merging or Soup of Experts, no Mixture-of-Agents (one request →
one node), no learned router, no vector-native model-to-model
communication, no production-grade auth.

## Licence

AGPL-3.0 (see `LICENSE`). Chosen deliberately: copyleft means anyone
running a modified version of Common as a network service must release
their changes back to the commons — structurally preventing this from
being taken closed, in keeping with the project's anti-enclosure thesis.
