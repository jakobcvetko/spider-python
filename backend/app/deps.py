import hashlib
from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Session as SessionModel
from app.models import User

settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def get_current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_hash = _hash_token(session_token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(SessionModel, User)
        .join(User, User.id == SessionModel.user_id)
        .where(SessionModel.token_hash == token_hash)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    session_obj, user = row
    if session_obj.expires_at <= now:
        await db.delete(session_obj)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    session_obj.last_used_at = now
    await db.commit()
    return user
