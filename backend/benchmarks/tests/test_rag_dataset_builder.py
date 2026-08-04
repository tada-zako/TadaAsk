import json
import zipfile
from pathlib import Path

import pytest

from benchmarks.rag import build
from benchmarks.rag.adapters.squad import adapt_squad
from benchmarks.rag.adapters.techqa import adapt_techqa
from benchmarks.rag.models import BenchmarkLanguage


def _write_squad(path: Path, count: int, impossible_count: int = 0) -> None:
    paragraphs = []
    for index in range(count):
        answer = f"answer-{index}"
        context = f"Document {index}. " + ("background text " * 20) + answer
        impossible = index < impossible_count
        paragraphs.append(
            {
                "context": context,
                "qas": [
                    {
                        "id": f"q-{index}",
                        "question": f"What is answer {index}?",
                        "is_impossible": impossible,
                        "answers": []
                        if impossible
                        else [
                            {
                                "text": answer,
                                "answer_start": context.index(answer),
                            }
                        ],
                    }
                ],
            }
        )
    path.write_text(
        json.dumps({"data": [{"title": path.stem, "paragraphs": paragraphs}]}),
        encoding="utf-8",
    )


def _write_techqa(
    train_path: Path,
    corpus_path: Path,
    *,
    answerable_count: int,
    unanswerable_count: int,
    distractor_count: int,
) -> None:
    rows = []
    documents: dict[str, str] = {}
    for index in range(answerable_count):
        filename = f"technote-{index}.txt"
        answer = f"value-{index}"
        text = f"Technical note {index}. " + ("support detail " * 20) + answer
        documents[filename] = text
        rows.append(
            {
                "id": f"answerable-{index}",
                "question": f"How can I find value {index}?",
                "answer": answer,
                "is_impossible": False,
                "contexts": [{"filename": filename, "text": text}],
            }
        )
    for index in range(unanswerable_count):
        rows.append(
            {
                "id": f"impossible-{index}",
                "question": f"Which absent setting is number {index}?",
                "answer": "-",
                "is_impossible": True,
                "contexts": [],
            }
        )
    for index in range(distractor_count):
        documents[f"distractor-{index}.txt"] = f"Unrelated technote {index}. " + (
            "unrelated detail " * 20
        )
    train_path.write_text(json.dumps(rows), encoding="utf-8")
    with zipfile.ZipFile(corpus_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, text in documents.items():
            archive.writestr(filename, text)


def test_squad_adapter_filters_and_samples_unique_paragraphs(tmp_path: Path) -> None:
    source_path = tmp_path / "squad.json"
    _write_squad(source_path, 5, impossible_count=1)

    cases, documents = adapt_squad(
        source_path,
        dataset="squad_v2",
        language=BenchmarkLanguage.EN,
        answerable_count=2,
        unanswerable_count=1,
        distractor_count=1,
    )

    assert len(cases) == 3
    assert len(documents) == 4
    assert len({item.id for item in documents}) == 4
    assert sum(item.is_distractor for item in documents) == 1


def test_techqa_adapter_resolves_contexts_from_corpus_zip(tmp_path: Path) -> None:
    train_path = tmp_path / "train.json"
    corpus_path = tmp_path / "corpus.zip"
    _write_techqa(
        train_path,
        corpus_path,
        answerable_count=2,
        unanswerable_count=1,
        distractor_count=1,
    )

    cases, documents = adapt_techqa(
        train_path,
        corpus_path,
        answerable_count=2,
        unanswerable_count=1,
        distractor_count=1,
    )

    assert len(cases) == 3
    assert len(documents) == 3
    assert sum(item.expected_answer is None for item in cases) == 1
    assert sum(item.is_distractor for item in documents) == 1
    assert all(item.needs_review for item in cases if item.expected_answer is None)


@pytest.mark.integration
def test_full_builder_freezes_expected_distribution(tmp_path: Path) -> None:
    cmrc_path = tmp_path / "cmrc.json"
    squad_path = tmp_path / "squad.json"
    techqa_train_path = tmp_path / "techqa-train.json"
    techqa_corpus_path = tmp_path / "techqa-corpus.zip"
    _write_squad(cmrc_path, 32)
    _write_squad(squad_path, 30, impossible_count=2)
    _write_techqa(
        techqa_train_path,
        techqa_corpus_path,
        answerable_count=14,
        unanswerable_count=2,
        distractor_count=16,
    )
    config_path = tmp_path / "baseline.json"
    config_path.write_text(
        json.dumps(
            {
                "expectations": {
                    "case_count": 80,
                    "cases_by_question_type": {
                        "direct": 50,
                        "exact": 6,
                        "multi_document": 4,
                        "multi_turn": 4,
                        "paraphrase": 10,
                        "unanswerable": 6,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "bundle"
    summary = build.build_bundle(
        cmrc_path=cmrc_path,
        squad_path=squad_path,
        techqa_train_path=techqa_train_path,
        techqa_corpus_path=techqa_corpus_path,
        config_path=config_path,
        output_dir=output_dir,
    )

    assert summary["case_count"] == 80
    assert summary["document_count"] == 109
    assert summary["distractor_document_count"] == 48
    assert summary["documents_by_format"] == {
        "html": 16,
        "markdown": 77,
        "pdf": 16,
    }
    assert summary["cases_by_dataset"] == {
        "cmrc2018": 16,
        "squad_v2": 12,
        "techqa_rag_eval": 16,
        "tadaask_custom": 36,
    }
