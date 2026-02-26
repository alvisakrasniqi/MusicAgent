from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.users import router as users_router
from app.core.database import close_mongo_connection, connect_to_mongo, get_database
from app.repositories.user_repository import create_user_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await connect_to_mongo()
    await create_user_indexes(db)
    try:
        yield
    finally:
        await close_mongo_connection()


app = FastAPI(title="MusicAgent API", lifespan=lifespan)
app.include_router(users_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    # Confirms FastAPI is up and DB dependency is initialized.
    get_database()
    return {"status": "ok"}
