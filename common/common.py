#!/usr/bin/env python3
"""COMMON. — the commons, belonging to everyone and no one.

Usage:
    common                         open the interactive session
    common ask "<prompt>"          route one question through the network
    common join                    put this machine on the commons as a node
    common serve <model>           contribute a specific model
    common leave                   take this machine off the commons
    common status                  this node: health, position, requests served
    common demand                  live domain coverage gaps
    common peers                   connected nodes and their coverage
    common contrib                 your contribution ledger
    common whoami                  your node identity
    common config                  settings (all local, all editable)
    common help [verb]             help, per verb

"synth" and "map" are recognised but not yet built -- see `common help synth`
/ `common help map`. This CLI checks GitHub for a newer version of itself on
every run and updates in place (pass --no-update to skip).
"""
import argparse
import json
import os
import platform
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# --- Identity ---------------------------------------------------------------
# join.py owns writing/clearing this file (it runs the actual registration).
# This CLI only reads it.
IDENTITY_PATH = Path.home() / ".common-network" / "identity.json"

DEFAULT_GATEWAY = "https://gateway-production-b820.up.railway.app"
REPO = "robot-time/common-network"
UPDATE_URL = f"https://raw.githubusercontent.com/{REPO}/main/common/common.py"
JOIN_SCRIPT_URL = f"https://raw.githubusercontent.com/{REPO}/main/join/join.py"
INSTALL_DIR = Path.home() / ".common-network"

WORDMARK = r""" ██████  ██████  ███    ███ ███    ███  ██████  ███    ██
██      ██    ██ ████  ████ ████  ████ ██    ██ ████   ██
██      ██    ██ ██ ████ ██ ██ ████ ██ ██    ██ ██ ██  ██
██      ██    ██ ██  ██  ██ ██  ██  ██ ██    ██ ██  ██ ██
 ██████  ██████  ██      ██ ██      ██  ██████  ██   ████ ·"""

LOCKUP = "common."  # for tight spaces -- period rendered in blue by print_lockup()


# --- Palette / style ---------------------------------------------------------
# Exactly the four brand colours from the COMMON. design doc. No green, no
# purple, no gradients -- restraint is the point.
PALETTE = {
    "charcoal": (0x28, 0x26, 0x24),
    "paper":    (0xED, 0xE9, 0xE1),
    "dim":      (0x8A, 0x86, 0x81),
    "blue":     (0x92, 0xB4, 0xC8),
    "red":      (0xC8, 0x44, 0x2A),
}


def _enable_windows_ansi() -> None:
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def _color_enabled() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR") and not _ARGS_NO_COLOR[0]


_ARGS_NO_COLOR = [False]  # set from --no-color in main(); NO_COLOR env already covered above


def fg(text: str, color: str, bold: bool = False) -> str:
    if not _color_enabled():
        return text
    r, g, b = PALETTE[color]
    prefix = ("\033[1m" if bold else "") + f"\033[38;2;{r};{g};{b}m"
    return f"{prefix}{text}\033[0m"


def dim(text: str) -> str:
    return fg(text, "dim")


def blue(text: str, bold: bool = False) -> str:
    return fg(text, "blue", bold)


def red(text: str, bold: bool = False) -> str:
    return fg(text, "red", bold)


def paper(text: str, bold: bool = False) -> str:
    return fg(text, "paper", bold)


# Fixed glyph vocabulary -- see design doc 1.5. Consistency over cleverness.
GLYPH_WORK = dim("·")
GLYPH_ROUTE = blue("→")
GLYPH_RECV = dim("←")
GLYPH_DONE = blue("✓")
GLYPH_FORMING = red("⚠")
GLYPH_FAILED = red("✗")


def comment(text: str) -> str:
    return dim(f"  # {text}")


def print_wordmark() -> None:
    print(paper(WORDMARK, bold=True))


