# TadaAsk Backend

FastAPI backend for TadaAsk. See the [root README](../README.md) for setup and deployment instructions.

## Logging

Console output supports two format options:
- `LOG_FORMAT=console` provides a format suitable for everyday reading by developers;
- `LOG_FORMAT=json` emits JSON Lines format suitable for container log collectors, making it easier to pinpoint detailed exception locations;

Backend logging is controlled by the following configuration:

```env
LOG_LEVEL=INFO
LOG_FORMAT=console
LOG_FILE_ENABLED=false  # file logging is disabled by default
LOG_FILE_PATH=./data/logs/tadaask.log
```

The file sink does not replace console output. It rotates at 15 MB, keeps archives for 14 days, compresses rotated files, and does not propagate sink write failures into requests.


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
