"""CLI that validates benchmark metadata and prints a compact count summary."""

import argparse
import json
from pathlib import Path

from .dataset import BenchmarkDataError, validate_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate RAG benchmark manifests without running a benchmark."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent / "configs" / "smoke.json",
        help="Path to a benchmark run config.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = validate_bundle(args.config)
    except BenchmarkDataError as exc:
        print(f"validation failed: {exc}")
        return 2

    print(json.dumps(summary.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
