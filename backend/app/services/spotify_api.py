from datetime import datetime, timezone
from typing import Any
import urllib.parse

import requests
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.repositories.user_repository import get_user_spotify_auth, save_user_spotify_tokens


SPOTIFY_API_BASE = "https://api.spotify.com/v1"


def describe_spotify_error(payload: Any, status_code: int, context: str) -> str:
    if isinstance(payload, dict):
        if isinstance(payload.get("error_description"), str):
            return f"Spotify {context} failed ({status_code}): {payload['error_description']}"

        error_obj = payload.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            reason = error_obj.get("reason")
            if isinstance(message, str) and isinstance(reason, str):
                return f"Spotify {context} failed ({status_code}): {message} ({reason})"
            if isinstance(message, str):
                return f"Spotify {context} failed ({status_code}): {message}"

        if isinstance(error_obj, str):
            return f"Spotify {context} failed ({status_code}): {error_obj}"

    return f"Spotify {context} failed with status {status_code}."


def exchange_code_for_token(code: str, redirect_uri: str) -> dict[str, Any]:
    token_url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "client_secret": settings.SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post(token_url, data=data, timeout=20)
    payload = response.json()

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=describe_spotify_error(payload, response.status_code, "token exchange"),
        )

    return payload


def refresh_spotify_access_token(refresh_token: str) -> dict[str, Any]:
    token_url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "client_secret": settings.SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post(token_url, data=data, timeout=20)
    payload = response.json()

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=describe_spotify_error(payload, response.status_code, "token refresh"),
        )

    return payload


def spotify_get(
    path: str,
    access_token: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, params=params, timeout=20)
    payload = response.json() if response.content else {}

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=describe_spotify_error(payload, response.status_code, f"request to {path}"),
        )

    return payload


def spotify_get_paginated_items(
    path: str,
    access_token: str,
    params: dict[str, Any] | None = None,
    item_key: str = "items",
    max_pages: int = 1,
) -> list[dict[str, Any]]:
    next_path = path
    next_params = dict(params or {})
    collected: list[dict[str, Any]] = []

    for _ in range(max_pages):
        payload = spotify_get(next_path, access_token, next_params)
        items = payload.get(item_key, [])
        if isinstance(items, list):
            collected.extend([item for item in items if isinstance(item, dict)])

        next_url = payload.get("next")
        if not isinstance(next_url, str) or not next_url:
            break

        parsed = urllib.parse.urlsplit(next_url)
        if not parsed.path.startswith("/v1"):
            break

        next_path = parsed.path[len("/v1") :]
        next_params = dict(urllib.parse.parse_qsl(parsed.query))

    return collected


def is_expired(expires_at: Any) -> bool:
    if not expires_at:
        return True

    if isinstance(expires_at, str):
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            return True
    elif isinstance(expires_at, datetime):
        expires_dt = expires_at
    else:
        return True

    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=timezone.utc)

    return expires_dt <= datetime.now(timezone.utc)


async def get_valid_user_spotify_access_token(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> str:
    spotify_auth = await get_user_spotify_auth(db, user_id)
    if not spotify_auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or Spotify is not linked",
        )

    access_token = spotify_auth.get("access_token")
    refresh_token = spotify_auth.get("refresh_token")
    expires_at = spotify_auth.get("expires_at")

    if not access_token and not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spotify tokens missing for user. Link Spotify first.",
        )

    if is_expired(expires_at):
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Spotify access token expired and no refresh token is stored.",
            )

        refreshed_payload = refresh_spotify_access_token(refresh_token)
        await save_user_spotify_tokens(db, user_id, refreshed_payload)
        access_token = refreshed_payload.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to obtain valid Spotify access token.",
        )

    return access_token