def print_banner_box(subtitle: str) -> None:
    lines = WORDMARK.splitlines()
    width = max(len(l) for l in lines) + 4
    top = dim("╭" + "─" * width + "╮")
    bottom = dim("╰" + "─" * width + "╯")
    print(top)
    print(dim("│") + " " * width + dim("│"))
    for line in lines:
        pad = width - len(line) - 2
        print(dim("│") + "  " + paper(line, bold=True) + " " * pad + dim("│"))
    print(dim("│") + " " * width + dim("│"))
    sub_pad = width - len(subtitle) - 2
    print(dim("│") + "  " + dim(subtitle) + " " * max(sub_pad, 0) + dim("│"))
    print(dim("│") + " " * width + dim("│"))
    print(bottom)


# --- HTTP --------------------------------------------------------------------

def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout: float = 20.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# --- Self-update (same pattern as join.py/chat.py) ---------------------------

def self_update() -> None:
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as resp:
            remote = resp.read()
    except (urllib.error.URLError, socket.timeout):
        return
    if not remote.strip():
        return
    local_path = os.path.abspath(__file__)
    try:
        with open(local_path, "rb") as f:
            local = f.read()
    except OSError:
        return
    if remote == local:
        return
    print(dim("updating common to the latest version..."))
    try:
        with open(local_path, "wb") as f:
            f.write(remote)
    except OSError as e:
        print(dim(f"warning: couldn't self-update ({e}), continuing with current version"))
        return
    os.execv(sys.executable, [sys.executable, local_path] + sys.argv[1:])


# --- Identity ------------------------------------------------------------

