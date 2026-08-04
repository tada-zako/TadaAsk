import json
import shutil
from pathlib import Path
from typing import Any

from .adapters.squad import adapt_squad
from .adapters.techqa import adapt_techqa
from .bundle import audit_bundle, load_jsonl
from .corpus import render_corpus
from .models import BenchmarkCase, BenchmarkDocument, BenchmarkLanguage
from .resources.curated.documents_v1 import DOCUMENTS as CURATED_DOCUMENTS
from .sources import PUBLIC_SOURCES


RESOURCE_ROOT = Path(__file__).resolve().parent / "resources"


def _write_jsonl(
    path: Path, records: list[BenchmarkCase] | list[BenchmarkDocument]
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(record.model_dump_json(exclude_none=True))
            handle.write("\n")


def build_bundle(
    *,
    cmrc_path: Path,
    squad_path: Path,
    techqa_train_path: Path,
    techqa_corpus_path: Path,
    config_path: Path,
    output_dir: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build the controlled baseline bundle from public and curated sources.

    Args:
        cmrc_path: Downloaded CMRC 2018 JSON file.
        squad_path: Downloaded SQuAD 2.0 JSON file.
        techqa_train_path: Downloaded TechQA-RAG-Eval question file.
        techqa_corpus_path: Downloaded TechQA-RAG-Eval corpus archive.
        config_path: Frozen aggregate expectations for the bundle.
        output_dir: Directory that receives manifests and rendered documents.
        overwrite: Replace an existing output directory when true.

    Returns:
        Aggregate counts for the generated bundle.

    Raises:
        FileExistsError: The output already exists and overwrite is false.
        ValueError: A source cannot provide the configured sample distribution.
    """
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"output already exists: {output_dir}; pass --overwrite to replace it"
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Public adapters first reduce raw sources to the small, fixed benchmark set.
    cmrc_cases, cmrc_documents = adapt_squad(
        cmrc_path,
        dataset="cmrc2018",
        language=BenchmarkLanguage.ZH,
        answerable_count=16,
        unanswerable_count=0,
        distractor_count=16,
    )
    squad_cases, squad_documents = adapt_squad(
        squad_path,
        dataset="squad_v2",
        language=BenchmarkLanguage.EN,
        answerable_count=10,
        unanswerable_count=2,
        distractor_count=16,
    )
    techqa_cases, techqa_documents = adapt_techqa(
        techqa_train_path,
        techqa_corpus_path,
    )
    curated_cases = load_jsonl(
        RESOURCE_ROOT / "curated" / "cases_v1.jsonl", BenchmarkCase
    )

    cases = [*cmrc_cases, *squad_cases, *techqa_cases, *curated_cases]
    source_documents = [
        *cmrc_documents,
        *squad_documents,
        *techqa_documents,
        *CURATED_DOCUMENTS,
    ]

    # The final bundle owns all rendered files, so manifest paths remain local.
    documents = render_corpus(source_documents, output_dir)
    _write_jsonl(output_dir / "cases.jsonl", cases)
    _write_jsonl(output_dir / "documents.jsonl", documents)
    summary = audit_bundle(output_dir, config_path)

    inputs = {
        "cmrc2018": (cmrc_path, PUBLIC_SOURCES["cmrc2018"]),
        "squad_v2": (squad_path, PUBLIC_SOURCES["squad_v2"]),
        "techqa_train": (techqa_train_path, PUBLIC_SOURCES["techqa_train"]),
        "techqa_corpus": (techqa_corpus_path, PUBLIC_SOURCES["techqa_corpus"]),
    }
    metadata = {
        **summary,
        "raw_sources": {
            name: {
                "url": source.url,
                "license": source.license,
                "bytes": path.stat().st_size,
            }
            for name, (path, source) in inputs.items()
        },
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
