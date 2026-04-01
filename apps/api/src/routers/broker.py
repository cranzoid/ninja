"""Broker router — health, session, and Zerodha OAuth endpoints.

Phase 6: Broker adapter health monitoring.
Phase 7: Zerodha OAuth login URL + callback for access_token flow.
"""

from __future__ import annotations

import hashlib
import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from packages.contracts.broker import BrokerHealth, BrokerSession

from ..dependencies import get_app_state
from ..schemas.responses import APIResponse
from ..services.app_state import AppState

router = APIRouter(prefix="/api/broker", tags=["broker"])


@router.get("/health", response_model=APIResponse[BrokerHealth])
async def get_broker_health(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[BrokerHealth]:
    """Return broker adapter health status."""
    if state.mock_broker is None:
        return APIResponse[BrokerHealth](
            success=False, error="No broker adapter configured."
        )

    try:
        health = await state.mock_broker.healthcheck()
        return APIResponse[BrokerHealth](success=True, data=health)
    except Exception as e:
        return APIResponse[BrokerHealth](
            success=False, error=f"Broker health check failed: {e}"
        )


@router.get("/session", response_model=APIResponse[BrokerSession])
async def get_broker_session(
    state: Annotated[AppState, Depends(get_app_state)],
) -> APIResponse[BrokerSession]:
    """Return current broker session info (without credentials)."""
    if state.mock_broker is None:
        return APIResponse[BrokerSession](
            success=False, error="No broker adapter configured."
        )

    if state.mock_broker._session is None:
        return APIResponse[BrokerSession](
            success=False, error="No active broker session."
        )

    return APIResponse[BrokerSession](
        success=True, data=state.mock_broker._session
    )


@router.get("/login-url", tags=["zerodha"])
async def zerodha_login_url() -> dict[str, str]:
    """Return the Zerodha login URL to start the OAuth flow.

    Open the returned URL in a browser. After login, Zerodha redirects
    to your registered redirect URL at /api/broker/callback.
    """
    api_key = os.environ.get("ZERODHA_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ZERODHA_API_KEY not set")
    return {
        "login_url": f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
    }


@router.get("/callback", tags=["zerodha"])
async def zerodha_callback(
    request: Request,
    state: Annotated[AppState, Depends(get_app_state)],
) -> dict[str, object]:
    """Zerodha OAuth callback — exchanges request_token for access_token.

    Zerodha redirects here after login with ?request_token=...&status=success.
    The access_token is persisted to disk so authenticate() can reuse it.
    Register this URL (https://yourdomain.com/api/broker/callback) in your
    Zerodha developer console as the redirect URL.
    """
    request_token = request.query_params.get("request_token")
    status = request.query_params.get("status")

    if status != "success" or not request_token:
        return {
            "ok": False,
            "message": f"Zerodha login failed or cancelled (status={status})",
        }

    api_key = os.environ.get("ZERODHA_API_KEY")
    api_secret = os.environ.get("ZERODHA_API_SECRET")
    if not api_key or not api_secret:
        return {
            "ok": False,
            "message": "ZERODHA_API_KEY or ZERODHA_API_SECRET not configured on server",
        }

    checksum = hashlib.sha256(
        f"{api_key}{request_token}{api_secret}".encode()
    ).hexdigest()

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://api.kite.trade/session/token",
            data={
                "api_key": api_key,
                "request_token": request_token,
                "checksum": checksum,
            },
            headers={"X-Kite-Version": "3"},
        )

    if resp.status_code != 200:
        return {
            "ok": False,
            "message": f"Zerodha token exchange failed: {resp.status_code} {resp.text}",
        }

    payload = resp.json()
    session_data = payload.get("data", payload)

    if state.zerodha_adapter is not None:
        state.zerodha_adapter.save_persisted_session(session_data)

    return {"ok": True, "message": "Zerodha session created and stored. You can close this tab."}
