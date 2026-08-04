import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..corpus import BuildDocument
from ..models import BenchmarkCase, BenchmarkLanguage, GoldEvidence, QuestionType


def _safe_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", value.casefold()).strip("-.")
    digest = hashlib.sha256(value.encode()).hexdigest()[:12]
    return f"{normalized[:48]}-{digest}" if normalized else digest


def _evidence_window(context: str, answer_start: int, answer: str) -> str:
    start = max(0, answer_start - 180)
    end = min(len(context), answer_start + len(answer) + 180)
    return context[start:end].strip()


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))

    candidates: list[dict[str, Any]] = []
    for article in raw.get("data", []):
        title = str(article.get("title") or "Untitled")
        for paragraph_index, paragraph in enumerate(article.get("paragraphs", [])):
            context = str(paragraph.get("context") or "")
            if not 200 <= len(context) <= 6000:
                continue
            paragraph_id = f"{title}:{paragraph_index}"
            for qa in paragraph.get("qas", []):
                question = str(qa.get("question") or "").strip()
                if not 4 <= len(question) <= 300:
                    continue
                if bool(qa.get("is_impossible", False)):
                    candidates.append(
                        {
                            "id": str(qa.get("id") or paragraph_id),
                            "title": title,
                            "paragraph_id": paragraph_id,
                            "context": context,
                            "question": question,
                            "answers": [],
                        }
                    )
                    continue
                answers: list[tuple[str, int]] = []
                for answer in qa.get("answers") or []:
                    text = str(answer.get("text") or "").strip()
                    start = int(answer.get("answer_start", -1))
                    if (
                        text
                        and start >= 0
                        and context[start : start + len(text)] == text
                    ):
                        answers.append((text, start))
                if answers:
                    candidates.append(
                        {
                            "id": str(qa.get("id") or paragraph_id),
                            "title": title,
                            "paragraph_id": paragraph_id,
                            "context": context,
                            "question": question,
                            "answers": answers,
                        }
                    )
    return sorted(
        candidates,
        key=lambda item: hashlib.sha256(
            f"tadaask-rag:{item['id']}".encode()
        ).hexdigest(),
    )


def adapt_squad(
    path: Path,
    *,
    dataset: str,
    language: BenchmarkLanguage,
    answerable_count: int,
    unanswerable_count: int,
    distractor_count: int,
) -> tuple[list[BenchmarkCase], list[BuildDocument]]:
    """Select benchmark cases and corpus documents from SQuAD-style JSON.

    Args:
        path: Public dataset JSON file.
        dataset: Dataset name written to generated records.
        language: Language assigned to selected records.
        answerable_count: Number of answerable questions to select.
        unanswerable_count: Number of unanswerable questions to select.
        distractor_count: Number of unrelated contexts to include.

    Returns:
        Selected benchmark cases and source documents.

    Raises:
        ValueError: The source cannot satisfy the requested sample distribution.
    """
    candidates = _load_candidates(path)

    # Select at most one question per paragraph to prevent near-duplicate cases.
    chosen: list[dict[str, Any]] = []
    used_paragraphs: set[str] = set()
    answerable_selected = 0
    unanswerable_selected = 0
    for item in candidates:
        answerable = bool(item["answers"])
        if answerable and answerable_selected >= answerable_count:
            continue
        if not answerable and unanswerable_selected >= unanswerable_count:
            continue
        if item["paragraph_id"] in used_paragraphs:
            continue
        chosen.append(item)
        used_paragraphs.add(item["paragraph_id"])
        answerable_selected += int(answerable)
        unanswerable_selected += int(not answerable)
        if (
            answerable_selected == answerable_count
            and unanswerable_selected == unanswerable_count
        ):
            break
    if (
        answerable_selected != answerable_count
        or unanswerable_selected != unanswerable_count
    ):
        raise ValueError(f"{dataset} did not contain enough unique valid cases")

    cases: list[BenchmarkCase] = []
    documents: list[BuildDocument] = []
    for item in chosen:
        document_id = f"{dataset}.{_safe_id(item['paragraph_id'])}"
        documents.append(
            BuildDocument(
                id=document_id,
                dataset=dataset,
                title=item["title"],
                language=language,
                text=item["context"],
            )
        )
        if item["answers"]:
            answers: list[tuple[str, int]] = item["answers"]
            answer, answer_start = answers[0]
            cases.append(
                BenchmarkCase(
                    id=f"{dataset}.{_safe_id(item['id'])}",
                    dataset=dataset,
                    language=language,
                    question_type=QuestionType.DIRECT,
                    question=item["question"],
                    expected_answer=answer,
                    acceptable_answers=list(
                        dict.fromkeys(text for text, _ in answers[1:] if text != answer)
                    ),
                    gold_evidence=[
                        GoldEvidence(
                            document_id=document_id,
                            text=_evidence_window(
                                item["context"], answer_start, answer
                            ),
                        )
                    ],
                )
            )
        else:
            cases.append(
                BenchmarkCase(
                    id=f"{dataset}.{_safe_id(item['id'])}",
                    dataset=dataset,
                    language=language,
                    question_type=QuestionType.UNANSWERABLE,
                    question=item["question"],
                    needs_review=True,
                )
            )

    # Add stable paragraph-level distractors after excluding all selected contexts.
    for item in candidates:
        if len(documents) == len(chosen) + distractor_count:
            break
        if item["paragraph_id"] in used_paragraphs:
            continue
        used_paragraphs.add(item["paragraph_id"])
        documents.append(
            BuildDocument(
                id=f"{dataset}.{_safe_id(item['paragraph_id'])}",
                dataset=dataset,
                title=item["title"],
                language=language,
                text=item["context"],
                is_distractor=True,
            )
        )
    if len(documents) != len(chosen) + distractor_count:
        raise ValueError(f"{dataset} did not contain enough distractor contexts")
    return cases, documents
