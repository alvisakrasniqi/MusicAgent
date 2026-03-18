from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.agent.music_agent import run_agent
from app.api.deps.auth import get_current_user
from app.core.database import get_database
from app.repositories.user_repository import get_user_spotify_auth

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    timestamp: str


async def _get_valid_access_token(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> str:
    spotify_auth = await get_user_spotify_auth(db, user_id)
    if not spotify_auth or not spotify_auth.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spotify not linked. Connect Spotify first.",
        )
    return spotify_auth["access_token"]


@router.post("/recommendations/chat", response_model=ChatResponse)
async def recommendation_chat(
    body: ChatRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ChatResponse:
    user_id = current_user["_id"]
    access_token = await _get_valid_access_token(db, user_id)

    reply = await run_agent(db, user_id, body.message, access_token)

    return ChatResponse(
        reply=reply,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/recommendations/quick", response_model=ChatResponse)
async def quick_recommend(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ChatResponse:
    user_id = current_user["_id"]
    access_token = await _get_valid_access_token(db, user_id)

    reply = await run_agent(
        db,
        user_id,
        (
            "Based on my listening history, recommend 5 songs I haven't been listening to "
            "that you think I'd love. Search Spotify to find real tracks. For each, explain "
            "why it fits my taste."
        ),
        access_token,
    )

    return ChatResponse(
        reply=reply,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
