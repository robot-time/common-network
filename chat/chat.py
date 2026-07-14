#!/usr/bin/env python3
"""Chat with the Common Network from your terminal.

Usage:
    common-chat                    # interactive chat
    common-chat "your question"    # one-shot

Every reply is followed by a line showing which node answered and its
routing score — transparency is a feature of the commons, not an
afterthought.

On every run it checks GitHub for a newer version of itself and updates
in place first (pass --no-update to skip).
"""
import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request

DEFAULT_GATEWAY = "https://gateway-production-b820.up.railway.app"
REPO = "robot-time/common-network"
UPDATE_URL = f"https://raw.githubusercontent.com/{REPO}/main/chat/chat.py"

BANNER = r"""
░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓██████████████▓▒░░▒▓██████████████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓██▓▒░
 ░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓██▓▒░
"""


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

    print("Updating to the latest version...")
    try:
        with open(local_path, "wb") as f:
            f.write(remote)
    except OSError as e:
        print(f"warning: couldn't self-update ({e}), continuing with current version", file=sys.stderr)
        return

    os.execv(sys.executable, [sys.executable, local_path] + sys.argv[1:])


def dim(text: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return f"\033[2m{text}\033[0m"


def stream_chat(gateway: str, messages: list[dict], region: str | None) -> tuple[str, str | None, str | None]:
    body = {"model": "auto", "messages": messages, "stream": True}
    headers = {"Content-Type": "application/json"}
    if region:
        headers["X-Common-Region"] = region

    req = urllib.request.Request(
        f"{gateway}/v1/chat/completions", data=json.dumps(body).encode(), headers=headers, method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")
        raise RuntimeError(f"{e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(str(e.reason))

    node = resp.headers.get("X-Common-Node")
    score = resp.headers.get("X-Common-Score")
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
            choices = chunk.get("choices") or [{}]
            delta = choices[0].get("delta", {}).get("content")
            if delta:
                print(delta, end="", flush=True)
                full.append(delta)
    print()
    return "".join(full), node, score


def print_footer(node: str | None, score: str | None) -> None:
    if node:
        label = f"via {node}" + (f" (score {float(score):.3f})" if score else "")
        print(dim(label))
    else:
        print(dim("via unknown node"))


def one_shot(gateway: str, question: str, region: str | None) -> None:
    messages = [{"role": "user", "content": question}]
    try:
        _, node, score = stream_chat(gateway, messages, region)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    print_footer(node, score)


def interactive(gateway: str, region: str | None) -> None:
    print(BANNER)
    print(dim(f"Common Network chat — talking to {gateway}"))
    print(dim("Ctrl+C or Ctrl+D to quit.\n"))
    messages: list[dict] = []
    while True:
        try:
            question = input("you: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if not question:
            continue
        messages.append({"role": "user", "content": question})
        print(flush=True)
        try:
            answer, node, score = stream_chat(gateway, messages, region)
        except RuntimeError as e:
            print(f"error: {e}\n", file=sys.stderr)
            messages.pop()
            continue
        messages.append({"role": "assistant", "content": answer})
        print_footer(node, score)
        print()


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question", nargs="*", help="Ask a one-shot question (omit for interactive chat)")
    parser.add_argument("--gateway", default=os.environ.get("COMMON_GATEWAY_URL", DEFAULT_GATEWAY), help="Gateway base URL (default: the shared Common Network gateway)")
    parser.add_argument("--region", default=None, help="Optional region hint for routing, e.g. au-adelaide")
    parser.add_argument("--no-update", action="store_true", default=bool(os.environ.get("COMMON_NO_UPDATE")), help="Skip the self-update check")
    args = parser.parse_args()

    if not args.no_update:
        self_update()

    gateway = args.gateway.rstrip("/")

    if args.question:
        one_shot(gateway, " ".join(args.question), args.region)
    else:
        interactive(gateway, args.region)


if __name__ == "__main__":
    main()
