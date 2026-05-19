from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "FlowEngine"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str
    SYNC_DATABASE_URL: str
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    RATE_LIMIT_PER_MINUTE: int = 60
    SURGE_THRESHOLD_PER_SECOND: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
