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
            "query_expansion": raw.get("query_expansion"),
        }
    )
    if int(config.search_options.get("top_k", 8)) < 5:
        raise ValueError("search.top_k must be at least 5 for Recall@5")
    if config.mode == BenchmarkSearchMode.FAST:
        return config

    query_expansion = config.query_expansion
    if query_expansion is None:
        raise ValueError(
            "query_expansion.provider and query_expansion.model are required "
            "for adaptive/full recall"
        )
    if query_expansion.base_url and "PORT" in query_expansion.base_url.upper():
        raise ValueError("query_expansion.base_url still contains a placeholder")
    if query_expansion.provider != "ollama" and (
        query_expansion.api_key is None
        or not query_expansion.api_key.get_secret_value()
    ):
        raise ValueError("query_expansion.api_key is required by this provider")
    return config
