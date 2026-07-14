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
    python3 join.py --secret SHARED_SECRET --permanent   # run as a background service
    python3 join.py --remove-permanent                   # undo the above

Joins the default shared Common Network gateway unless --gateway overrides
it. If --secret is omitted you'll be prompted for it. It checks GitHub for
a newer version of itself on startup, and again every 30 minutes while
running — if one is found it deregisters, stops the tunnel, updates, and
restarts cleanly (pass --no-update to disable both checks).

--permanent installs this as a real background service (LaunchAgent on
macOS, systemd --user on Linux, a Scheduled Task on Windows) that starts
at login and restarts automatically if it crashes — for servers or
computers you don't want to babysit with an open terminal. Everything
else has a sensible default — see --help.
"""
import argparse
import getpass
import json
import os
import platform
import plistlib
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BANNER = r"""
 ░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓██████████████▓▒░░▒▓██████████████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░         
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░        
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓██▓▒░ 
 ░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓██▓▒░ 
                                                                                                     
                                                                                                     
"""

OLLAMA_URL = "http://localhost:11434"
TUNNEL_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")

# The default, shared Common Network gateway. Override with --gateway to
# join (or run) a different network entirely.
DEFAULT_GATEWAY = "https://gateway-production-b820.up.railway.app"

REPO = "robot-time/common-network"
UPDATE_URL = f"https://raw.githubusercontent.com/{REPO}/main/join/join.py"


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


def die(msg: str, code: int = 1) -> None:
    print(style(f"error: {msg}", "red"), file=sys.stderr)
    sys.exit(code)


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout: float = 10.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


UPDATE_CHECK_INTERVAL_SECONDS = 1800  # re-check every 30 min while a node sits running


def fetch_update() -> bytes | None:
    """Return the latest join.py source from GitHub if it differs from the local copy, else None."""
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as resp:
            remote = resp.read()
    except (urllib.error.URLError, socket.timeout):
        return None  # offline or GitHub unreachable — carry on with the current version

    if not remote.strip():
        return None

    local_path = os.path.abspath(__file__)
    try:
        with open(local_path, "rb") as f:
            local = f.read()
    except OSError:
        return None

    return remote if remote != local else None


def apply_update_and_restart(remote: bytes) -> None:
    """Overwrite this script with `remote` and re-exec. Never returns on success."""
    local_path = os.path.abspath(__file__)
    try:
        with open(local_path, "wb") as f:
            f.write(remote)
    except OSError as e:
        print(style(f"warning: couldn't self-update ({e}), continuing with current version", "yellow"), file=sys.stderr)
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

    print(style("Ollama doesn't seem to be running — trying `ollama serve`...", "yellow"))
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
    print(style(f"Model '{model}' not found locally — pulling it now (this may take a while)...", "cyan"))
    result = subprocess.run(["ollama", "pull", model])
    if result.returncode != 0:
        die(f"failed to pull model '{model}'")


def start_tunnel() -> tuple[subprocess.Popen, str]:
    # Cloudflare's quick tunnel forwards the public tunnel hostname as the
    # Host header by default. Some Ollama versions reject any request whose
    # Host isn't localhost/127.0.0.1 (anti-DNS-rebinding protection) and
    # respond 403 -- force the header cloudflared sends to the origin so
    # that check always passes regardless of the Ollama version.
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", OLLAMA_URL, "--http-host-header", "localhost:11434"],
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


LAUNCHD_LABEL = "network.common.join"
SYSTEMD_UNIT = "common-join.service"
SCHTASKS_NAME = "CommonNetworkJoin"


def _service_argv(args: argparse.Namespace) -> list[str]:
    argv = [
        sys.executable, os.path.abspath(__file__),
        "--gateway", args.gateway,
        "--secret", args.secret,
        "--model", args.model,
        "--name", args.name,
        "--operator", args.operator,
        "--cost", str(args.cost),
    ]
    if args.region:
        argv += ["--region", args.region]
    if args.capability:
        argv += ["--capability", args.capability]
    if args.no_update:
        argv += ["--no-update"]
    return argv


def _macos_plist_path() -> Path:
    d = Path.home() / "Library" / "LaunchAgents"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{LAUNCHD_LABEL}.plist"


def install_macos_service(argv: list[str]) -> None:
    plist_path = _macos_plist_path()
    log_path = Path.home() / ".common-network" / "join.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # launchd's default PATH doesn't include /usr/local/bin or /opt/homebrew/bin,
    # so ollama/cloudflared (installed there) won't resolve unless we carry over
    # the PATH from the shell that ran --permanent.
    with open(plist_path, "wb") as f:
        plistlib.dump({
            "Label": LAUNCHD_LABEL,
            "ProgramArguments": argv,
            "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")},
            "RunAtLoad": True,
            "KeepAlive": True,
            "StandardOutPath": str(log_path),
            "StandardErrorPath": str(log_path),
        }, f)

    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LAUNCHD_LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)], check=True)
    print(style("Installed as a background service (LaunchAgent) — it will start at login and restart if it crashes.", "green", "bold"))
    print(dim(f"Logs: {log_path}"))
    print(dim(f"To stop: python3 {os.path.abspath(__file__)} --remove-permanent --no-update"))


def remove_macos_service() -> None:
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LAUNCHD_LABEL}"], capture_output=True)
    plist_path = _macos_plist_path()
    if plist_path.exists():
        plist_path.unlink()
    print(style("Removed the background service.", "green"))


def _systemd_unit_path() -> Path:
    d = Path.home() / ".config" / "systemd" / "user"
    d.mkdir(parents=True, exist_ok=True)
    return d / SYSTEMD_UNIT


def install_linux_service(argv: list[str]) -> None:
    unit_path = _systemd_unit_path()
    exec_start = " ".join(shlex.quote(a) for a in argv)
    path_env = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    unit_path.write_text(f"""[Unit]
