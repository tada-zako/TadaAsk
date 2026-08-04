import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from ..corpus import BuildDocument
from ..models import BenchmarkCase, BenchmarkLanguage, GoldEvidence, QuestionType


DATASET_ID = "techqa_rag_eval"


def _stable_key(value: str) -> str:
    return hashlib.sha256(f"tadaask-rag:{value}".encode()).hexdigest()


def _safe_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", value.casefold()).strip("-.")
    digest = hashlib.sha256(value.encode()).hexdigest()[:12]
    return f"{normalized[:48]}-{digest}" if normalized else digest


def _evidence_window(text: str, answer: str) -> str:
    answer_start = text.casefold().find(answer.casefold())
    if answer_start < 0:
        return text[:400].strip()
    start = max(0, answer_start - 180)
    end = min(len(text), answer_start + len(answer) + 180)
    return text[start:end].strip()


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))

    candidates: list[dict[str, Any]] = []
    for item in raw:
        case_id = str(item.get("id") or "").strip()
        question = str(item.get("question") or "").strip()
        impossible = bool(item.get("is_impossible", False))
        answer = str(item.get("answer") or "").strip()
        contexts = item.get("contexts") or []
        if not case_id or not question:
            continue
        if impossible:
            candidates.append(
                {
                    "id": case_id,
                    "question": question,
                    "answer": None,
                    "contexts": [],
                }
            )
            continue
        valid_contexts = [
            context
            for context in contexts
            if context.get("filename") and context.get("text")
        ]
        if answer and answer != "-" and valid_contexts:
            candidates.append(
                {
                    "id": case_id,
                    "question": question,
                    "answer": answer,
                    "contexts": valid_contexts,
                }
            )
    return sorted(candidates, key=lambda item: _stable_key(item["id"]))


def _read_document(archive: zipfile.ZipFile, member: str) -> str:
    return archive.read(member).decode("utf-8-sig").strip()


def adapt_techqa(
    train_path: Path,
    corpus_path: Path,
    *,
    answerable_count: int = 14,
    unanswerable_count: int = 2,
    distractor_count: int = 16,
) -> tuple[list[BenchmarkCase], list[BuildDocument]]:
    """Select benchmark cases and documents from TechQA-RAG-Eval.

    Args:
        train_path: TechQA-RAG-Eval question file.
        corpus_path: TechQA-RAG-Eval corpus archive.
        answerable_count: Number of answerable questions to select.
        unanswerable_count: Number of unanswerable questions to select.
        distractor_count: Number of unrelated corpus documents to include.

    Returns:
        Selected benchmark cases and source documents.

    Raises:
        ValueError: The source cannot satisfy the requested sample distribution.
    """
    candidates = _load_candidates(train_path)
    answerable = [item for item in candidates if item["answer"] is not None][
        :answerable_count
    ]
    unanswerable = [item for item in candidates if item["answer"] is None][
        :unanswerable_count
    ]
    if len(answerable) != answerable_count or len(unanswerable) != unanswerable_count:
        raise ValueError("TechQA-RAG-Eval did not contain enough valid cases")

    cases: list[BenchmarkCase] = []
    documents: list[BuildDocument] = []
    document_ids: dict[str, str] = {}
    with zipfile.ZipFile(corpus_path) as archive:
        members = {
            PurePosixPath(info.filename.replace("\\", "/")).name: info.filename
            for info in archive.infolist()
            if not info.is_dir()
        }

        # Resolve labeled contexts against the independent corpus archive.
        for item in answerable:
            evidence: list[GoldEvidence] = []
            for context in item["contexts"]:
                filename = PurePosixPath(str(context["filename"])).name
                member = members.get(filename)
                if member is None:
                    raise ValueError(
                        "TechQA corpus is missing a selected context document"
                    )
                document_id = document_ids.get(filename)
                if document_id is None:
                    document_id = f"techqa.{_safe_id(filename)}"
                    document_ids[filename] = document_id
                    documents.append(
                        BuildDocument(
                            id=document_id,
                            dataset=DATASET_ID,
                            title=PurePosixPath(filename).stem,
                            language=BenchmarkLanguage.EN,
                            text=_read_document(archive, member),
                        )
                    )
                evidence.append(
                    GoldEvidence(
                        document_id=document_id,
                        text=_evidence_window(
                            str(context["text"]), str(item["answer"])
                        ),
                    )
                )
            cases.append(
                BenchmarkCase(
                    id=f"techqa.{_safe_id(item['id'])}",
                    dataset=DATASET_ID,
                    language=BenchmarkLanguage.EN,
                    question_type=QuestionType.DIRECT,
                    question=item["question"],
                    expected_answer=item["answer"],
                    gold_evidence=evidence,
                )
            )

        for item in unanswerable:
            cases.append(
                BenchmarkCase(
                    id=f"techqa.{_safe_id(item['id'])}",
                    dataset=DATASET_ID,
                    language=BenchmarkLanguage.EN,
                    question_type=QuestionType.UNANSWERABLE,
                    question=item["question"],
                    needs_review=True,
                )
            )

        # Distractor contents are read only after member names have been selected.
        relevant_document_count = len(documents)
        for filename, member in sorted(
            members.items(), key=lambda item: _stable_key(item[0])
        ):
            if len(documents) == relevant_document_count + distractor_count:
                break
            if filename in document_ids:
                continue
            text = _read_document(archive, member)
            if not 200 <= len(text) <= 20000:
                continue
            document_id = f"techqa.{_safe_id(filename)}"
            document_ids[filename] = document_id
            documents.append(
                BuildDocument(
                    id=document_id,
                    dataset=DATASET_ID,
                    title=PurePosixPath(filename).stem,
                    language=BenchmarkLanguage.EN,
                    text=text,
                    is_distractor=True,
                )
            )
    if sum(document.is_distractor for document in documents) != distractor_count:
        raise ValueError("TechQA corpus did not contain enough distractor documents")
    return cases, documents
