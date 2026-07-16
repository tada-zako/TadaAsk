from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class AdminScopedCORSMiddleware:
    """
    仅为 Admin API 应用可配置的跨域策略，避免影响 Visitor Widget；
    复用 CORSMiddleware 逻辑，只对 request.path 进行选择性处理
    """

    def __init__(self, app: ASGIApp, *, allow_origins: list[str]) -> None:
        self.app = app
        self.cors_app = CORSMiddleware(
            app,
            allow_origins=allow_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Accept", "Authorization", "Content-Type"],
            expose_headers=["Content-Disposition", "Retry-After"],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] == "http" and (path == "/admin" or path.startswith("/admin/")):
            # 只处理 /admin router API
            await self.cors_app(scope, receive, send)
            return

        await self.app(scope, receive, send)
