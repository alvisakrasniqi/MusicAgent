from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.api.deps.auth import (
    clear_authenticated_session,
    get_current_user,
    set_authenticated_session,
)
from app.core.database import get_database
from app.core.security import hash_password, verify_password
from app.models.user import AuthenticatedUserResponse, LoginRequest, UserCreate
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    get_user_spotify_auth,
    update_user,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _build_authenticated_user_response(
    db: AsyncIOMotorDatabase,
    user: dict[str, Any],
) -> dict[str, Any]:
    response_user = {k: v for k, v in user.items() if k != "hashed_password"}
    spotify_auth = await get_user_spotify_auth(db, response_user["_id"])
    response_user["spotify_connected"] = bool(
        isinstance(spotify_auth, dict)
        and (spotify_auth.get("access_token") or spotify_auth.get("refresh_token"))
    )
    return response_user


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthenticatedUserResponse)
async def register_route(
    payload: UserCreate,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    existing_username = await get_user_by_username(db, payload.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    existing_email = await get_user_by_email(db, payload.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    user_doc = {
        "username": payload.username,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "email": payload.email,
        "hashed_password": hash_password(payload.password),
    }

    try:
        created_user = await create_user(db, user_doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        ) from None

    if not created_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

    set_authenticated_session(request, created_user["_id"])
    return await _build_authenticated_user_response(db, created_user)


@router.post("/login", response_model=AuthenticatedUserResponse)
async def login_route(
    payload: LoginRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    user = await get_user_by_email(db, payload.identifier, include_password_hash=True)
    if not user:
        user = await get_user_by_username(db, payload.identifier, include_password_hash=True)

    if not user or not verify_password(payload.password, user.get("hashed_password")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not str(user.get("hashed_password", "")).startswith("pbkdf2_"):
        await update_user(
            db,
            user["_id"],
            {"hashed_password": hash_password(payload.password)},
        )

    set_authenticated_session(request, user["_id"])
    return await _build_authenticated_user_response(db, user)


@router.get("/me", response_model=AuthenticatedUserResponse)
async def current_user_route(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    return await _build_authenticated_user_response(db, current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_route(request: Request) -> Response:
    clear_authenticated_session(request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
