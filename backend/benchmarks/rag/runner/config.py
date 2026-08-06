import os
import re
import tomllib
from pathlib import Path

from .schemas import BenchmarkSearchMode, RecallRunConfig


BACKEND_ROOT = Path(__file__).resolve().parents[3]


def load_recall_config(path: Path) -> RecallRunConfig:
    """Load and validate the operator-managed recall configuration.

    Args:
        path: TOML configuration path.

    Returns:
        Configuration with paths resolved from the backend directory.
    """
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    benchmark = raw["benchmark"]

    def resolve(value: str) -> Path:
        candidate = Path(value)
        return (
            candidate.resolve()
            if candidate.is_absolute()
            else (BACKEND_ROOT / candidate).resolve()
        )

    config = RecallRunConfig.model_validate(
        {
            **benchmark,
            "bundle_dir": resolve(benchmark["bundle_dir"]),
            "workspace_dir": resolve(benchmark["workspace_dir"]),
            "run_dir": resolve(benchmark["run_dir"]),
            "app_settings": raw.get("app", {}),
            "search_options": raw.get("search", {}),
            "query_expansion": raw.get("query_expansion", {}),
        }
    )
    if int(config.search_options.get("top_k", 8)) < 5:
        raise ValueError("search.top_k must be at least 5 for Recall@5")
    if config.mode == BenchmarkSearchMode.FAST:
        return config

    missing = {"provider", "model"}.difference(config.query_expansion)
    if missing:
        raise ValueError(
            "query_expansion.provider and query_expansion.model are required "
            "for adaptive/full recall"
        )
    base_url = config.query_expansion.get("base_url", "")
    if "PORT" in base_url.upper():
        raise ValueError("query_expansion.base_url still contains a placeholder")
    if config.query_expansion["provider"] != "ollama":
        api_key_env = config.query_expansion.get("api_key_env")
        if not api_key_env or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
            raise ValueError(
                "query_expansion.api_key_env must name an environment variable"
            )
        if not os.environ.get(api_key_env):
            raise ValueError(
                "the API key environment variable configured by "
                "query_expansion.api_key_env is not available"
            )
    return config
