"""Config loading for the wiki system."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("~/.config/wiki/config.toml")


@dataclass
class Config:
    vault_path: Path
    user_name: str
    resolver_mode: str
    llm_backend: str
    llm_path: str
    llm_args: list[str]
    compile_max_files: int = 10


def load(config_path: Path | None = None) -> Config:
    path = (config_path or DEFAULT_CONFIG_PATH).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    vault = data.get("vault", {})
    user = data.get("user", {})
    resolver = data.get("resolver", {})
    llm = data.get("llm", {})
    compile_cfg = data.get("compile", {})

    backend = llm.get("backend", "claude")
    backend_cfg = data.get(backend, {})

    return Config(
        vault_path=Path(vault.get("path", "~/wiki")).expanduser(),
        user_name=user.get("name", "user"),
        resolver_mode=resolver.get("mode", "direct"),
        llm_backend=backend,
        llm_path=_resolve_exe(backend_cfg.get("path", "claude")),
        llm_args=backend_cfg.get("args", ["-p"]),
        compile_max_files=compile_cfg.get("max_files", 10),
    )


def _resolve_exe(path: str) -> str:
    """Expand ~ and home-relative paths (e.g. '.local/bin/claude' → '~/.local/bin/claude')."""
    if not path:
        return path
    if "/" not in path:
        return path  # bare name — resolved via PATH
    p = Path(path)
    if path.startswith("~"):
        return str(p.expanduser())
    if not p.is_absolute():
        return str(Path.home() / p)  # .local/bin/claude → /home/user/.local/bin/claude
    return path
