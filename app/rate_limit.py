"""Limitador de frequ?ncia para reconhecimento facial."""

import math
import os
import threading
import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse


class RecognitionRateLimitMiddleware:
    def __init__(self, app):
        self.app = app

        self.enabled = (
            os.environ.get("FACEREC_RATE_LIMIT_ENABLED", "0") == "1"
        )

        self.max_requests = max(
            1, int(os.environ.get("FACEREC_RATE_LIMIT_MAX", "10"))
        )

        self.window_seconds = max(
            1, int(os.environ.get("FACEREC_RATE_LIMIT_WINDOW", "5"))
        )

        self.global_max = max(
            self.max_requests,
            int(
                os.environ.get(
                    "FACEREC_RATE_LIMIT_GLOBAL_MAX",
                    str(self.max_requests * 5),
                )
            ),
        )

        self.events = defaultdict(deque)
        self.global_events = deque()
        self.lock = threading.Lock()

    @staticmethod
    def client_key(scope):
        headers = {
            key.lower(): value
            for key, value in scope.get("headers", [])
        }

        client_type = headers.get(
            b"x-facerec-client", b""
        ).decode("ascii", errors="ignore").strip().lower()

        if client_type not in {"web", "android"}:
            client_type = "other"

        client = scope.get("client")
        ip = str(client[0]) if client else "unknown"

        return (ip, client_type)

    def clean_events(self, events, now):
        while (
            events
            and now - events[0] >= self.window_seconds
        ):
            events.popleft()

    def retry_after(self, events, now):
        return max(
            1,
            math.ceil(
                self.window_seconds - (now - events[0])
            ),
        )

    async def __call__(self, scope, receive, send):
        if (
            not self.enabled
            or scope["type"] != "http"
            or scope.get("path") != "/reconhecer"
            or scope.get("method") != "POST"
        ):
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        key = self.client_key(scope)

        with self.lock:
            events = self.events[key]

            self.clean_events(events, now)
            self.clean_events(self.global_events, now)

            client_blocked = (
                len(events) >= self.max_requests
            )

            global_blocked = (
                len(self.global_events) >= self.global_max
            )

            if client_blocked or global_blocked:
                waits = []

                if client_blocked:
                    waits.append(
                        self.retry_after(events, now)
                    )

                if global_blocked:
                    waits.append(
                        self.retry_after(
                            self.global_events, now
                        )
                    )

                retry_after = max(waits)
                blocked = True
            else:
                events.append(now)
                self.global_events.append(now)
                retry_after = 0
                blocked = False

            # Remove chaves inativas para evitar crescimento
            # indefinido do dicionario de clientes.
            for old_key in list(self.events):
                self.clean_events(
                    self.events[old_key], now
                )
                if not self.events[old_key]:
                    del self.events[old_key]

        if blocked:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Muitas requisi??es. "
                        "Aguarde e tente novamente."
                    )
                },
                headers={
                    "Retry-After": str(retry_after)
                },
            )

            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
