"""LLM invocation via CLI (claude or copilot)."""

import logging
import subprocess
import time
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
    """Call the configured LLM CLI and return its stdout.

    If dry_run is True, print the command and prompt instead of executing.
    Retries up to _RETRY_COUNT times on failure with _RETRY_DELAY seconds between
    attempts. Raises RuntimeError if all attempts fail.
    """
    if config is None:
        config = load_config()

    full_prompt = f"{prompt}\n\n{context}" if context.strip() else prompt
    cmd = [config.llm_path, *config.llm_args, full_prompt]

    if dry_run:
        import shlex
        # Print the invocation with the prompt truncated for readability
        truncated = full_prompt[:200].replace("\n", "\\n")
        if len(full_prompt) > 200:
            truncated += f"... [{len(full_prompt)} chars total]"
        print(f"[dry-run] cwd: {cwd or Path.cwd()}")
        print(f"[dry-run] cmd: {shlex.join([config.llm_path, *config.llm_args, '<prompt>'])}")
        print(f"[dry-run] prompt: {truncated}")
        return ""

    last_error: str = ""
    for attempt in range(_RETRY_COUNT):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
            )
            if result.returncode == 0:
                return result.stdout
            last_error = result.stderr.strip()
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
