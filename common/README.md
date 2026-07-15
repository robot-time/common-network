# common — the COMMON. CLI

The full network client: ask questions, contribute a node, watch demand,
see who's on the commons. Installed by the same one-liner as everything
else — see the [top-level README](../README.md#contributing-a-node-for-friends).

## Commands

```
common                    interactive session (just type a question, or a /command)
common ask "<prompt>"     route one question through the network
common join               put this machine on the commons as a node
common serve <model>      contribute a specific model
common leave              take this machine off the commons
common status             this node: health, position, requests served
common demand             live domain coverage gaps (real data, not a mockup)
common peers              connected nodes and their coverage
common contrib            your contribution ledger
common whoami             your node identity
common config             settings, and exactly what the network retains
common help [verb]        help, per verb
```

Short alias: `cmn` does the same thing as `common`.

## Flags

```
--gateway <url>     talk to a different network
--region <id>       bias routing to a region
--model <id>         pin a specific model (ask: refuses rather than silently
                     rerouting if nothing serves it; join/serve: pick from
                     the catalogue or a raw Ollama tag)
--auto              accept join's recommended model without confirming
--local             ask only — never leaves this machine, talks to your
                     local Ollama directly
--json               machine-readable output, no colour, stable-ish schema
-q / --quiet         answer only, no banners/footers
-v / --verbose       extra routing detail
--no-color           also honours the NO_COLOR env var and non-tty output
--no-update          skip the self-update check (for local development)
```

## What's not built yet

- **`common synth <region>`** — would trigger Soup-of-Experts weight merging
  to fill a coverage gap. Real weight merging doesn't exist yet (explicitly
  out of scope through v0.3). Run `common help synth` for the honest
  explanation rather than a fake simulation.
- **`common map`** — a vector-space position view. Needs a new gateway
  endpoint exposing embeddings (none is public today) plus a 2D projection.
  `common help map` explains what's missing.
- **Local keypair identity** — `whoami` currently tracks a name-based local
  identity file (`~/.common-network/identity.json`, written by `join.py` on
  registration), not a cryptographic keypair. That's a real architecture
  decision, not something to assume into existence — flagged plainly in
  `whoami`'s own output.

## Design

Built to the COMMON. CLI design system: a four-colour palette (charcoal /
paper / dim / blue+red for attention), a fixed glyph vocabulary (`·` `→`
`←` `✓` `⚠` `✗` `#`), lowercase direct copy, and a transparency footer on
every `ask` — node, score, latency, and what was actually retained (an
embedding for demand analytics, not the raw question — the footer says so
honestly rather than claiming blanket "no data retained").
