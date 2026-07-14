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
import platform
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


def _enable_windows_ansi() -> None:
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


_ANSI_CODES = {
    "reset": "0", "bold": "1", "dim": "2",
    "red": "31", "green": "32", "yellow": "33",
    "blue": "34", "magenta": "35", "cyan": "36", "white": "37",
}


def _color_enabled() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def style(text: str, *codes: str) -> str:
    if not _color_enabled():
        return text
    prefix = "".join(f"\033[{_ANSI_CODES[c]}m" for c in codes)
    return f"{prefix}{text}\033[{_ANSI_CODES['reset']}m"


def dim(text: str) -> str:
    return style(text, "dim")


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

    print(style("Updating to the latest version...", "yellow"))
    try:
        with open(local_path, "wb") as f:
            f.write(remote)
    except OSError as e:
        print(style(f"warning: couldn't self-update ({e}), continuing with current version", "yellow"), file=sys.stderr)
        return

    os.execv(sys.executable, [sys.executable, local_path] + sys.argv[1:])


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
    dot = style("●", "green")
    if node:
        label = f"via {node}" + (f" (score {float(score):.3f})" if score else "")
        print(f"{dot} {dim(label)}")
    else:
        print(f"{dot} {dim('via unknown node')}")


def one_shot(gateway: str, question: str, region: str | None) -> None:
    messages = [{"role": "user", "content": question}]
    try:
        _, node, score = stream_chat(gateway, messages, region)
    except RuntimeError as e:
        print(style(f"error: {e}", "red"), file=sys.stderr)
        sys.exit(1)
    print_footer(node, score)


def interactive(gateway: str, region: str | None) -> None:
    print(style(BANNER, "white", "bold"))
    print(dim(f"Common Network chat — talking to {gateway}"))
    print(dim("Ctrl+C or Ctrl+D to quit.\n"))
    messages: list[dict] = []
    while True:
        try:
            question = input(style("you: ", "cyan", "bold")).strip()
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
            print(style(f"error: {e}\n", "red"), file=sys.stderr)
            messages.pop()
            continue
        messages.append({"role": "assistant", "content": answer})
        print_footer(node, score)
        print()


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    _enable_windows_ansi()
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
