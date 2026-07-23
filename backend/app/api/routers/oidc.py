import secrets
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import cookie_transport, get_jwt_strategy
from app.config import get_settings
from app.db import get_db
from app.models.system_settings import SystemSettings
from app.models.user import User
from app.services.encryption import decrypt

router = APIRouter(prefix="/auth/oidc", tags=["oidc"])

_STATE_COOKIE = "oidc_state"


async def _get_settings_row(db: AsyncSession) -> SystemSettings | None:
    result = await db.execute(select(SystemSettings).limit(1))
    return result.scalar_one_or_none()


async def _discover(issuer_url: str) -> dict:
    discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(discovery_url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail="Could not reach the identity provider"
        ) from exc


@router.get("/config")
async def public_oidc_config(db: AsyncSession = Depends(get_db)):
    """Unauthenticated — just enough for the login page to render a button."""
    row = await _get_settings_row(db)
    if row is None or not row.oidc_enabled:
        return {"enabled": False}
    return {"enabled": True, "display_name": row.oidc_display_name or "SSO"}


@router.get("/login")
async def oidc_login(request: Request, db: AsyncSession = Depends(get_db)):
    row = await _get_settings_row(db)
    if row is None or not row.oidc_enabled:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    discovery = await _discover(row.oidc_issuer_url)
    state = secrets.token_urlsafe(32)
    params = {
        "response_type": "code",
        "client_id": row.oidc_client_id,
        "redirect_uri": str(request.url_for("oidc_callback")),
        "scope": "openid email profile",
        "state": state,
    }
    response = RedirectResponse(f"{discovery['authorization_endpoint']}?{urlencode(params)}")
    response.set_cookie(
        _STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
    )
    return response


@router.get("/callback", name="oidc_callback")
async def oidc_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    row = await _get_settings_row(db)
    if row is None or not row.oidc_enabled:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    cookie_state = request.cookies.get(_STATE_COOKIE)
    if not cookie_state or not secrets.compare_digest(cookie_state, state):
        raise HTTPException(status_code=400, detail="Invalid or expired OIDC state")

    discovery = await _discover(row.oidc_issuer_url)
    client_secret = decrypt(row.oidc_client_secret_encrypted)
    redirect_uri = str(request.url_for("oidc_callback"))

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                discovery["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": row.oidc_client_id,
                    "client_secret": client_secret,
                },
            )
            if token_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="OIDC token exchange failed")
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=400, detail="OIDC provider returned no access token"
                )

            userinfo_resp = await client.get(
                discovery["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch OIDC user info")
            userinfo = userinfo_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail="Could not reach the identity provider"
        ) from exc

    email = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="OIDC provider did not return an email")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=email,
            # Never used for password login -- OIDC users authenticate via the IdP only.
            hashed_password=secrets.token_hex(32),
            full_name=userinfo.get("name", ""),
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    token = await get_jwt_strategy().write_token(user)
    cors_origins = get_settings().cors_origins
    frontend_base = cors_origins[0].rstrip("/") if cors_origins else ""
    response = RedirectResponse(f"{frontend_base}/cases")
    response.delete_cookie(_STATE_COOKIE)
    return cookie_transport._set_login_cookie(response, token)
