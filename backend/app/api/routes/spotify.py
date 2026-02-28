from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.database import get_database
from app.repositories.spotify_repository import create_spotify_ingestion_snapshot
from app.repositories.user_repository import get_user_spotify_auth, save_user_spotify_tokens
import urllib.parse
import requests


router = APIRouter()
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


def _exchange_code_for_token(code: str) -> dict[str, Any]:
    token_url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "client_secret": settings.SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post(token_url, data=data, timeout=20)
    payload = response.json()

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=payload)

    return payload


def _refresh_spotify_access_token(refresh_token: str) -> dict[str, Any]:
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
        raise HTTPException(status_code=response.status_code, detail=payload)

    return payload


def _spotify_get(
    path: str,
    access_token: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{SPOTIFY_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, params=params, timeout=20)
    payload = response.json() if response.content else {}

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=payload)

    return payload


def _is_expired(expires_at: Any) -> bool:
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

@router.get("/spotify/login")
def spotify_login():
    scope = "user-read-recently-played user-top-read playlist-modify-private"
    
    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": scope,
    }

    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
    
    return RedirectResponse(url)



@router.get("/spotify/callback")
def spotify_callback(code: str | None = None, error: str | None = None):
    if error:
        return {"error": error, "message": "Spotify authorization was denied or failed"}
    if not code:
        return {"error": "no_code", "message": "No authorization code received from Spotify"}
    return {"code": code, "message": "Copy this code and use /auth/spotify/exchange with your user_id"}


@router.get("/spotify/exchange")
async def spotify_exchange(
    code: str,
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    token_payload = _exchange_code_for_token(code)
    updated_user = await save_user_spotify_tokens(db, user_id, token_payload)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {
        "stored": True,
        "user_id": user_id,
        "token_type": token_payload.get("token_type"),
        "scope": token_payload.get("scope"),
        "expires_in": token_payload.get("expires_in"),
    }


@router.get("/spotify/exchange-from-redirect")
async def spotify_exchange_from_redirect(
    redirect_url: str,
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(redirect_url)
    query = urllib.parse.parse_qs(parsed.query)
    code_values = query.get("code", [])
    code = code_values[0] if code_values else None

    if not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No code found in redirect_url",
        )

    token_payload = _exchange_code_for_token(code)
    updated_user = await save_user_spotify_tokens(db, user_id, token_payload)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {
        "stored": True,
        "user_id": user_id,
        "token_type": token_payload.get("token_type"),
        "scope": token_payload.get("scope"),
        "expires_in": token_payload.get("expires_in"),
    }


@router.post("/spotify/ingest")
async def spotify_ingest(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
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

    if _is_expired(expires_at):
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Spotify access token expired and no refresh token is stored.",
            )
        refreshed_payload = _refresh_spotify_access_token(refresh_token)
        await save_user_spotify_tokens(db, user_id, refreshed_payload)
        access_token = refreshed_payload.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to obtain valid Spotify access token.",
        )

    top_tracks_payload = _spotify_get(
        "/me/top/tracks",
        access_token,
        params={"limit": 50, "time_range": "medium_term"},
    )
    top_artists_payload = _spotify_get(
        "/me/top/artists",
        access_token,
        params={"limit": 50, "time_range": "medium_term"},
    )
    recently_played_payload = _spotify_get(
        "/me/player/recently-played",
        access_token,
        params={"limit": 50},
    )

    top_tracks = top_tracks_payload.get("items", [])
    track_ids = [track.get("id") for track in top_tracks if track.get("id")]

    audio_features_payload: list[dict[str, Any]] = []
    for i in range(0, len(track_ids), 100):
        chunk_ids = track_ids[i : i + 100]
        if not chunk_ids:
            continue
        features_response = _spotify_get(
            "/audio-features",
            access_token,
            params={"ids": ",".join(chunk_ids)},
        )
        features = features_response.get("audio_features", [])
        audio_features_payload.extend([f for f in features if f])

    snapshot_id = await create_spotify_ingestion_snapshot(
        db,
        user_id,
        {
            "top_tracks": top_tracks,
            "top_artists": top_artists_payload.get("items", []),
            "recently_played": recently_played_payload.get("items", []),
            "audio_features": audio_features_payload,
            "source": "spotify_api_v1",
        },
    )

    if snapshot_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {
        "stored": True,
        "user_id": user_id,
        "snapshot_id": snapshot_id,
        "counts": {
            "top_tracks": len(top_tracks),
            "top_artists": len(top_artists_payload.get("items", [])),
            "recently_played": len(recently_played_payload.get("items", [])),
            "audio_features": len(audio_features_payload),
        },
    }
