from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class VisibleFields(BaseModel):
    year: bool = True
    tags: bool = True
    format: bool = False
    audio_types: bool = False
    rating: bool = False


class UserSettings(BaseModel):
    sort_field: str | None = None
    sort_direction: str | None = None
    visible_fields: VisibleFields = Field(default_factory=VisibleFields)


class UserSettingsUpdate(BaseModel):
    sort_field: str | None = None
    sort_direction: str | None = None
    visible_fields: VisibleFields | None = None


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, value: str) -> str:
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Brugernavn må kun indeholde bogstaver, tal, - og _")
        return value


class UserLogin(BaseModel):
    username: str
    password: str


class User(BaseModel):
    id: str
    username: str
    settings: UserSettings
    created_at: datetime
