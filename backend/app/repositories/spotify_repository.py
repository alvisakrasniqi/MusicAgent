from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING


SPOTIFY_SNAPSHOT_COLLECTION = "spotify_snapshots"


def _spotify_snapshots_collection(db: AsyncIOMotorDatabase):
    return db[SPOTIFY_SNAPSHOT_COLLECTION]


def _to_object_id(user_id: str) -> ObjectId | None:
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def create_spotify_snapshot_indexes(db: AsyncIOMotorDatabase) -> None:
    snapshots = _spotify_snapshots_collection(db)
    await snapshots.create_index([("user_id", ASCENDING), ("fetched_at", DESCENDING)])


async def create_spotify_ingestion_snapshot(
    db: AsyncIOMotorDatabase,
    user_id: str,
    snapshot_payload: dict[str, Any],
) -> str | None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None

    snapshots = _spotify_snapshots_collection(db)
    snapshot_doc = {
        "user_id": object_id,
        "fetched_at": _utc_now(),
        **snapshot_payload,
    }
    result = await snapshots.insert_one(snapshot_doc)
    return str(result.inserted_id)
