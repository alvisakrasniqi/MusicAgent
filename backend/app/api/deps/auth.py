from typing import Any

from fastapi import Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.repositories.user_repository import get_user_by_id


SESSION_USER_ID_KEY = "user_id"
SPOTIFY_STATE_SESSION_KEY = "spotify_oauth_state"
FRONTEND_ORIGIN_SESSION_KEY = "frontend_origin"


def set_authenticated_session(request: Request, user_id: str) -> None:
    request.session.clear()
    request.session[SESSION_USER_ID_KEY] = user_id


def clear_authenticated_session(request: Request) -> None:
    request.session.clear()


def set_spotify_oauth_state(request: Request, state: str) -> None:
    request.session[SPOTIFY_STATE_SESSION_KEY] = state


def pop_spotify_oauth_state(request: Request) -> str | None:
    return request.session.pop(SPOTIFY_STATE_SESSION_KEY, None)


def set_frontend_origin(request: Request, origin: str) -> None:
    request.session[FRONTEND_ORIGIN_SESSION_KEY] = origin


def get_frontend_origin(request: Request) -> str | None:
    origin = request.session.get(FRONTEND_ORIGIN_SESSION_KEY)
    return origin if isinstance(origin, str) and origin else None


async def get_optional_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any] | None:
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if not user_id:
        return None

    user = await get_user_by_id(db, user_id)
    if not user:
        clear_authenticated_session(request)
        return None

    return user


async def get_current_user(
    current_user: dict[str, Any] | None = Depends(get_optional_current_user),
) -> dict[str, Any]:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return current_user
