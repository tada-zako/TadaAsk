from typing import Annotated, AsyncIterable

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from ...deps import RAGJobManagerDeps


router = APIRouter()


def _parse_last_event_sequence(last_event_id: str | None) -> int:
    """解析 SSE Last-Event-ID；避免非法值。"""
    if not last_event_id:
        return 0

    try:
        sequence = int(last_event_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Last-Event-ID",
        ) from exc

    if sequence < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Last-Event-ID",
        )

    return sequence


@router.get(
    "/jobs/{job_uid}/events",
    response_class=EventSourceResponse,
)
async def stream_rag_job_events(
    job_uid: str,
    rag_job_manager: RAGJobManagerDeps,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> AsyncIterable[ServerSentEvent]:
    """RAG job SSE 观察接口。"""
    job = rag_job_manager.get_job(job_uid)
    if not job:
        # 验证 job_uid
        raise HTTPException(status_code=404, detail="RAG job not found")

    # 从 Last-Event-ID 头部获取上次事件的 sequence
    after_sequence = _parse_last_event_sequence(last_event_id)

    # 订阅 job 事件流，并持续输出 SSE
    async for stored in rag_job_manager.subscribe(
        job_uid=job_uid,
        after_sequence=after_sequence,
    ):
        yield ServerSentEvent(
            id=str(stored.sequence),
            event=stored.event.event,
            data=stored.event.model_dump(
                exclude={"event"},
                by_alias=True,
                mode="json",
            ),
        )