Description=Common Network node
After=network-online.target

[Service]
Environment=PATH={path_env}
ExecStart={exec_start}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
""")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", SYSTEMD_UNIT], check=True)
    print(style("Installed as a background service (systemd --user) — it will start at login and restart if it crashes.", "green", "bold"))
    print(dim(f"Logs: journalctl --user -u {SYSTEMD_UNIT} -f"))
    print(dim("If this is a server, also run `loginctl enable-linger $USER` so it keeps running after you log out."))
    print(dim(f"To stop: python3 {os.path.abspath(__file__)} --remove-permanent --no-update"))


def remove_linux_service() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT], capture_output=True)
    unit_path = _systemd_unit_path()
    if unit_path.exists():
        unit_path.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    print(style("Removed the background service.", "green"))


def install_windows_service(argv: list[str]) -> None:
    cmd_str = " ".join(f'"{a}"' if " " in a else a for a in argv)
    subprocess.run([
        "schtasks", "/create", "/f", "/sc", "onlogon", "/rl", "highest",
        "/tn", SCHTASKS_NAME, "/tr", cmd_str,
    ], check=True)
    subprocess.run(["schtasks", "/run", "/tn", SCHTASKS_NAME], check=True)
    print(style("Installed as a scheduled task — it will start at login. (Windows Task Scheduler doesn't auto-restart on crash like launchd/systemd do.)", "green", "bold"))
    print(dim(f"To stop: python3 {os.path.abspath(__file__)} --remove-permanent --no-update"))


def remove_windows_service() -> None:
    subprocess.run(["schtasks", "/end", "/tn", SCHTASKS_NAME], capture_output=True)
    subprocess.run(["schtasks", "/delete", "/f", "/tn", SCHTASKS_NAME], capture_output=True)
    print(style("Removed the scheduled task.", "green"))


def install_permanent(args: argparse.Namespace) -> None:
    argv = _service_argv(args)
    system = platform.system()
    if system == "Darwin":
        install_macos_service(argv)
    elif system == "Linux":
        install_linux_service(argv)
    elif system == "Windows":
        install_windows_service(argv)
    else:
        die(f"--permanent isn't supported on {system}")


def remove_permanent() -> None:
    system = platform.system()
    if system == "Darwin":
        remove_macos_service()
    elif system == "Linux":
        remove_linux_service()
    elif system == "Windows":
        remove_windows_service()
    else:
        die(f"--permanent isn't supported on {system}")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    _enable_windows_ansi()
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
    parser.add_argument("--permanent", action="store_true", help="Install as a background service that starts at login/boot and restarts if it crashes, then exit")
    parser.add_argument("--remove-permanent", action="store_true", help="Remove the background service installed by --permanent, then exit")
    args = parser.parse_args()

    if not args.no_update:
        remote = fetch_update()
        if remote:
            print(style("Updating to the latest version...", "yellow"))
            apply_update_and_restart(remote)

    print(style(BANNER, "white", "bold"))

    if args.remove_permanent:
        remove_permanent()
        return

    if not args.secret:
        if sys.stdin.isatty():
            args.secret = getpass.getpass("Enter the network secret you were given: ").strip()
        if not args.secret:
            die("--secret is required (or set COMMON_REGISTRY_SECRET)")

    if args.permanent:
        install_permanent(args)
        return

    gateway = args.gateway.rstrip("/")

    check_binaries()
    ensure_ollama_running()
    ensure_model(args.model)

    print(style("Opening a Cloudflare quick tunnel to your local Ollama...", "cyan"))
    tunnel_proc, tunnel_url = start_tunnel()
    print(style(f"Tunnel live at {tunnel_url}", "green"))

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

    print(style(f"Registering '{args.name}' with {gateway}...", "cyan"))
    try:
        node = http_json("POST", f"{gateway}/nodes", body=payload, headers={"X-Common-Secret": args.secret})
    except urllib.error.HTTPError as e:
        tunnel_proc.terminate()
        die(f"registration failed: {e.code} {e.read().decode()}")

    node_id = node["id"]
    print(style(f"● You're live! Node id: {node_id}", "green", "bold"))
    print(dim("Keep this window open to stay in the network. Press Ctrl+C to leave."))

    def deregister_and_stop_tunnel():
        try:
            req = urllib.request.Request(f"{gateway}/nodes/{node_id}", method="DELETE", headers={"X-Common-Secret": args.secret})
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.URLError:
            pass
        tunnel_proc.terminate()

    def cleanup(signum=None, frame=None):
        print(style("\nLeaving the network...", "yellow"))
        deregister_and_stop_tunnel()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    last_update_check = time.monotonic()
    while True:
        if tunnel_proc.poll() is not None:
            print(style("Tunnel dropped unexpectedly.", "red"))
            cleanup()

        if not args.no_update and time.monotonic() - last_update_check > UPDATE_CHECK_INTERVAL_SECONDS:
            last_update_check = time.monotonic()
            remote = fetch_update()
            if remote:
                print(style("\nA new version is available — restarting to update...", "yellow"))
                deregister_and_stop_tunnel()
                apply_update_and_restart(remote)

        time.sleep(2)


if __name__ == "__main__":
    main()
