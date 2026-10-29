from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from app.core.config import get_settings


@dataclass(frozen=True)
class RlsContext:
    user_id: str | None = None
    role: str | None = None
    clerk_user_id: str | None = None


SYSTEM_CONTEXT = RlsContext(role="admin")


def _conninfo() -> str:
    url = get_settings().DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not set (services/backend/.env.backend.local)")
    return url


@contextmanager
def rls_transaction(ctx: RlsContext) -> Iterator[psycopg.Connection]:
    """
    One transaction with the RLS session settings from migrations 0001/0002 applied.
    Tables use FORCE RLS, so every query must run inside this context.
    """
    with psycopg.connect(_conninfo(), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute(
                "select set_config('app.current_user_id', %s, true),"
                " set_config('app.current_user_role', %s, true),"
                " set_config('app.current_clerk_user_id', %s, true)",
                (ctx.user_id or "", ctx.role or "", ctx.clerk_user_id or ""),
            )
            yield conn
