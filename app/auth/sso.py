"""OIDC SSO authentication guard and login handlers."""

from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from litestar import get
from litestar.connection import ASGIConnection
from litestar.exceptions import HTTPException
from litestar.handlers.base import BaseRouteHandler
from litestar.response import Redirect
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_502_BAD_GATEWAY

from app.config import settings


@dataclass
class AuthenticatedUser:
    """Authenticated user info extracted from JWT."""

    sub: str
    email: str | None
    name: str | None
    roles: list[str]

    @classmethod
    def from_jwt_claims(cls, claims: dict[str, Any]) -> "AuthenticatedUser":
        realm_access = claims.get("realm_access", {})
        roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
        custom_roles = claims.get("roles", [])
        if isinstance(custom_roles, list):
            roles.extend(custom_roles)
        return cls(
            sub=claims.get("sub", ""),
            email=claims.get("email"),
            name=claims.get("name") or claims.get("preferred_username"),
            roles=roles,
        )

_jwks_cache: dict[str, str] = {}


async def _get_public_key(issuer: str) -> str:
    kid = issuer  # Use issuer as cache key since there's one key per issuer
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


async def sso_auth_guard(
    connection: ASGIConnection,
    route_handler: BaseRouteHandler,
) -> None:
    path = connection.url.path
    if path in ("/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/callback"):
        return
    if settings.debug:
        connection.state.user = AuthenticatedUser(
            sub="debug-user",
            email="debug@example.com",
            name="Debug User",
            roles=["admin"],
        )
        return
    auth_header = connection.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
        )
    token = parts[1]
    try:
        public_key = await _get_public_key(settings.oidc_issuer_url)
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer_url,
        )
        connection.state.user = AuthenticatedUser.from_jwt_claims(claims)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


@get(path="/api/v1/auth/login")
async def oidc_login_handler() -> Redirect:
    redirect_url = f"{settings.oidc_issuer_url}/protocol/openid-connect/auth"
    params = {
        "client_id": settings.oidc_client_id,
        "redirect_uri": f"{settings.oidc_issuer_url}/auth-callback",
        "response_type": "code",
        "scope": "openid profile email",
    }
    import urllib.parse
    url = f"{redirect_url}?{urllib.parse.urlencode(params)}"
    return Redirect(path=url)


@get(path="/api/v1/auth/callback")
async def oidc_callback_handler(code: str = "", error: str = "") -> dict:
    if error:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"OIDC error: {error}",
        )

    if not code:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    token_url = f"{settings.oidc_issuer_url}/protocol/openid-connect/token"
    redirect_uri = f"{settings.oidc_issuer_url}/auth-callback"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret.get_secret_value(),
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=HTTP_502_BAD_GATEWAY,
                detail=f"Token exchange failed: {response.text}",
            )

        token_response = response.json()

    access_token = token_response.get("access_token")
    id_token = token_response.get("id_token")
    refresh_token = token_response.get("refresh_token")

    if not access_token or not id_token:
        raise HTTPException(
            status_code=HTTP_502_BAD_GATEWAY,
            detail="Invalid token response from IdP",
        )

    public_key = await _get_public_key(settings.oidc_issuer_url)
    claims = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256", "ES256"],
        audience=settings.oidc_client_id,
        issuer=settings.oidc_issuer_url,
    )

    user = AuthenticatedUser.from_jwt_claims(claims)

    return {
        "access_token": access_token,
        "id_token": id_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": token_response.get("expires_in", 3600),
        "user": {
            "sub": user.sub,
            "email": user.email,
            "name": user.name,
            "roles": user.roles,
        },
    }
