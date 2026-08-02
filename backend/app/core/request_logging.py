import asyncio
import time
import uuid

from loguru import logger
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


REQUEST_ID_HEADER = "X-Request-ID"


class UnhandledExceptionMiddleware:
    """
    将未由 ExceptionMiddleware 处理的异常转换为可关联且不泄密的 500 响应。

    目前（26-07-31） fastapi APP 实际的中间件链路：
        ServerErrorMiddleware: 最顶层的 @app.exception_handler(Exception)
        -> RequestLogging
        -> Widget CORS
        -> Admin CORS
        -> UnhandledExceptionMiddleware
        -> ExceptionMiddleware: 明确异常的处理 @app.exception_handler(SpecifiedError)
        -> Router
    对于 Router 触发的异常，如果未被 ExceptionMiddleware 处理，
    除 asyncio.CancelledError（继承自 BaseException） 或 SSE body 响应阶段的异常，
    会被 UnhandledExceptionMiddleware 捕获并转换为 JSONResponse，
    确保在 CORS Middleware 中能够正确为未处理异常设置跨域 header。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_with_start_tracking(message: Message) -> None:
            """send 函数包装"""
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_with_start_tracking)
        except Exception as exc:
            # 流式响应已经发出 headers 后无法再合法发送第二个 500 响应；
            # 交回 Starlette 最外层异常处理器记录异常并中止当前连接。
            if response_started:
                raise

            request_id = str(
                scope.setdefault("state", {}).get("request_id") or uuid.uuid4().hex
            )
            response = internal_server_error_response(
                request_id=request_id,
                exc=exc,
            )
            await response(scope, receive, send)


class RequestLoggingMiddleware:
    """
    统一请求日志中间件：
    为 HTTP 请求注入关联 ID，并记录普通响应和 SSE 的生命周期，
    作用相当于 uvicorn 日志。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ----- 日志 context -----
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        started_at = time.perf_counter()
        status_code: int | None = None
        is_sse = False
        stream_opened = False
        response_completed = False
        client_disconnected = False
        outcome = "completed"

        async def receive_with_disconnect_tracking() -> Message:
            """标记是否客户端断连"""
            nonlocal client_disconnected
            message = await receive()
            if message["type"] == "http.disconnect":
                client_disconnected = True
            return message

        async def send_with_request_id(message: Message) -> None:
            """标记响应上下文"""
            nonlocal status_code, is_sse, stream_opened, response_completed

            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                media_type = headers.get("content-type", "").partition(";")[0]
                is_sse = media_type.strip().lower() == "text/event-stream"

            await send(message)

            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                response_completed = True

            if is_sse and not stream_opened:
                stream_opened = True
                logger.bind(
                    event="http.stream.opened",
                    http_method=scope["method"],
                    http_route=_resolve_route(scope),
                    status_code=status_code,
                ).info("HTTP event stream opened")

        with logger.contextualize(request_id=request_id):
            try:
                await self.app(
                    scope,
                    receive_with_disconnect_tracking,
                    send_with_request_id,
                )
            except asyncio.CancelledError:
                # asyncio.CancelledError 继承自 BaseException，ExceptionMiddleware 无法捕获
                outcome = "cancelled"
                raise
            except Exception:
                outcome = "failed"
                status_code = status_code or 500
                raise
            finally:
                if client_disconnected and not response_completed:
                    outcome = "disconnected"

                duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
                event_prefix = "http.stream" if is_sse else "http.request"
                logger.bind(
                    event=f"{event_prefix}.{outcome}",
                    http_method=scope["method"],
                    http_route=_resolve_route(scope),
                    status_code=status_code,
                    duration_ms=duration_ms,
                ).info(
                    "HTTP event stream finished" if is_sse else "HTTP request finished"
                )


def _resolve_route(scope: Scope) -> str:
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str):
        return route_path
    return str(scope.get("path", ""))


def internal_server_error_response(
    *,
    request_id: str,
    exc: Exception,
) -> JSONResponse:
    """记录一次完整服务端异常，并返回不泄露内部细节的关联响应。"""
    error_id = uuid.uuid4().hex

    logger.bind(
        event="http.request.exception",
        request_id=request_id,
        error_id=error_id,
        exception_type=type(exc).__name__,
    ).opt(exception=exc).error("Unhandled HTTP request exception")

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "request_id": request_id,
            "error_id": error_id,
        },
        headers={REQUEST_ID_HEADER: request_id},
    )
