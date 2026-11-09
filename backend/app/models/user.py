"""User and authentication schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.common import MongoModel


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserPublic(MongoModel):
    email: EmailStr
    full_name: str | None = None
    created_at: datetime


class UserInDB(UserPublic):
    hashed_password: str

    def to_public(self) -> UserPublic:
        return UserPublic.model_validate(self.model_dump(exclude={"hashed_password"}))


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    user: UserPublic
    tokens: TokenPair
