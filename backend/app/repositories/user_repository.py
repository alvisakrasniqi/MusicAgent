from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING


USER_COLLECTION = "users"
PUBLIC_USER_PROJECTION = {"hashed_password": 0, "spotify": 0, "agent_context": 0}


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


async def save_user_spotify_tokens(
    db: AsyncIOMotorDatabase,
    user_id: str,
    token_payload: dict[str, Any],
) -> dict[str, Any] | None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None

    users = _users_collection(db)
    now = _utc_now()

    expires_in = int(token_payload.get("expires_in", 0) or 0)
    expires_at = now + timedelta(seconds=expires_in) if expires_in > 0 else None

    updates: dict[str, Any] = {
        "spotify.access_token": token_payload.get("access_token"),
        "spotify.token_type": token_payload.get("token_type"),
        "spotify.scope": token_payload.get("scope"),
        "spotify.expires_in": expires_in,
        "spotify.expires_at": expires_at,
        "spotify.updated_at": now,
        "updated_at": now,
    }

    refresh_token = token_payload.get("refresh_token")
    if refresh_token:
        updates["spotify.refresh_token"] = refresh_token

    updates = {k: v for k, v in updates.items() if v is not None}

    result = await users.update_one({"_id": object_id}, {"$set": updates})
    if result.matched_count == 0:
        return None

    doc = await users.find_one({"_id": object_id}, PUBLIC_USER_PROJECTION)
    return _serialize_user(doc)


async def get_user_spotify_auth(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> dict[str, Any] | None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None

    users = _users_collection(db)
    doc = await users.find_one({"_id": object_id}, {"spotify": 1})
    if not doc:
        return None

    spotify_auth = doc.get("spotify")
    if not isinstance(spotify_auth, dict):
        return None

    return spotify_auth


async def set_user_mood_context(
    db: AsyncIOMotorDatabase,
    user_id: str,
    mood: str,
    preferred_context: str | None = None,
    duration_hours: int = 8,
) -> dict[str, Any] | None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None

    now = _utc_now()
    expires_at = now + timedelta(hours=max(duration_hours, 1))
    payload = {
        "agent_context.mood.value": mood,
        "agent_context.mood.updated_at": now,
        "agent_context.mood.expires_at": expires_at,
        "updated_at": now,
    }
    if preferred_context:
        payload["agent_context.mood.preferred_context"] = preferred_context

    users = _users_collection(db)
    update_doc: dict[str, Any] = {"$set": payload}
    if not preferred_context:
        update_doc["$unset"] = {"agent_context.mood.preferred_context": ""}

    result = await users.update_one({"_id": object_id}, update_doc)
    if result.matched_count == 0:
        return None

    doc = await users.find_one({"_id": object_id}, {"agent_context": 1})
    return doc.get("agent_context", {}) if isinstance(doc, dict) else None


async def clear_user_mood_context(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return

    users = _users_collection(db)
    await users.update_one(
        {"_id": object_id},
        {
            "$unset": {
                "agent_context.mood": "",
            },
            "$set": {
                "updated_at": _utc_now(),
            },
        },
    )


async def get_user_mood_context(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> dict[str, Any] | None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None

    users = _users_collection(db)
    doc = await users.find_one({"_id": object_id}, {"agent_context.mood": 1})
    if not doc:
        return None

    agent_context = doc.get("agent_context")
    if not isinstance(agent_context, dict):
        return None

    mood_context = agent_context.get("mood")
    if not isinstance(mood_context, dict):
        return None

    expires_at = mood_context.get("expires_at")
    if isinstance(expires_at, datetime):
        expires_dt = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    elif isinstance(expires_at, str):
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            expires_dt = None
    else:
        expires_dt = None

    if expires_dt is None or expires_dt <= _utc_now():
        await clear_user_mood_context(db, user_id)
        return None

    return mood_context
