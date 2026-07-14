#!/usr/bin/env python3
"""Join the Common Network as a node operator.

Runs your local Ollama as a contributing node: opens a Cloudflare quick
tunnel to your local Ollama, registers it with the shared gateway, and
keeps running until you press Ctrl+C (at which point it deregisters
cleanly). No account or signup needed for the tunnel.

Requires: Python 3.8+, Ollama (https://ollama.com/download), cloudflared
(https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).

Usage:
    python3 join.py --secret SHARED_SECRET

Joins the default shared Common Network gateway unless --gateway overrides
it. If --secret is omitted you'll be prompted for it. On every run it
checks GitHub for a newer version of itself and updates in place first
(pass --no-update to skip). Everything else has a sensible default — see
--help.
"""
import argparse
import getpass
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434"
TUNNEL_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")

# The default, shared Common Network gateway. Override with --gateway to
# join (or run) a different network entirely.
DEFAULT_GATEWAY = "https://gateway-production-b820.up.railway.app"

REPO = "robot-time/common-network"
UPDATE_URL = f"https://raw.githubusercontent.com/{REPO}/main/join/join.py"


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout: float = 10.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def self_update() -> None:
    """Replace this script with the latest version from GitHub and restart, if different."""
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as resp:
            remote = resp.read()
    except (urllib.error.URLError, socket.timeout):
        return  # offline or GitHub unreachable — carry on with the current version

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

    print("Updating to the latest version...")
    try:
        with open(local_path, "wb") as f:
            f.write(remote)
    except OSError as e:
        print(f"warning: couldn't self-update ({e}), continuing with current version", file=sys.stderr)
        return

    os.execv(sys.executable, [sys.executable, local_path] + sys.argv[1:])


def check_binaries() -> None:
    if shutil.which("ollama") is None:
        die("Ollama not found. Install it from https://ollama.com/download, then run this again.")
    if shutil.which("cloudflared") is None:
        system = platform.system()
        hint = {
            "Darwin": "brew install cloudflared",
            "Linux": "see https://pkg.cloudflare.com/index.html for your distro",
            "Windows": "winget install --id Cloudflare.cloudflared",
        }.get(system, "see https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        die(f"cloudflared not found. Install it with: {hint}")


def ensure_ollama_running() -> None:
    try:
        http_json("GET", f"{OLLAMA_URL}/api/tags", timeout=3)
        return
    except (urllib.error.URLError, socket.timeout):
        pass

    print("Ollama doesn't seem to be running — trying `ollama serve`...")
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(20):
        time.sleep(0.5)
        try:
            http_json("GET", f"{OLLAMA_URL}/api/tags", timeout=3)
            return
        except (urllib.error.URLError, socket.timeout):
            continue
    die("Could not reach Ollama at localhost:11434. Start it manually and try again.")


def ensure_model(model: str) -> None:
    tags = http_json("GET", f"{OLLAMA_URL}/api/tags")
    names = {m["name"] for m in tags.get("models", [])}
    if model in names:
        return
    print(f"Model '{model}' not found locally — pulling it now (this may take a while)...")
    result = subprocess.run(["ollama", "pull", model])
    if result.returncode != 0:
        die(f"failed to pull model '{model}'")


def start_tunnel() -> tuple[subprocess.Popen, str]:
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", OLLAMA_URL],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )

    found_url: list[str] = []

    def read_output():
        for line in proc.stdout:
            match = TUNNEL_URL_PATTERN.search(line)
            if match and not found_url:
                found_url.append(match.group(0))

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if found_url:
            return proc, found_url[0]
        if proc.poll() is not None:
            die("cloudflared exited before a tunnel URL appeared")
        time.sleep(0.5)

    proc.terminate()
    die("timed out waiting for cloudflared to open a tunnel")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gateway", default=os.environ.get("COMMON_GATEWAY_URL", DEFAULT_GATEWAY), help="Gateway base URL (default: the shared Common Network gateway)")
    parser.add_argument("--secret", default=os.environ.get("COMMON_REGISTRY_SECRET"), help="Shared registry secret (will prompt if not given)")
    parser.add_argument("--model", default="llama3.2:3b", help="Ollama model to serve (default: llama3.2:3b)")
    parser.add_argument("--name", default=f"{socket.gethostname()}-{os.environ.get('USER', 'node')}", help="Unique node name")
    parser.add_argument("--operator", default=os.environ.get("USER", "friend"), help="Your name")
    parser.add_argument("--region", default=None, help="Optional region hint, e.g. au-adelaide")
    parser.add_argument("--cost", type=float, default=0, help="Declared cost per 1k tokens (default: 0, it's free)")
    parser.add_argument("--capability", default=None, help="Override the auto-generated capability description")
    parser.add_argument("--no-update", action="store_true", default=bool(os.environ.get("COMMON_NO_UPDATE")), help="Skip the self-update check (useful when hacking on this script locally)")
    args = parser.parse_args()

    if not args.no_update:
        self_update()

    if not args.secret:
        if sys.stdin.isatty():
            args.secret = getpass.getpass("Enter the network secret you were given: ").strip()
        if not args.secret:
            die("--secret is required (or set COMMON_REGISTRY_SECRET)")

    gateway = args.gateway.rstrip("/")

    check_binaries()
    ensure_ollama_running()
    ensure_model(args.model)

    print("Opening a Cloudflare quick tunnel to your local Ollama...")
    tunnel_proc, tunnel_url = start_tunnel()
    print(f"Tunnel live at {tunnel_url}")

    capability_text = args.capability or (
        f"{args.model} running locally via Ollama, contributed by {args.operator}. Free, community-hosted."
    )

    payload = {
        "name": args.name,
        "operator": args.operator,
        "endpoint_url": f"{tunnel_url}/v1",
        "model_name": args.model,
        "capability_text": capability_text,
        "region": args.region,
        "cost_per_1k": args.cost,
    }

    print(f"Registering '{args.name}' with {gateway}...")
    try:
        node = http_json("POST", f"{gateway}/nodes", body=payload, headers={"X-Common-Secret": args.secret})
    except urllib.error.HTTPError as e:
        tunnel_proc.terminate()
        die(f"registration failed: {e.code} {e.read().decode()}")

    node_id = node["id"]
    print(f"You're live! Node id: {node_id}")
    print("Keep this window open to stay in the network. Press Ctrl+C to leave.")

    def cleanup(signum=None, frame=None):
        print("\nLeaving the network...")
        try:
            req = urllib.request.Request(f"{gateway}/nodes/{node_id}", method="DELETE", headers={"X-Common-Secret": args.secret})
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.URLError:
            pass
        tunnel_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    while True:
        if tunnel_proc.poll() is not None:
            print("Tunnel dropped unexpectedly.")
            cleanup()
        time.sleep(2)


if __name__ == "__main__":
    main()
