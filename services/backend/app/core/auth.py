from dataclasses import dataclass
from functools import lru_cache

import jwt
import psycopg
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.db import RlsContext, rls_transaction

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    clerk_user_id: str
    email: str
    role: str

    @property
    def rls(self) -> RlsContext:
        return RlsContext(user_id=self.id, role=self.role, clerk_user_id=self.clerk_user_id)


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = get_settings().CLERK_JWKS_URL
    if not url:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "CLERK_JWKS_URL is not configured")
    return jwt.PyJWKClient(url, cache_keys=True)


def _verify_clerk_token(token: str) -> str:
    settings = get_settings()
    try:
        key = _jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER or None,
            options={"require": ["exp", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session token") from exc

    parties = {p.strip() for p in settings.CLERK_AUTHORIZED_PARTIES.split(",") if p.strip()}
    if claims.get("azp") and parties and claims["azp"] not in parties:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Untrusted token origin")
    return claims["sub"]


def dev_mock_auth_enabled() -> bool:
    settings = get_settings()
    return settings.ENABLE_DEV_MOCK_AUTH and settings.ENVIRONMENT == "development"


def _dev_mock_user(user_id: str, role: str | None) -> CurrentUser:
    """
    Offline testing only: trusts X-Dev-User-Id (an existing, active `users` row). The row's
    own role drives RLS, so a mismatching X-Dev-User-Role is rejected, not escalated.
    """
    try:
        with rls_transaction(RlsContext(user_id=user_id)) as conn:
            row = conn.execute(
                "select id::text, clerk_user_id, email, role::text, is_active"
                " from users where id = %s::uuid",
                (user_id,),
            ).fetchone()
    except psycopg.errors.InvalidTextRepresentation:
        row = None
    if not row or not row["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown or inactive dev user")
    if role and role != row["role"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "X-Dev-User-Role does not match the user")
    return CurrentUser(row["id"], row["clerk_user_id"], row["email"], row["role"])


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    dev_user_id: str | None = Header(default=None, alias="X-Dev-User-Id", include_in_schema=False),
    dev_user_role: str | None = Header(
        default=None, alias="X-Dev-User-Role", include_in_schema=False
    ),
) -> CurrentUser:
    if creds is None and dev_user_id and dev_mock_auth_enabled():
        return _dev_mock_user(dev_user_id, dev_user_role)
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    clerk_user_id = _verify_clerk_token(creds.credentials)

    with rls_transaction(RlsContext(clerk_user_id=clerk_user_id)) as conn:
        row = conn.execute(
            "select id::text, clerk_user_id, email, role::text, is_active"
            " from users where clerk_user_id = %s",
            (clerk_user_id,),
        ).fetchone()
    if not row or not row["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User is not provisioned or is inactive")
    return CurrentUser(row["id"], row["clerk_user_id"], row["email"], row["role"])


def require_roles(*roles: str):
    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return dependency
