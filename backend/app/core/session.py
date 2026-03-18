import base64
import binascii
import hashlib
import hmac
import json
from http.cookies import SimpleCookie
from typing import Any

from starlette.datastructures import MutableHeaders


class SessionCookieMiddleware:
    def __init__(
        self,
        app: Any,
        secret_key: str,
        session_cookie: str = "session",
        max_age: int = 14 * 24 * 60 * 60,
        same_site: str = "lax",
        https_only: bool = False,
    ) -> None:
        self.app = app
        self.secret_key = secret_key.encode("utf-8")
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.same_site = same_site
        self.https_only = https_only

    def _sign(self, payload: str) -> str:
        digest = hmac.new(self.secret_key, payload.encode("utf-8"), hashlib.sha256)
        return digest.hexdigest()

    def _serialize_session(self, session: dict[str, Any]) -> str:
        payload = json.dumps(session, separators=(",", ":"), sort_keys=True).encode("utf-8")
        encoded_payload = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
        signature = self._sign(encoded_payload)
        return f"{encoded_payload}.{signature}"

    def _deserialize_session(self, value: str) -> dict[str, Any]:
        try:
            encoded_payload, signature = value.rsplit(".", 1)
        except ValueError:
            return {}

        expected_signature = self._sign(encoded_payload)
        if not hmac.compare_digest(signature, expected_signature):
            return {}

        try:
            padding = "=" * (-len(encoded_payload) % 4)
            payload = base64.urlsafe_b64decode(f"{encoded_payload}{padding}")
            session = json.loads(payload.decode("utf-8"))
        except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
            return {}

        return session if isinstance(session, dict) else {}

    def _build_set_cookie(self, value: str) -> str:
        parts = [
            f"{self.session_cookie}={value}",
            "HttpOnly",
            "Path=/",
            f"Max-Age={self.max_age}",
            f"SameSite={self.same_site}",
        ]

        if self.https_only:
            parts.append("Secure")

        return "; ".join(parts)

    def _build_clear_cookie(self) -> str:
        parts = [
            f"{self.session_cookie}=",
            "HttpOnly",
            "Path=/",
            "Max-Age=0",
            f"SameSite={self.same_site}",
        ]

        if self.https_only:
            parts.append("Secure")

        return "; ".join(parts)

    def _extract_cookie_value(self, scope: dict[str, Any]) -> str | None:
        raw_cookie_header = None
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"cookie":
                raw_cookie_header = header_value.decode("latin-1")
                break

        if not raw_cookie_header:
            return None

        parsed_cookie = SimpleCookie()
        parsed_cookie.load(raw_cookie_header)
        morsel = parsed_cookie.get(self.session_cookie)
        return morsel.value if morsel else None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_session_cookie = self._extract_cookie_value(scope)
        initial_session = self._deserialize_session(raw_session_cookie) if raw_session_cookie else {}
        scope["session"] = dict(initial_session)

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                current_session = scope.get("session", {})

                if current_session:
                    if current_session != initial_session or raw_session_cookie is None:
                        headers.append(
                            "Set-Cookie",
                            self._build_set_cookie(self._serialize_session(current_session)),
                        )
                elif raw_session_cookie is not None:
                    headers.append("Set-Cookie", self._build_clear_cookie())

            await send(message)

        await self.app(scope, receive, send_wrapper)
