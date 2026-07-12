import functools
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from loguru import logger

from app.db.models import Project, ProjectWidget
from app.utils import normalize_origin


# TODO: 这里查库的 IO 可能性能有消耗，MVP 阶段不加 Cache
class WidgetScopedCORSMiddleware:
    """
    visitor 侧 widget 请求 API 的 widget scoped CORS 中间件；

    该中间件只处理 /visitor/project/{project_uid}/widget/{widget_uid}/... 的请求，
    """

    # 路径匹配正则
    _path_pattern = re.compile(
        r"^/visitor/project/(?P<project_uid>[^/]+)/widget/(?P<widget_uid>[^/]+)(?:/|$)"
    )

    def __init__(
        self,
        app: ASGIApp,
        *,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.app = app
        self.session_factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """中间件入口函数，处理 CORS 逻辑"""
        # logger.debug(f"触发 custom middleware 处理: {scope.get('path')}")
        if scope["type"] != "http":  # 只处理 HTTP 请求
            await self.app(scope, receive, send)
            return

        # 匹配请求路径
        match = self._path_pattern.match(scope.get("path", ""))
        if not match:
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        headers = Headers(scope=scope)
        origin = headers.get("origin")

        if not origin:
            await self.app(scope, receive, send)
            return

        # 处理预检请求
        if method == "OPTIONS" and "access-control-request-method" in headers:
            response = await self.preflight_response(
                match=match,
                request_headers=headers,
            )
            await response(scope, receive, send)
            return

        await self.simple_response(
            scope, receive, send, request_headers=headers, match=match
        )

    async def _is_allowed_origin(
        self,
        *,
        project_uid: str,
        widget_uid: str,
        request_origin: str,
    ) -> bool:
        """解析请求 origin，判断是否允许"""
        try:
            # 标准化 origin
            normalized_origin = normalize_origin(request_origin)
        except ValueError:
            return False

        # 先读取部署配置，再用普通 Python 值比较，避免 Result 被重复消费。
        stmt = (
            select(ProjectWidget.site_origin)
            .join(Project, Project.id == ProjectWidget.project_id)
            .where(
                Project.uid == project_uid,
                ProjectWidget.uid == widget_uid,
                ProjectWidget.is_enabled.is_(True),
            )
        )
        async with self.session_factory() as session:
            configured_origin = await session.scalar(stmt)

        # 文本比较；请求 origin 和允许 origin 是否一致
        is_allowed = configured_origin == normalized_origin
        logger.debug(
            "Widget CORS Origin 校验: request_origin={}, configured_origin={}, allowed={}",
            normalized_origin,
            configured_origin,
            is_allowed,
        )
        return is_allowed

    async def preflight_response(
        self, *, match: re.Match, request_headers: Headers
    ) -> Response:
        """预检查请求响应"""
        # 解析请求头
        requested_origin = request_headers["origin"]
        requested_headers = request_headers.get("access-control-request-headers")

        preflight_headers = {
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        }
        failures: list[str] = []

        # 检查 origin 是否允许
        if await self._is_allowed_origin(
            project_uid=match.group("project_uid"),
            widget_uid=match.group("widget_uid"),
            request_origin=requested_origin,
        ):
            # logger.debug("preflight 请求 CORS 通过")
            preflight_headers["Access-Control-Allow-Origin"] = requested_origin
        else:
            failures.append("origin")

        # 处理 Access-Control-Allow-Headers
        if requested_headers is not None:
            preflight_headers["Access-Control-Allow-Headers"] = requested_headers

        if failures:
            # 失败响应
            # logger.debug("preflight 请求 CORS 失败")
            failure_text = "Disallowed CORS " + ", ".join(failures)
            return PlainTextResponse(
                failure_text, status_code=400, headers=preflight_headers
            )

        return Response(status_code=204, headers=preflight_headers)

    async def simple_response(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        request_headers: Headers,
        match: re.Match,
    ) -> None:
        """
        简单响应，处理非预检请求
        复用 CORSMiddleware 实现
        """
        # 提前查询 DB，避免在底层 send 管道中执行慢速 IO
        requested_origin = request_headers.get("origin", "")
        is_allowed = await self._is_allowed_origin(
            project_uid=match.group("project_uid"),
            widget_uid=match.group("widget_uid"),
            request_origin=requested_origin,
        )

        send = functools.partial(
            self.send,
            send=send,
            requested_origin=requested_origin,
            is_allowed=is_allowed,
        )
        await self.app(scope, receive, send)

    async def send(
        self, message: Message, send: Send, requested_origin: str, is_allowed: bool
    ) -> None:
        if message["type"] != "http.response.start":
            await send(message)
            return

        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)

        if is_allowed:
            self.allow_explicit_origin(headers, requested_origin)
        else:
            # Vary: Origin 响应头，防止 CDN 错误缓存
            headers.add_vary_header("Origin")

        # 继续发送响应
        await send(message)

    @staticmethod
    def allow_explicit_origin(headers: MutableHeaders, origin: str) -> None:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Expose-Headers"] = "Retry-After"
        headers.add_vary_header("Origin")
