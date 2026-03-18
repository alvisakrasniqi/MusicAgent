from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo, get_database
from app.core.session import SessionCookieMiddleware
from app.repositories.spotify_repository import create_spotify_snapshot_indexes
from app.repositories.user_repository import create_user_indexes
from app.api.routes.spotify import router as spotify_router
from app.api.routes.recommendations import router as recommendations_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await connect_to_mongo()
    await create_user_indexes(db)
    await create_spotify_snapshot_indexes(db)
    try:
        yield
    finally:
        await close_mongo_connection()


import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MusicAgent API", lifespan=lifespan)

app.add_middleware(
    SessionCookieMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=settings.SESSION_HTTPS_ONLY,
)

# Allow React app origin
allowed_origins = sorted(
    {
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        settings.FRONTEND_URL.rstrip("/"),
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(spotify_router, prefix="/api", tags=["spotify"])
app.include_router(recommendations_router, prefix="/api", tags=["recommendations"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    get_database()
    return {"status": "ok"}
