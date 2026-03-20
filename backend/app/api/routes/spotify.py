from datetime import datetime, timezone
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps.auth import (
    get_frontend_origin,
    get_current_user,
    get_optional_current_user,
    pop_spotify_oauth_state,
    set_frontend_origin,
    set_spotify_oauth_state,
)
from app.core.config import settings
from app.core.database import get_database
from app.repositories.spotify_repository import create_spotify_ingestion_snapshot
from app.repositories.user_repository import save_user_spotify_tokens
from app.services.spotify_api import (
    exchange_code_for_token,
    get_valid_user_spotify_access_token,
    spotify_get,
)
import urllib.parse
import requests


router = APIRouter()
legacy_callback_router = APIRouter()
SPOTIFY_REDIRECT_URI_SESSION_KEY = "spotify_redirect_uri"


def _extract_frontend_origin(request: Request) -> str | None:
    candidate = request.headers.get("origin")
    if not candidate:
        referer = request.headers.get("referer")
        if referer:
            parsed_referer = urllib.parse.urlsplit(referer)
            if parsed_referer.scheme and parsed_referer.netloc:
                candidate = f"{parsed_referer.scheme}://{parsed_referer.netloc}"

    if not candidate:
        return None

    parsed_candidate = urllib.parse.urlsplit(candidate)
    parsed_configured = urllib.parse.urlsplit(settings.FRONTEND_URL)
    allowed_hosts = {"localhost", "127.0.0.1"}
    if parsed_configured.hostname:
        allowed_hosts.add(parsed_configured.hostname)

    if parsed_candidate.scheme not in {"http", "https"} or parsed_candidate.hostname not in allowed_hosts:
        return None

    return f"{parsed_candidate.scheme}://{parsed_candidate.netloc}"


def _get_spotify_redirect_uri(request: Request) -> str:
    session_redirect_uri = request.session.get(SPOTIFY_REDIRECT_URI_SESSION_KEY)
    if isinstance(session_redirect_uri, str) and session_redirect_uri:
        return session_redirect_uri
    return settings.SPOTIFY_REDIRECT_URI


def _frontend_callback_redirect(request: Request, params: dict[str, str]) -> RedirectResponse:
    frontend_origin = get_frontend_origin(request) or settings.FRONTEND_URL.rstrip("/")
    frontend_callback_url = f"{frontend_origin.rstrip('/')}/auth/callback"
    query_string = urllib.parse.urlencode(params)
    destination = frontend_callback_url if not query_string else f"{frontend_callback_url}?{query_string}"
    return RedirectResponse(destination)


def _safe_optional_spotify_get(
    path: str,
    access_token: str,
    warnings: list[str],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        return spotify_get(path, access_token, params=params)
    except HTTPException as exc:
        if exc.status_code in {401, 403, 404}:
            warnings.append(str(exc.detail))
            return {}
        raise

@router.get("/spotify/login")
def spotify_login(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    scope = (
        "user-read-recently-played "
        "user-read-currently-playing "
        "user-top-read "
        "user-library-read "
        "playlist-read-private "
        "playlist-modify-private"
    )

    state = secrets.token_urlsafe(32)
    set_spotify_oauth_state(request, state)

    frontend_origin = _extract_frontend_origin(request)
    if frontend_origin:
        set_frontend_origin(request, frontend_origin)

    redirect_uri = str(request.url.replace(path="/auth/spotify/callback", query="", fragment=""))
    request.session[SPOTIFY_REDIRECT_URI_SESSION_KEY] = redirect_uri

    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }

    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)

    return RedirectResponse(url)



async def _spotify_callback_impl(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    current_user: dict[str, Any] | None = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    if not current_user:
        return _frontend_callback_redirect(request, {"error": "session_required"})

    expected_state = pop_spotify_oauth_state(request)
    redirect_uri = _get_spotify_redirect_uri(request)

    if error:
        return _frontend_callback_redirect(request, {"error": error})
    if not code:
        return _frontend_callback_redirect(request, {"error": "no_code"})
    if not state or state != expected_state:
        return _frontend_callback_redirect(request, {"error": "invalid_state"})

    try:
        token_payload = exchange_code_for_token(code, redirect_uri)
    except (HTTPException, requests.RequestException):
        return _frontend_callback_redirect(request, {"error": "token_exchange_failed"})

    updated_user = await save_user_spotify_tokens(db, current_user["_id"], token_payload)
    if not updated_user:
        return _frontend_callback_redirect(request, {"error": "user_not_found"})

    return _frontend_callback_redirect(request, {"status": "linked"})


@router.get("/spotify/callback")
async def spotify_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    current_user: dict[str, Any] | None = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await _spotify_callback_impl(request, code, state, error, current_user, db)


@legacy_callback_router.get("/auth/spotify/callback", include_in_schema=False)
async def spotify_callback_legacy(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    current_user: dict[str, Any] | None = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await _spotify_callback_impl(request, code, state, error, current_user, db)


@router.post("/spotify/ingest")
async def spotify_ingest(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    user_id = current_user["_id"]
    access_token = await get_valid_user_spotify_access_token(db, user_id)

    top_tracks_payload = spotify_get(
        "/me/top/tracks",
        access_token,
        params={"limit": 50, "time_range": "medium_term"},
    )
    top_artists_payload = spotify_get(
        "/me/top/artists",
        access_token,
        params={"limit": 50, "time_range": "medium_term"},
    )
    recently_played_payload = spotify_get(
        "/me/player/recently-played",
        access_token,
        params={"limit": 50},
    )
    warnings: list[str] = []
    saved_tracks_payload = _safe_optional_spotify_get(
        "/me/tracks",
        access_token,
        warnings,
        params={"limit": 50},
    )
    user_playlists_payload = _safe_optional_spotify_get(
        "/me/playlists",
        access_token,
        warnings,
        params={"limit": 20},
    )
    currently_playing_payload = _safe_optional_spotify_get(
        "/me/player/currently-playing",
        access_token,
        warnings,
    )

    top_tracks = top_tracks_payload.get("items", [])
    track_ids = [track.get("id") for track in top_tracks if track.get("id")]

    audio_features_payload: list[dict[str, Any]] = []
    for i in range(0, len(track_ids), 100):
        chunk_ids = track_ids[i : i + 100]
        if not chunk_ids:
            continue
        try:
            features_response = spotify_get(
                "/audio-features",
                access_token,
                params={"ids": ",".join(chunk_ids)},
            )
        except HTTPException as exc:
            # Spotify restricts audio-features access for many new or development-mode apps.
            # Recommendations can still work from top tracks, artists, and recent plays.
            if exc.status_code in {401, 403, 404}:
                warnings.append(str(exc.detail))
                break
            raise

        features = features_response.get("audio_features", [])
        audio_features_payload.extend([f for f in features if f])

    snapshot_id = await create_spotify_ingestion_snapshot(
        db,
        user_id,
        {
            "top_tracks": top_tracks,
            "top_artists": top_artists_payload.get("items", []),
            "recently_played": recently_played_payload.get("items", []),
            "saved_tracks": saved_tracks_payload.get("items", []),
            "user_playlists": user_playlists_payload.get("items", []),
            "currently_playing": currently_playing_payload or None,
            "audio_features": audio_features_payload,
            "source": "spotify_api_v1",
            "warnings": warnings,
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
            "saved_tracks": len(saved_tracks_payload.get("items", [])),
            "user_playlists": len(user_playlists_payload.get("items", [])),
            "currently_playing": 1 if currently_playing_payload else 0,
            "audio_features": len(audio_features_payload),
        },
        "warnings": warnings,
    }
