from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SAFE_METHODS = {"GET", "HEAD"}


class NoStoreMiddleware:
    """Añade `Cache-Control: no-store` a toda respuesta bajo `prefix`, también a las de error.

    Middleware ASGI puro (no BaseHTTPMiddleware) para no alterar el streaming ni las BackgroundTasks.
    """

    def __init__(self, app: ASGIApp, prefix: str, cacheable_get_paths: frozenset[str] = frozenset()) -> None:
        self.app = app
        self.prefix = prefix
        self.cacheable_get_paths = cacheable_get_paths

    def _applies(self, scope: Scope) -> bool:
        path: str = scope["path"]
        if not (path == self.prefix or path.startswith(f"{self.prefix}/")):
            return False
        return not (scope["method"] in _SAFE_METHODS and path in self.cacheable_get_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._applies(scope):
            await self.app(scope, receive, send)
            return

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, _send)