def read_identity() -> dict | None:
    try:
        return json.loads(IDENTITY_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# --- Commands ------------------------------------------------------------

def cmd_ask(gateway: str, question: str, region: str | None, model: str | None,
            local: bool, as_json: bool, quiet: bool, verbose: bool) -> None:
    if local:
        _ask_local(question, model, as_json, quiet)
        return

    node_override = None
    if model:
        try:
            nodes = http_json("GET", f"{gateway}/nodes")
        except (urllib.error.URLError, socket.timeout) as e:
            print(red(f"✗ can't reach the network."), file=sys.stderr)
            print(comment(f"{e}"), file=sys.stderr)
            sys.exit(1)
        match = next((n for n in nodes if n["healthy"] and n["model_name"] == model), None)
        if not match:
            print(red(f"✗ no healthy node is currently serving '{model}'."), file=sys.stderr)
            print(comment("refusing rather than silently rerouting to a different model."), file=sys.stderr)
            print(dim("  → see what's available:   common peers"), file=sys.stderr)
            sys.exit(1)
        node_override = match["name"]

    if not quiet:
        print(dim("plotting request into vector space"))

    body = {"model": "auto", "messages": [{"role": "user", "content": question}], "stream": True}
    headers = {"Content-Type": "application/json"}
    if region:
        headers["X-Common-Region"] = region
    if node_override:
        headers["X-Common-Node"] = node_override

    req = urllib.request.Request(f"{gateway}/v1/chat/completions", data=json.dumps(body).encode(), headers=headers, method="POST")
    start = time.monotonic()
    try:
        resp = urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")
        print(red("✗ the network couldn't answer that."), file=sys.stderr)
        print(comment(f"{e.code}: {detail}"), file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(red("✗ can't reach the network."), file=sys.stderr)
        print(comment("you're offline, or no peers are up in your region."), file=sys.stderr)
        print(dim(f"  → retry:            common ask \"{question}\" --retry"), file=sys.stderr)
        print(dim("  → run local only:   common ask \"...\" --local"), file=sys.stderr)
        sys.exit(1)

    node_name = resp.headers.get("X-Common-Node")
    score = resp.headers.get("X-Common-Score")

    if not quiet and not as_json:
        score_str = f"   ·   {float(score):.2f} match" if score not in (None, "forced") else ""
        weak = score not in (None, "forced") and float(score) < 0.5
        marker = f"  {GLYPH_FORMING}" if weak else ""
        print(f"{GLYPH_ROUTE} nearest node   {blue(node_name or 'unknown')}{score_str}{marker}")
        if weak:
            print(comment("nothing on the commons serves this well yet."))
        print(GLYPH_RECV + dim(" streaming"))
        print()

    full = []
    with resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                if as_json:
                    full.append(delta)
                else:
                    print(paper(delta), end="", flush=True)
                    full.append(delta)
    if not as_json:
        print()

    latency_ms = int((time.monotonic() - start) * 1000)

    if as_json:
        print(json.dumps({
            "answer": "".join(full), "node": node_name, "score": score,
            "latency_ms": latency_ms,
        }))
        return

    if not quiet:
        print()
        print(dim("─" * 63))
        model_bit = f" ({model})" if model else ""
        print(dim(f"served by   {node_name}{model_bit}"))
        retention = "embedding retained for demand analytics · no raw text stored"
        print(dim(f"routed in   {latency_ms}ms   ·   {retention}   ·   no one owns this"))
        if verbose:
            print(dim(f"  score: {score}"))


def _ask_local(question: str, model: str | None, as_json: bool, quiet: bool) -> None:
    ollama_url = "http://localhost:11434"
    try:
        tags = http_json("GET", f"{ollama_url}/api/tags", timeout=5)
    except (urllib.error.URLError, socket.timeout):
        print(red("✗ can't reach Ollama on this machine."), file=sys.stderr)
        print(comment("is it installed and running? https://ollama.com/download"), file=sys.stderr)
        sys.exit(1)
    names = [m["name"] for m in tags.get("models", [])]
    if not names:
        print(red("✗ no local models available. pull one first: ollama pull llama3.2:3b"), file=sys.stderr)
        sys.exit(1)
    chosen = model or names[0]
    if not quiet:
        print(dim(f"asking {chosen} locally (never leaves this machine)"))
    body = {"model": chosen, "messages": [{"role": "user", "content": question}], "stream": False}
    try:
        result = http_json("POST", f"{ollama_url}/v1/chat/completions", body=body, timeout=180)
    except (urllib.error.URLError, socket.timeout) as e:
        print(red(f"✗ local request failed: {e}"), file=sys.stderr)
        sys.exit(1)
    answer = result["choices"][0]["message"]["content"]
    if as_json:
        print(json.dumps({"answer": answer, "node": "local", "model": chosen}))
    else:
        print(paper(answer))
        print()
        print(dim("─" * 63))
        print(dim(f"served by   local ({chosen})   ·   never left this machine"))


def cmd_peers(gateway: str, as_json: bool) -> None:
    nodes = http_json("GET", f"{gateway}/nodes")
    if as_json:
        print(json.dumps(nodes))
        return
    if not nodes:
        print(dim("no peers reachable yet."))
        print(dim("  → common join"))
        return
    healthy = sum(1 for n in nodes if n["healthy"])
    print(dim(f"{len(nodes)} peer(s)   ·   {healthy} healthy\n"))
    for n in nodes:
        badge = GLYPH_DONE if n["healthy"] else GLYPH_FAILED
        tags = ", ".join(n.get("domain_tags") or []) or "untagged"
        print(f"{badge}  {paper(n['name'])}")
        print(dim(f"   {n['model_name']}   ·   {tags}   ·   {n['avg_latency_ms']}ms avg"))


def cmd_demand(gateway: str, as_json: bool) -> None:
    nodes = http_json("GET", f"{gateway}/nodes")
    decisions = http_json("GET", f"{gateway}/decisions/recent?limit=200")

    demand: dict[str, int] = {}
    for d in decisions:
        if d.get("matched_domain"):
            demand[d["matched_domain"]] = demand.get(d["matched_domain"], 0) + 1
    coverage: dict[str, int] = {}
    for n in nodes:
        if n["healthy"] and n.get("domain_tags"):
            for t in n["domain_tags"]:
                coverage[t] = coverage.get(t, 0) + 1

    domains = sorted(set(demand) | set(coverage))
    if as_json:
        print(json.dumps({d: {"demand": demand.get(d, 0), "coverage": coverage.get(d, 0)} for d in domains}))
        return

    if not domains:
        print(dim("no domain-matched requests yet. the network hasn't seen enough traffic to show gaps."))
        return

    print(dim("domain coverage   ·   live\n"))
    max_val = max([1] + list(demand.values()) + list(coverage.values()))
    for d in domains:
        dv, cv = demand.get(d, 0), coverage.get(d, 0)
        bar_len = 20
        filled = int((dv / max_val) * bar_len) if max_val else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        status = f"{GLYPH_DONE} ok" if cv > 0 else f"{GLYPH_FORMING} forming"
        print(f"  {d:28s} {paper(bar)}   {status}")
        print(dim(f"    {dv} request(s)   ·   {cv} node(s) serving it\n"))

    forming = [d for d in domains if coverage.get(d, 0) == 0 and demand.get(d, 0) > 0]
    if forming:
        print(f"a cloud is forming in {red(forming[0])}.")
        print(comment("no node serves it well yet. join a machine into this gap:"))
        print(dim(f"  → common join --auto"))


def cmd_status(gateway: str, as_json: bool) -> None:
    identity = read_identity()
    if not identity:
        if as_json:
            print(json.dumps({"joined": False}))
            return
        print(dim("not currently on the commons."))
        print(dim("  → common join"))
        return

    try:
        nodes = http_json("GET", f"{gateway}/nodes")
    except (urllib.error.URLError, socket.timeout):
        nodes = []
    node = next((n for n in nodes if n["id"] == identity.get("node_id")), None)

    if as_json:
        print(json.dumps({"joined": True, "identity": identity, "node": node}))
        return

    since = time.time() - identity.get("joined_at", time.time())
    days = since / 86400
    print(f"node  {paper(identity['name'], bold=True)}   ·   on the commons {days:.1f} days\n")
    if node:
        badge = f"{GLYPH_DONE} healthy" if node["healthy"] else f"{GLYPH_FAILED} unhealthy"
        print(dim(f"status          {badge}"))
        print(dim(f"model           {node['model_name']}"))
        print(dim(f"avg latency     {node['avg_latency_ms']}ms"))
        print(dim(f"domain tags     {', '.join(node.get('domain_tags') or []) or 'untagged'}"))
    else:
        print(red("this node is no longer registered (deregistered or replaced)."))


def cmd_whoami(as_json: bool) -> None:
    identity = read_identity()
    if not identity:
        if as_json:
            print(json.dumps(None))
            return
        print(dim("no identity yet. join the network first:"))
        print(dim("  → common join"))
        return
    if as_json:
        print(json.dumps(identity))
        return
    print(f"node      {paper(identity['name'], bold=True)}")
    print(dim(f"gateway   {identity['gateway']}"))
    print(dim(f"node id   {identity['node_id']}"))
    print()
    print(comment("this is a name-based identity, not a cryptographic keypair yet."))
    print(comment("no account, nothing to log into -- see TODO(v0.4) in the design doc."))


def cmd_contrib(gateway: str, as_json: bool) -> None:
    identity = read_identity()
    if not identity:
        print(dim("not currently on the commons."))
        print(dim("  → common join"))
        return
    decisions = http_json("GET", f"{gateway}/decisions/recent?limit=500")
    served = [d for d in decisions if d.get("chosen_node") == identity.get("node_id")]
    ok = sum(1 for d in served if d.get("ok"))

    if as_json:
        print(json.dumps({"requests_served": len(served), "ok": ok}))
        return

    since = time.time() - identity.get("joined_at", time.time())
    days = max(since / 86400, 0.01)
    print(f"node  {paper(identity['name'], bold=True)}   ·   on the commons {days:.1f} days\n")
    print(dim(f"requests served (last 500 logged)   {len(served)}"))
    print(dim(f"successful                          {ok}/{len(served)}" if served else dim("successful                          —")))
    print()
    print(comment(f"{len(served)} questions got answered because you left your gate open."))


def cmd_config(as_json: bool, args: argparse.Namespace) -> None:
    cfg = {
        "gateway": args.gateway,
        "region": args.region or None,
        "no_color": bool(os.environ.get("NO_COLOR")),
    }
    if as_json:
        print(json.dumps(cfg))
        return
    print(dim("gateway   ") + paper(cfg["gateway"]))
    print(dim("region    ") + paper(str(cfg["region"] or "(none set)")))
    print()
    print(dim("what the network retains, in words:"))
    print(comment("every request's embedding + which node answered + latency, for"))
    print(comment("demand analytics (see `common demand`). no raw question text,"))
    print(comment("no account, no telemetry beyond that. nothing sent home beyond"))
    print(comment("what's needed to route your request and log that decision."))


def cmd_leave(gateway: str) -> None:
    identity = read_identity()
    join_py = INSTALL_DIR / "join.py"
    if join_py.exists():
        import subprocess
        print(dim("checking for a running background node service..."))
        result = subprocess.run([sys.executable, str(join_py), "--no-update", "--remove-permanent"], capture_output=True, text=True)
        if result.returncode == 0 and "Removed" in result.stdout:
            print(f"{GLYPH_DONE} done. you're off the network.")
            print(comment("nothing was kept. your keypair stays on your machine."))
            return
    if identity:
        print(dim("no background service found, and no foreground session this command can reach."))
        print(comment(f"if `common join` is running in another terminal, press Ctrl+C there to leave."))
    else:
        print(dim("not currently on the commons."))


def cmd_join_or_serve(verb: str, gateway: str, args: argparse.Namespace, extra_model: str | None = None) -> None:
    join_py = INSTALL_DIR / "join.py"
    # Always fetch the current version before delegating -- a stale local
    # copy's own self-update runs *after* argparse, so a new flag this CLI
    # relies on (e.g. --auto) would crash before join.py ever got the chance
    # to update itself. Found exactly this bug in testing.
    try:
        with urllib.request.urlopen(JOIN_SCRIPT_URL, timeout=10) as resp:
            remote = resp.read()
        join_py.parent.mkdir(parents=True, exist_ok=True)
        join_py.write_bytes(remote)
    except (urllib.error.URLError, socket.timeout) as e:
        if not join_py.exists():
            print(red(f"✗ couldn't fetch the join script: {e}"), file=sys.stderr)
            sys.exit(1)
        # Offline but we already have a copy -- use it as-is.

    if verb == "serve":
        print(dim(f"putting {extra_model} out to graze on the commons.\n"))

    argv = [sys.executable, str(join_py), "--gateway", gateway]
    if extra_model:
        argv += ["--model", extra_model, "--auto"]
    elif args.auto:
        argv += ["--auto"]
    if args.model and not extra_model:
        argv += ["--model", args.model]
    if args.region:
        argv += ["--region", args.region]

    os.execv(sys.executable, argv)


def cmd_help(verb: str | None) -> None:
    if verb == "synth":
        print(dim("common synth <region>"))
        print()
        print(red("not built yet."))
        print(comment("this requires real Soup-of-Experts weight merging across"))
        print(comment("nearby specialists -- explicitly out of scope until that"))
        print(comment("architecture exists (see the v0.2/v0.3 build briefs). when"))
        print(comment("it ships, it will combine real weights and validate against"))
        print(comment("held-out demand -- not simulate the result."))
        return
    if verb == "map":
        print(dim("common map"))
        print()
        print(red("not built yet."))
        print(comment("needs a new gateway endpoint exposing node/request embeddings"))
        print(comment("(none is public today) plus a 2D projection. planned, not"))
        print(comment("guessed at -- see TODO(v0.4)."))
        return
    print(__doc__)


def build_repl_help() -> str:
    return dim(
        "/ask (implicit: just type)  /join  /serve  /leave  /status\n"
        "/demand  /peers  /contrib  /whoami  /config  /model  /local  /help  /exit"
    )


def interactive_session(gateway: str, args: argparse.Namespace) -> None:
    print_banner_box("the commons. belonging to everyone and no one.")
    print()
    print(dim("you're in the interactive session. type a question, or a /command."))
    print(build_repl_help())
    print()
    session_model: str | None = args.model
    session_local = args.local
    while True:
        try:
            line = input(blue("› ", bold=True)).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if not line:
            continue
        if line in ("/exit", "/quit"):
            return
        if line == "/help":
            print(build_repl_help())
            continue
        if line == "/status":
            cmd_status(gateway, False)
            continue
        if line == "/peers":
            cmd_peers(gateway, False)
            continue
        if line == "/demand":
            cmd_demand(gateway, False)
            continue
        if line == "/contrib":
            cmd_contrib(gateway, False)
            continue
        if line == "/whoami":
            cmd_whoami(False)
            continue
        if line == "/config":
            cmd_config(False, args)
            continue
        if line == "/local":
            session_local = not session_local
            print(dim(f"local-only: {'on' if session_local else 'off'}"))
            continue
        if line.startswith("/model"):
            parts = line.split(maxsplit=1)
            session_model = parts[1] if len(parts) > 1 else None
            print(dim(f"model pinned to: {session_model or '(auto)'}"))
            continue
        if line in ("/join", "/serve", "/leave"):
            print(dim(f"run this from a real terminal instead: common {line[1:]}"))
            print(comment("join/leave manage a long-running process and a background"))
            print(comment("service -- not something to do mid-session here."))
            continue
        if line.startswith("/"):
            print(dim(f"unknown command: {line}"))
            continue
        cmd_ask(gateway, line, args.region, session_model, session_local, False, False, args.verbose)
        print()


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    _enable_windows_ansi()

    parser = argparse.ArgumentParser(prog="common", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)
    parser.add_argument("verb", nargs="?", default=None)
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    parser.add_argument("--gateway", default=os.environ.get("COMMON_GATEWAY_URL", DEFAULT_GATEWAY))
    parser.add_argument("--region", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--no-update", action="store_true", default=bool(os.environ.get("COMMON_NO_UPDATE")))
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()

    _ARGS_NO_COLOR[0] = args.no_color

    if not args.no_update:
        self_update()

    if args.version:
        print_wordmark()
        return

    if args.help or args.verb == "help":
        cmd_help(args.rest[0] if args.rest else None)
        return

    gateway = args.gateway.rstrip("/")

    if args.verb is None:
        interactive_session(gateway, args)
        return

    if args.verb == "ask":
        question = " ".join(args.rest)
        if not question:
            print(red("✗ ask needs a question: common ask \"...\""), file=sys.stderr)
            sys.exit(1)
        cmd_ask(gateway, question, args.region, args.model, args.local, args.json, args.quiet, args.verbose)
    elif args.verb == "peers":
        cmd_peers(gateway, args.json)
    elif args.verb == "demand":
        cmd_demand(gateway, args.json)
    elif args.verb == "status":
        cmd_status(gateway, args.json)
    elif args.verb == "whoami":
        cmd_whoami(args.json)
    elif args.verb == "contrib":
        cmd_contrib(gateway, args.json)
    elif args.verb == "config":
        cmd_config(args.json, args)
    elif args.verb == "join":
        cmd_join_or_serve("join", gateway, args)
    elif args.verb == "serve":
        model = args.rest[0] if args.rest else args.model
        if not model:
            print(red("✗ serve needs a model: common serve <model>"), file=sys.stderr)
            sys.exit(1)
        cmd_join_or_serve("serve", gateway, args, extra_model=model)
    elif args.verb == "leave":
        cmd_leave(gateway)
    elif args.verb in ("synth", "map"):
        cmd_help(args.verb)
    else:
        print(red(f"✗ unknown command: {args.verb}"), file=sys.stderr)
        print(dim("  → common help"), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
