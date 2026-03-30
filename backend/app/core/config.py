from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    SPOTIFY_REDIRECT_URI: str = "http://127.0.0.1:8000/auth/spotify/callback"
    FRONTEND_URL: str = "http://localhost:3000"
    SESSION_SECRET_KEY: str = "change-me-in-production"
    SESSION_COOKIE_NAME: str = "music_agent_session"
    SESSION_MAX_AGE_SECONDS: int = 604800
    SESSION_HTTPS_ONLY: bool = False
    GOOGLE_API_KEY: str = ""
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_TRACING: bool = True
    LANGSMITH_PROJECT: str = "music-agent"

    model_config = SettingsConfigDict(env_file=BACKEND_ENV_PATH, extra="ignore")

settings = Settings()
