import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.models.user import UserCreate, UserUpdate, UserResponse
from app.repositories.user_repository import (
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    list_users,
    update_user,
)


router = APIRouter(prefix="/users", tags=["users"])


def _hash_password_for_now(password: str) -> str:
    # Temporary hash helper for DB testing only. Replace with passlib/pwdlib + salt.
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@router.get("/db-ping")
async def db_ping(db: AsyncIOMotorDatabase = Depends(get_database)) -> dict[str, str]:
    await db.command("ping")
    return {"status": "ok"}


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user_route(
    payload: UserCreate,
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
        "hashed_password": _hash_password_for_now(payload.password),
    }

    try:
        created = await create_user(db, user_doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        ) from None

    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

    return created


@router.get("/")
async def list_users_route(
    limit: int = 100,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 500",
        )
    return await list_users(db, limit=limit)


@router.get("/{user_id}")
async def get_user_route(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_route(
    user_id: str,
    payload: UserUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, Any]:
    update_payload = payload.model_dump(exclude_none=True)

    if "password" in update_payload:
        update_payload["hashed_password"] = _hash_password_for_now(update_payload.pop("password"))

    if not update_payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No valid fields to update",
        )

    try:
        updated = await update_user(db, user_id, update_payload)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        ) from None

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return updated


@router.delete("/{user_id}")
async def delete_user_route(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, bool]:
    deleted = await delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"deleted": True}
