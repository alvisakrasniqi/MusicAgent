from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING


FEEDBACK_COLLECTION = "recommendation_feedback"


def _feedback_collection(db: AsyncIOMotorDatabase):
    return db[FEEDBACK_COLLECTION]


def _to_object_id(user_id: str) -> ObjectId | None:
    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_feedback(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None

    document["_id"] = str(document["_id"])
    document["user_id"] = str(document["user_id"])
    return document


async def create_recommendation_feedback_indexes(db: AsyncIOMotorDatabase) -> None:
    feedback = _feedback_collection(db)
    await feedback.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await feedback.create_index([("user_id", ASCENDING), ("feedback_type", ASCENDING), ("created_at", DESCENDING)])


async def record_recommendation_feedback(
    db: AsyncIOMotorDatabase,
    user_id: str,
    feedback_doc: dict[str, Any],
) -> dict[str, Any] | None:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return None

    feedback = _feedback_collection(db)
    doc_to_insert = {
        "user_id": object_id,
        "created_at": _utc_now(),
        **feedback_doc,
    }

    result = await feedback.insert_one(doc_to_insert)
    created = await feedback.find_one({"_id": result.inserted_id})
    return _serialize_feedback(created)


async def list_recommendation_feedback(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 50,
    max_age_days: int = 180,
) -> list[dict[str, Any]]:
    object_id = _to_object_id(user_id)
    if object_id is None:
        return []

    feedback = _feedback_collection(db)
    cutoff = _utc_now() - timedelta(days=max_age_days)
    docs = await feedback.find(
        {"user_id": object_id, "created_at": {"$gte": cutoff}},
        sort=[("created_at", DESCENDING)],
    ).to_list(length=limit)

    return [_serialize_feedback(doc) for doc in docs if doc]
