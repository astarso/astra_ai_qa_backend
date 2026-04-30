"""Role-based access control guard."""

from typing import Any

import httpx
import jwt
from litestar import get
from litestar.connection import ASGIConnection
from litestar.exceptions import HTTPException
from litestar.handlers.base import BaseRouteHandler
from litestar.status_codes import HTTP_403_FORBIDDEN

from app.config import settings

_jwks_cache: dict[str, str] = {}


async def _get_public_key(issuer: str) -> Any:
    kid = issuer
    if kid in _jwks_cache:
        return _jwks_cache[kid]
    jwks_url = f"{issuer.rstrip('/')}/protocol/openid-connect/certs"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url, timeout=10)
        response.raise_for_status()
        jwks = response.json()
    for key in jwks.get("keys", []):
        if key.get("use") == "sig" and key.get("alg"):
            from jwt import PyJWK
            _jwks_cache[kid] = PyJWK.from_dict(key).key
            return _jwks_cache[kid]
    raise ValueError("No suitable signing key found in JWKS")


async def _extract_roles_from_token(token: str) -> list[str]:
    try:
        public_key = await _get_public_key(settings.oidc_issuer_url)
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer_url,
            options={"verify_exp": False},
        )
        realm_access = claims.get("realm_access", {})
        roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
        custom_roles = claims.get("roles", [])
        if isinstance(custom_roles, list):
            roles.extend(custom_roles)
        return roles
    except jwt.InvalidTokenError:
        return []


class RBACGuard:
    def __init__(self, *required_roles: str) -> None:
        self.required_roles = set(required_roles)

    async def __call__(
        self,
        connection: ASGIConnection,
        route_handler: BaseRouteHandler,
    ) -> None:
        if settings.debug:
            return
        user = getattr(connection.state, "user", None)
        if user is None:
            auth_header = connection.headers.get("authorization", "")
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                user_roles = await _extract_roles_from_token(parts[1])
            else:
                user_roles = []
        else:
            user_roles = getattr(user, "roles", [])
        if not self.required_roles:
            return
        if not any(role in user_roles for role in self.required_roles):
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(self.required_roles)}",
            )


def require_role(*roles: str) -> RBACGuard:
    return RBACGuard(*roles)
