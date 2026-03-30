from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.users import router as users_router
from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.core.session import SessionCookieMiddleware
from app.repositories.recommendation_repository import create_recommendation_feedback_indexes
from app.repositories.spotify_repository import create_spotify_snapshot_indexes
from app.repositories.user_repository import create_user_indexes
from app.api.routes.spotify import legacy_callback_router, router as spotify_router
from app.api.routes.recommendations import router as recommendations_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await connect_to_mongo()
    await create_user_indexes(db)
    await create_spotify_snapshot_indexes(db)
    await create_recommendation_feedback_indexes(db)
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

# Accept the configured frontend plus common local dev origins so browser
# preflight requests succeed whether the app is opened via localhost or 127.0.0.1.
allowed_origins = sorted(
    {
        settings.FRONTEND_URL.rstrip("/"),
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(health_router)
app.include_router(spotify_router, prefix="/api", tags=["spotify"])
app.include_router(legacy_callback_router)
app.include_router(recommendations_router, prefix="/api", tags=["recommendations"])
