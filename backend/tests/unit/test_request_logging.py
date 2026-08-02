import asyncio
import re
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from loguru import logger
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from starlette.types import Message, Receive, Scope, Send

from app.core.request_logging import (
    REQUEST_ID_HEADER,
    RequestLoggingMiddleware,
    UnhandledExceptionMiddleware,
)
from app.main import register_exception_handlers


@pytest.fixture
def request_log_records() -> Iterator[list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []

    def capture_record(message) -> None:
        record = message.record
        records.append(
            {
                "exception": record["exception"],
                "extra": dict(record["extra"]),
                "level": record["level"].name,
                "message": record["message"],
            }
        )

    handler_id = logger.add(
        capture_record,
        level="TRACE",
        filter=lambda record: str(record["extra"].get("event", "")).startswith(
            ("http.", "test.")
        ),
    )
    try:
        yield records
    finally:
        logger.remove(handler_id)


async def test_request_ids_are_server_generated_and_isolated_per_request(
    request_log_records: list[dict[str, Any]],
) -> None:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/items/{item_id}")
    async def read_item(item_id: str, request: Request):
        logger.bind(event="test.request.context", item_id=item_id).info(
            "Request context available"
        )
        return {"requestId": request.state.request_id}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        responses = await asyncio.gather(
            client.get("/items/first", headers={REQUEST_ID_HEADER: "client-value"}),
            client.get("/items/second"),
        )

    response_ids = {response.headers[REQUEST_ID_HEADER] for response in responses}
    body_ids = {response.json()["requestId"] for response in responses}
    assert response_ids == body_ids
    assert len(response_ids) == 2
    assert "client-value" not in response_ids
    assert all(re.fullmatch(r"[0-9a-f]{32}", value) for value in response_ids)

    access_records = [
        record
        for record in request_log_records
        if record["extra"].get("event") == "http.request.completed"
    ]
    context_records = [
        record
        for record in request_log_records
        if record["extra"].get("event") == "test.request.context"
    ]
    assert len(access_records) == len(context_records) == 2
    assert {record["extra"]["request_id"] for record in access_records} == response_ids
    assert {record["extra"]["request_id"] for record in context_records} == response_ids
    assert all(
        record["extra"]["http_route"] == "/items/{item_id}" for record in access_records
    )


async def test_sse_logs_open_and_completed_lifecycle(
    request_log_records: list[dict[str, Any]],
) -> None:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/events")
    async def stream_events() -> StreamingResponse:
        async def generate():
            yield b"event: done\ndata: {}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/events")

    request_id = response.headers[REQUEST_ID_HEADER]
    stream_records = [
        record
        for record in request_log_records
        if str(record["extra"].get("event", "")).startswith("http.stream.")
    ]
    assert response.status_code == 200
    assert [record["extra"]["event"] for record in stream_records] == [
        "http.stream.opened",
        "http.stream.completed",
    ]
    assert all(record["extra"]["request_id"] == request_id for record in stream_records)
    assert all(record["extra"]["http_route"] == "/events" for record in stream_records)


async def test_server_error_returns_safe_correlation_fields_and_one_error_log(
    request_log_records: list[dict[str, Any]],
) -> None:
    app = FastAPI()
    app.add_middleware(UnhandledExceptionMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://console.example"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    @app.get("/fail")
    async def fail_request() -> None:
        raise RuntimeError("provider-secret-detail")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/fail",
            headers={"Origin": "https://console.example"},
        )

    payload = response.json()
    assert response.status_code == 500
    assert response.headers["Access-Control-Allow-Origin"] == "https://console.example"
    assert payload["detail"] == "Internal Server Error"
    assert payload["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert re.fullmatch(r"[0-9a-f]{32}", payload["error_id"])
    assert "provider-secret-detail" not in response.text

    error_records = [
        record for record in request_log_records if record["level"] == "ERROR"
    ]
    assert len(error_records) == 1
    assert error_records[0]["extra"]["event"] == "http.request.exception"
    assert error_records[0]["extra"]["request_id"] == payload["request_id"]
    assert error_records[0]["extra"]["error_id"] == payload["error_id"]
    assert error_records[0]["exception"] is not None
    assert (
        len(
            [
                record
                for record in request_log_records
                if record["extra"].get("event") == "http.request.completed"
                and record["extra"].get("status_code") == 500
            ]
        )
        == 1
    )


async def test_http_500_detail_is_replaced_with_safe_error_response(
    request_log_records: list[dict[str, Any]],
) -> None:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    @app.get("/storage-fail")
    async def fail_request() -> None:
        raise HTTPException(status_code=500, detail="storage-secret-detail")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/storage-fail")

    payload = response.json()
    assert response.status_code == 500
    assert payload["detail"] == "Internal Server Error"
    assert payload["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert "storage-secret-detail" not in response.text
    assert (
        len([record for record in request_log_records if record["level"] == "ERROR"])
        == 1
    )


async def test_expected_http_error_only_uses_info_access_log(
    request_log_records: list[dict[str, Any]],
) -> None:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/missing")

    access_records = [
        record
        for record in request_log_records
        if record["extra"].get("event") == "http.request.completed"
    ]
    assert response.status_code == 404
    assert REQUEST_ID_HEADER in response.headers
    assert len(access_records) == 1
    assert access_records[0]["level"] == "INFO"
    assert access_records[0]["extra"]["status_code"] == 404


async def test_cancelled_task_is_logged_and_reraised(
    request_log_records: list[dict[str, Any]],
) -> None:
    async def cancelled_app(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive, send
        raise asyncio.CancelledError

    middleware = RequestLoggingMiddleware(cancelled_app)
    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/cancel",
        "raw_path": b"/cancel",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "state": {},
    }

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        del message

    with pytest.raises(asyncio.CancelledError):
        await middleware(scope, receive, send)

    cancelled_records = [
        record
        for record in request_log_records
        if record["extra"].get("event") == "http.request.cancelled"
    ]
    assert len(cancelled_records) == 1
    assert cancelled_records[0]["extra"]["http_route"] == "/cancel"
