from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING


USER_COLLECTION = "users"
PUBLIC_USER_PROJECTION = {"hashed_password": 0}


def _users_collection(db: AsyncIOMotorDatabase):
    return db[USER_COLLECTION]


def _to_object_id(user_id: str) -> ObjectId | None:
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        return None


def _serialize_user(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None

    document["_id"] = str(document["_id"])
    return document


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def create_user_indexes(db: AsyncIOMotorDatabase) -> None:
    users = _users_collection(db)
    await users.create_index([("username", ASCENDING)], unique=True)
    await users.create_index([("email", ASCENDING)], unique=True)


async def create_user(
    db: AsyncIOMotorDatabase,
    user_doc: dict[str, Any],
) -> dict[str, Any] | None:
    users = _users_collection(db)

    now = _utc_now()
    user_to_insert = {
        **user_doc,
        "created_at": user_doc.get("created_at", now),
        "updated_at": user_doc.get("updated_at", now),
    }

    result = await users.insert_one(user_to_insert)
    created = await users.find_one(
        {"_id": result.inserted_id},
        PUBLIC_USER_PROJECTION,
    )
    return _serialize_user(created)


async def list_users(
    db: AsyncIOMotorDatabase,
    limit: int = 100,
) -> list[dict[str, Any]]:
    users = _users_collection(db)
    docs = await users.find({}, PUBLIC_USER_PROJECTION).to_list(length=limit)
    return [_serialize_user(doc) for doc in docs if doc]


async def get_user_by_id(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> dict[str, Any] | None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None

    users = _users_collection(db)
    doc = await users.find_one({"_id": object_id}, PUBLIC_USER_PROJECTION)
    return _serialize_user(doc)


async def get_user_by_username(
    db: AsyncIOMotorDatabase,
    username: str,
    include_password_hash: bool = False,
) -> dict[str, Any] | None:
    users = _users_collection(db)
    projection = None if include_password_hash else PUBLIC_USER_PROJECTION
    doc = await users.find_one({"username": username}, projection)
    return _serialize_user(doc)


async def get_user_by_email(
    db: AsyncIOMotorDatabase,
    email: str,
    include_password_hash: bool = False,
) -> dict[str, Any] | None:
    users = _users_collection(db)
    projection = None if include_password_hash else PUBLIC_USER_PROJECTION
    doc = await users.find_one({"email": email}, projection)
    return _serialize_user(doc)


async def update_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    update_data: dict[str, Any],
) -> dict[str, Any] | None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None

    updates = {k: v for k, v in update_data.items() if v is not None}
    updates.pop("_id", None)
    updates.pop("created_at", None)

    if not updates:
        return await get_user_by_id(db, user_id)

    updates["updated_at"] = _utc_now()

    users = _users_collection(db)
    await users.update_one({"_id": object_id}, {"$set": updates})
    doc = await users.find_one({"_id": object_id}, PUBLIC_USER_PROJECTION)
    return _serialize_user(doc)


async def delete_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> bool:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return False

    users = _users_collection(db)
    result = await users.delete_one({"_id": object_id})
    return result.deleted_count == 1
