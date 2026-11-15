"""aiohttp application factory + standalone runner for the CAS server."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from aiohttp import web

from ccbt.cas_server.auth import TokenAuth
from ccbt.cas_server.routes import AUTH_KEY, SECRET_KEY, STORE_KEY, register_routes
from ccbt.cas_server.store import CasStore


def parse_token_config(spec: Optional[str]) -> dict[str, set[str]]:
    """Parse "token:read,write;token2:read" into a token->scopes map."""
    out: dict[str, set[str]] = {}
    if not spec:
        return out
    for raw_part in spec.split(";"):
        part = raw_part.strip()
        if not part:
            continue
        token, _, scopes = part.partition(":")
        out[token.strip()] = {
            s.strip() for s in scopes.split(",") if s.strip() in ("read", "write")
        } or {"read"}
    return out


def create_app(
    root: Path,
    *,
    tokens: Optional[dict[str, set[str]]] = None,
    secret: Optional[bytes] = None,
) -> web.Application:
    """Public function."""
    app = web.Application(client_max_size=1024 * 1024 * 1024)
    store = CasStore(Path(root))
    app[STORE_KEY] = store
    app[AUTH_KEY] = TokenAuth(tokens)
    app[SECRET_KEY] = secret or secrets.token_bytes(32)

    async def _close_store(_app: web.Application) -> None:
        store.close()

    app.on_cleanup.append(_close_store)
    register_routes(app)
    return app


def run_server(
    root: Path,
    host: str = "127.0.0.1",
    port: int = 8470,
    *,
    tokens: Optional[dict[str, set[str]]] = None,
) -> None:
    """Public function."""
    web.run_app(create_app(root, tokens=tokens), host=host, port=port)
