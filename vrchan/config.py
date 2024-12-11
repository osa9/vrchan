from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    # VRC
    vrc_username: str
    vrc_password: str
    vrc_user_agent: str
    vrc_group_id: str
    otp_secret: str

    # Thumbnail
    thumbnail_url: str | None = None

    # Redis
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str

    # Discord
    discord_webhook_url: str

    class Config:
        env_file = ".env"
