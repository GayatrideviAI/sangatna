"""
services/auth_service.py
------------------------
Handles password hashing and JWT token creation/verification.
"""

from datetime import datetime, timedelta, timezone
import bcrypt

from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

# Password hashing
# Password hashing
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# JWT
def create_access_token(user: User) -> str:
    payload = {
        "sub":        str(user.id),
        "company_id": str(user.company_id),
        "role":       user.role.value,
        "exp":        datetime.now(timezone.utc) + timedelta(
                          minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                      ),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return {}


# DB helpers
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()