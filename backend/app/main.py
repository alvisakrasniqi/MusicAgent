from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.users import router as users_router
from app.core.database import close_mongo_connection, connect_to_mongo, get_database
from app.repositories.spotify_repository import create_spotify_snapshot_indexes
from app.repositories.user_repository import create_user_indexes
from app.api.routes.spotify import router as spotify_router 

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await connect_to_mongo()
    await create_user_indexes(db)
    await create_spotify_snapshot_indexes(db)
    try:
        yield
    finally:
        await close_mongo_connection()


app = FastAPI(title="MusicAgent API", lifespan=lifespan)

app.include_router(users_router)
app.include_router(spotify_router, prefix="/auth", tags=["spotify"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    get_database()
    return {"status": "ok"}
