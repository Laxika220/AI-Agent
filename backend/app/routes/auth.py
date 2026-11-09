"""Authentication routes: register, login, refresh, me."""

from datetime import UTC, datetime

from fastapi import APIRouter, status
from pymongo.errors import DuplicateKeyError

from app.core.deps import CacheDep, CurrentUser, DbDep, SettingsDep
from app.core.errors import AuthenticationError, ConflictError
from app.models.common import new_id, utcnow
from app.models.user import (
    AuthResponse,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserInDB,
    UserLogin,
    UserPublic,
)
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user_id: str, settings: SettingsDep) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: DbDep, settings: SettingsDep) -> AuthResponse:
    doc = {
        "_id": new_id(),
        "email": payload.email.lower(),
        "full_name": payload.full_name,
        "hashed_password": hash_password(payload.password),
        "created_at": utcnow(),
    }
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError as exc:
        raise ConflictError("An account with this email already exists") from exc
    user = UserInDB.from_doc(doc)
    return AuthResponse(user=user.to_public(), tokens=_issue_tokens(user.id, settings))


@router.post("/login", response_model=AuthResponse)
async def login(payload: UserLogin, db: DbDep, settings: SettingsDep) -> AuthResponse:
    doc = await db.users.find_one({"email": payload.email.lower()})
    if doc is None or not verify_password(payload.password, doc["hashed_password"]):
        raise AuthenticationError("Invalid email or password")
    user = UserInDB.from_doc(doc)
    return AuthResponse(user=user.to_public(), tokens=_issue_tokens(user.id, settings))


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbDep, cache: CacheDep, settings: SettingsDep) -> TokenPair:
    """Exchange a refresh token for a new token pair (refresh tokens are single-use)."""
    token = decode_token(payload.refresh_token, "refresh")
    if await db.users.count_documents({"_id": token.sub}, limit=1) == 0:
        raise AuthenticationError("User no longer exists")
    ttl = int((token.exp - datetime.now(UTC)).total_seconds())
    if not await cache.consume_refresh_token(token.jti, ttl):
        raise AuthenticationError("Refresh token has already been used")
    return _issue_tokens(token.sub, settings)


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return user.to_public()
