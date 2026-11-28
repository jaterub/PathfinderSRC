from pydantic import Field
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    token_expiration_minutes: int = Field(
        default=15, ge=1, le=60
    )


settings = AuthSettings()
