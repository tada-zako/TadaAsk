import argparse
import json
from pathlib import Path

from .build import build_bundle
from .bundle import audit_bundle
from .sources import PUBLIC_SOURCES, download_sources


PACKAGE_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PACKAGE_ROOT.parents[1]
RESOURCE_ROOT = PACKAGE_ROOT / "resources"
DATA_ROOT = BACKEND_ROOT / "data" / "benchmarks" / "rag"


def main() -> int:
    """Run the unified RAG benchmark data command."""
    parser = argparse.ArgumentParser(description="Manage TadaAsk RAG benchmark data.")
    commands = parser.add_subparsers(dest="command", required=True)

    # ----- 训练集下载命令；从网络下载训练集源数据。 -----
    download_parser = commands.add_parser("download", help="Download public sources.")
    download_parser.add_argument(
        "sources",
        nargs="*",
        choices=sorted(PUBLIC_SOURCES),
        default=list(PUBLIC_SOURCES),
    )
    download_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_ROOT / "sources",
    )

    # ----- 训练集构建命令；
    # 从 curated 训练集以及公开数据集构建真正用于 TadaAsk benchmark 的测试集。 -----
    build_parser = commands.add_parser("build", help="Build the baseline bundle.")
    source_root = DATA_ROOT / "sources"
    build_parser.add_argument(
        "--cmrc", type=Path, default=source_root / "cmrc2018_dev.json"
    )
    build_parser.add_argument(
        "--squad", type=Path, default=source_root / "squad_dev_v2.json"
    )
    build_parser.add_argument(
        "--techqa-train",
        type=Path,
        default=source_root / "techqa_rag_eval_train.json",
    )
    build_parser.add_argument(
        "--techqa-corpus",
        type=Path,
        default=source_root / "techqa_rag_eval_corpus.zip",
    )
    build_parser.add_argument(
        "--config",
        type=Path,
        default=RESOURCE_ROOT / "configs" / "baseline-v1.json",
    )
    build_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_ROOT / "bundles" / "v1",
    )
    build_parser.add_argument("--overwrite", action="store_true")

    # ----- 训练集下载命令 -----
    validate_parser = commands.add_parser(
        "validate", help="Validate a materialized bundle."
    )
    validate_parser.add_argument(
        "--bundle",
        type=Path,
        default=RESOURCE_ROOT / "smoke",
    )
    validate_parser.add_argument(
        "--config",
        type=Path,
        default=RESOURCE_ROOT / "configs" / "smoke.json",
    )

    args = parser.parse_args()
    if args.command == "download":
        result: object = {"downloads": download_sources(args.sources, args.output_dir)}
    elif args.command == "build":
        result = build_bundle(
            cmrc_path=args.cmrc,
            squad_path=args.squad,
            techqa_train_path=args.techqa_train,
            techqa_corpus_path=args.techqa_corpus,
            config_path=args.config,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    else:
        result = audit_bundle(args.bundle, args.config)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
