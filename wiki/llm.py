"""LLM invocation via CLI (claude or copilot)."""

import logging
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .config import Config, load as load_config

logger = logging.getLogger(__name__)

_RETRY_COUNT = 3
_RETRY_DELAY = 5  # seconds


def run(
    prompt: str,
    context: str = "",
    config: Config | None = None,
    cwd: Path | None = None,
    dry_run: bool = False,
) -> str:
    """Call the configured LLM CLI, tee output to logs/, and return empty string.

    The LLM writes files directly — we don't parse its stdout.
    Output flows live to the terminal and is also written to <cwd>/logs/.

    If dry_run is True, write an executable bash script instead of running.
    """
    if config is None:
        config = load_config()

    full_prompt = f"{prompt}\n\n{context}" if context.strip() else prompt

    # Auto-inject --permission-mode acceptEdits for claude so it can write files
    extra_args: list[str] = []
    if config.llm_backend == "claude" and "--permission-mode" not in config.llm_args:
        extra_args = ["--permission-mode", "acceptEdits"]

    cmd = [config.llm_path, *config.llm_args, *extra_args, "-p", full_prompt]

    if dry_run:
        script = _write_dry_run_script(cmd, full_prompt, extra_args, cwd, config)
        print(f"[dry-run] script: {script}")
        return ""

    log_path = _log_path(cwd)

    last_error: str = ""
    for attempt in range(_RETRY_COUNT):
        try:
            returncode = _tee_run(cmd, cwd, log_path)
            if returncode == 0:
                return ""
            last_error = f"exit code {returncode}"
            logger.warning(
                f"LLM call failed (attempt {attempt + 1}/{_RETRY_COUNT}): {last_error}"
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"LLM binary not found: {config.llm_path!r}. "
                "Check [claude] or [copilot] path in config."
            )
        except Exception as e:
            last_error = str(e)
            logger.warning(f"LLM call error (attempt {attempt + 1}/{_RETRY_COUNT}): {e}")

        if attempt < _RETRY_COUNT - 1:
            time.sleep(_RETRY_DELAY)

    raise RuntimeError(
        f"LLM call failed after {_RETRY_COUNT} attempts. Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_path(cwd: Path | None) -> Path:
    log_dir = (cwd / "logs") if cwd else Path(tempfile.gettempdir()) / "wiki-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return log_dir / f"{timestamp}.log"


def _tee_run(cmd: list[str], cwd: Path | None, log_path: Path) -> int:
    """Run cmd, streaming output to both the terminal and log_path."""
    with open(log_path, "w", encoding="utf-8") as log_f:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log_f.write(line)
        proc.wait()
    logger.debug(f"LLM output logged to: {log_path}")
    return proc.returncode


def _write_dry_run_script(
    cmd: list[str],
    prompt: str,
    extra_args: list[str],
    cwd: Path | None,
    config: Config,
) -> Path:
    """Write a self-contained bash script with the full prompt via heredoc."""
    work_dir = cwd or Path.cwd()
    script_path = Path(tempfile.gettempdir()) / "wiki-dry-run.sh"

    # Escape any heredoc sentinel that might appear in the prompt
    safe_prompt = prompt.replace("PROMPT_EOF", "PROMPT_E_O_F")

    base_cmd = shlex.join([config.llm_path, *config.llm_args, *extra_args])

    script = f"""\
#!/bin/sh
# wiki --dry-run  ({datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
# Edit the prompt below and run to invoke the LLM manually.

set -eu
cd {shlex.quote(str(work_dir))}

PROMPT=$(cat << 'PROMPT_EOF'
{safe_prompt}
PROMPT_EOF
)

{base_cmd} -p "$PROMPT"
"""
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)
    return script_path
