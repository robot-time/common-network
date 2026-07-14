"""Isolated execution for model-generated code.

Runs in a fresh subprocess (own memory space, own crash domain) with a wall-clock
timeout and a resource cap on CPU time / memory. This is process-level isolation,
not container-level -- it stops a hang or a crash from taking down the bench run,
but a determined malicious payload could still touch the filesystem or network.
That's an acceptable bar for scoring completions from known, trusted models in a
controlled benchmark run. TODO(v0.3): move to a container (e.g. Docker) sandbox
if this ever runs untrusted, user-submitted code.
"""
import resource
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 10
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024  # 512MB


def _limit_resources():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (DEFAULT_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS))


def run_program(source: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> tuple[bool, str]:
    """Run a self-contained Python program. Returns (ok, error_message)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(source)
        path = f.name

    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=timeout,
            preexec_fn=_limit_resources if sys.platform != "win32" else None,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or "non-zero exit").strip()[-2000:]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except Exception as e:
        return False, str(e)
    finally:
        Path(path).unlink(missing_ok=True)
