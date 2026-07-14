# Join the Common Network

Contribute your computer's spare capacity as a node. You don't need to clone
the whole repo or install any Python packages beyond the standard library —
just this one script.

## Prerequisites

1. **Ollama** — https://ollama.com/download (install and open it once so it's running)
2. **cloudflared** — this opens a free, no-signup tunnel so the shared gateway can reach your machine:
   - Mac: `brew install cloudflared`
   - Windows: `winget install --id Cloudflare.cloudflared`
   - Linux: see https://pkg.cloudflare.com/index.html for your distro
3. **Python 3.8+** (already installed on most Macs and Linux machines)

## Run it

Get the gateway URL and shared secret from whoever's running the network,
then:

```bash
python3 join.py --gateway https://your-gateway.example --secret THE_SHARED_SECRET
```

By default this serves `llama3.2:3b` (small, fast, works on most laptops).
Pass `--model` to use a different one you have pulled in Ollama — keep it to
7B or smaller unless your machine can comfortably handle more:

```bash
python3 join.py --gateway https://your-gateway.example --secret THE_SHARED_SECRET --model qwen2.5:7b
```

The script will:
1. Make sure Ollama is running and the model is pulled (pulling it if not).
2. Open a Cloudflare quick tunnel to your local Ollama.
3. Register your node with the shared gateway.
4. Keep running so your node stays online.

Press `Ctrl+C` to leave the network — it deregisters your node cleanly.

## Notes

- Your node only serves the model you specify. It's stateless — the gateway
  never sees your files, just chat requests.
- The tunnel URL changes every time you run the script, which is fine — the
  gateway is told your endpoint at registration time.
- If your laptop goes to sleep or loses internet, the gateway's health check
  will just mark your node unhealthy and stop routing to it until you're
  back.
- **The free Cloudflare quick tunnel has a hard ~100 second response
  ceiling** — if your model hasn't replied by then, the request fails with
  a Cloudflare 524 and the gateway falls back to another node. Stick to
  small, fast, non-reasoning models (the default `llama3.2:3b` is fine).
  "Thinking"/extended-reasoning models (e.g. some Qwen3 variants) can burn
  well past 100 seconds on modest hardware before producing any visible
  output — avoid those unless you've confirmed they respond quickly on
  your machine.
