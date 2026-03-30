from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.agent.music_agent import _build_tools
from app.core.config import settings
from app.core.database import get_database


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    timestamp: str


class ReadinessDependencies(BaseModel):
    database: Literal["ok"]


class ReadinessResponse(HealthResponse):
    dependencies: ReadinessDependencies


class AgentDependencies(BaseModel):
    database: Literal["ok"]
    google_api_key: Literal["configured"]
    tools: Literal["ok"]


class AgentHealthResponse(HealthResponse):
    dependencies: AgentDependencies


def _health_payload() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="music-agent-api",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def _require_ready_database() -> None:
    db = get_database()

    try:
        await db.command("ping")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready",
        ) from exc


def _require_google_api_key() -> None:
    if not settings.GOOGLE_API_KEY.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent provider is not configured",
        )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return _health_payload()


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    await _require_ready_database()

    payload = _health_payload()
    return ReadinessResponse(
        **payload.model_dump(),
        dependencies=ReadinessDependencies(database="ok"),
    )


@router.get("/health/agent", response_model=AgentHealthResponse)
async def agent_health_check() -> AgentHealthResponse:
    await _require_ready_database()
    _require_google_api_key()

    # Build the agent toolset with placeholder values to catch local wiring issues
    # without making external provider calls.
    try:
        tools = _build_tools(
            db=get_database(),
            user_id="healthcheck",
            music_profile="Health check profile",
            access_token=None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent tools failed to initialize",
        ) from exc

    if not tools:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent tools are unavailable",
        )

    payload = _health_payload()
    return AgentHealthResponse(
        **payload.model_dump(),
        dependencies=AgentDependencies(
            database="ok",
            google_api_key="configured",
            tools="ok",
        ),
    )


@router.get("/health/agent/live", response_model=AgentHealthResponse)
async def agent_live_health_check() -> AgentHealthResponse:
    await _require_ready_database()
    _require_google_api_key()

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
        response = await llm.ainvoke("Reply with OK")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent provider live check failed",
        ) from exc

    response_text = getattr(response, "content", "")
    if isinstance(response_text, list):
        response_text = " ".join(str(part) for part in response_text)
    response_text = str(response_text).strip().upper()
    if "OK" not in response_text:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent provider returned an unexpected response",
        )

    payload = _health_payload()
    return AgentHealthResponse(
        **payload.model_dump(),
        dependencies=AgentDependencies(
            database="ok",
            google_api_key="configured",
            tools="ok",
        ),
    )
