import os
from pathlib import Path
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


try:
    from dotenv import load_dotenv
except ImportError:  # Optional, but recommended
    load_dotenv = None


if load_dotenv is not None:
    # Load backend/.env when running from repo root or backend directory.
    backend_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=backend_env, override=False)


_mongo_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


def _get_mongo_uri() -> str:
    mongo_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URL")
    if not mongo_uri:
        raise RuntimeError("Missing MongoDB connection string. Set MONGODB_URI (or MONGO_URL).")
    return mongo_uri


def _get_database_name(mongo_uri: str) -> str:
    db_name = os.getenv("MONGODB_DB_NAME") or os.getenv("MONGO_DB_NAME")
    if db_name:
        return db_name

    parsed = urlparse(mongo_uri)
    path_db_name = parsed.path.lstrip("/")
    if path_db_name:
        return path_db_name

    raise RuntimeError("Missing database name. Set MONGODB_DB_NAME or include it in the Mongo URI path.")


async def connect_to_mongo() -> AsyncIOMotorDatabase:
    global _mongo_client, _database

    if _database is not None and _mongo_client is not None:
        return _database

    mongo_uri = _get_mongo_uri()
    db_name = _get_database_name(mongo_uri)

    _mongo_client = AsyncIOMotorClient(
        mongo_uri,
        tls=True,
        tlsAllowInvalidCertificates=True,
    )
    _database = _mongo_client[db_name]

    # Fail fast on startup if credentials/network are wrong.
    await _database.command("ping")
    return _database


async def close_mongo_connection() -> None:
    global _mongo_client, _database

    if _mongo_client is not None:
        _mongo_client.close()

    _mongo_client = None
    _database = None


def get_database() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("Database is not initialized. Call connect_to_mongo() on app startup.")
    return _database
