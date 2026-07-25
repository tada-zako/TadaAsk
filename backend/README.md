# TadaAsk Backend

FastAPI backend for TadaAsk. See the [root README](../README.md) for setup and deployment instructions.

## Tests

The backend includes a focused pytest suite for its core unit and integration
paths. It is intended as a practical regression safety net for the MVP, not as a
complete business specification.

Install the development dependency group and run the default suite:

```bash
uv sync --frozen --group dev
uv run pytest -m "not live"
```

Run the suite with the configured branch-coverage threshold:

```bash
uv run pytest -m "not live" --cov=app --cov-report=term-missing
```

Useful focused commands:

```bash
uv run pytest tests/unit
uv run pytest -m integration tests/integration
```

Tests marked `live` are excluded by default because they may require network
access, provider credentials, or incur costs. Run them only when explicitly
needed:

```bash
uv run pytest --run-live -m live
```
