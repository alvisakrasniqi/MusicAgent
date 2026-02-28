from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    SPOTIFY_REDIRECT_URI: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
