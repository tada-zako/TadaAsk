import re
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db.models import Project, ProjectWidget
from app.utils import normalize_origin


class WidgetScopedCORSMiddleware:
    """
    Scoped CORS middleware for visitor widget APIs.

    Global CORSMiddleware remains responsible for admin/dev routes. This middleware
    only handles /visitor/project/{project_uid}/widget/{widget_uid}/... requests.
    """

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
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        match = self._path_pattern.match(scope.get("path", ""))
        if not match:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")
        if not origin:
            await self.app(scope, receive, send)
            return

        allowed_origin = await self._resolve_allowed_origin(
            project_uid=match.group("project_uid"),
            widget_uid=match.group("widget_uid"),
            request_origin=origin,
        )

        if self._is_preflight_request(scope=scope, headers=headers):
            response = self._preflight_response(
                allowed_origin=allowed_origin,
                request_headers=headers,
            )
            await response(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start" and allowed_origin:
                self._set_cors_headers(
                    MutableHeaders(scope=message),
                    allowed_origin=allowed_origin,
                )
            await send(message)

        await self.app(scope, receive, send_with_cors)

    async def _resolve_allowed_origin(
        self,
        *,
        project_uid: str,
        widget_uid: str,
        request_origin: str,
    ) -> str | None:
        try:
            normalized_origin = normalize_origin(request_origin)
        except ValueError:
            return None

        stmt = (
            select(ProjectWidget.id)
            .join(Project, Project.id == ProjectWidget.project_id)
            .where(
                Project.uid == project_uid,
                ProjectWidget.uid == widget_uid,
                ProjectWidget.site_origin == normalized_origin,
                ProjectWidget.is_enabled.is_(True),
            )
        )
        async with self.session_factory() as session:
            result = await session.execute(stmt)

        return normalized_origin if result.scalar_one_or_none() is not None else None

    def _is_preflight_request(self, *, scope: Scope, headers: Headers) -> bool:
        return (
            scope["method"] == "OPTIONS"
            and headers.get("access-control-request-method") is not None
        )

    def _preflight_response(
        self, *, allowed_origin: str | None, request_headers: Headers
    ) -> Response:
        if not allowed_origin:
            return PlainTextResponse("Origin is not allowed for this widget", 403)

        headers = {
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        }
        requested_headers = request_headers.get("access-control-request-headers")
        if requested_headers:
            headers["Access-Control-Allow-Headers"] = requested_headers

        return Response(status_code=204, headers=headers)

    def _set_cors_headers(
        self, response_headers: MutableHeaders, *, allowed_origin: str
    ) -> None:
        response_headers["Access-Control-Allow-Origin"] = allowed_origin
        self._append_vary(response_headers, ["Origin"])

    def _append_vary(
        self, response_headers: MutableHeaders, values: Sequence[str]
    ) -> None:
        existing = response_headers.get("Vary")
        if not existing:
            response_headers["Vary"] = ", ".join(values)
            return

        existing_values = {value.strip().lower() for value in existing.split(",")}
        missing = [value for value in values if value.lower() not in existing_values]
        if missing:
            response_headers["Vary"] = f"{existing}, {', '.join(missing)}"
