"""
schemas/auth.py
---------------
Pydantic schemas for auth and user registration.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserRegister(BaseModel):
    """Register a new user and their company in one step."""
    # User fields
    email:      EmailStr
    password:   str       = Field(..., min_length=8)
    full_name:  str       = Field(..., min_length=2)
    phone:      Optional[str] = None
    role:       UserRole  = UserRole.MSME_OWNER
    language:   str       = "en"

    # Company fields — required for first user
    company_name:     str
    company_industry: Optional[str] = None
    company_state:    Optional[str] = None
    company_city:     Optional[str] = None
    msme_category:    Optional[str] = None


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      UUID
    company_id:   UUID
    role:         UserRole
    full_name:    str


class UserResponse(BaseModel):
    id:         UUID
    company_id: UUID
    email:      str
    full_name:  str
    role:       UserRole
    language:   str
    is_active:  bool

    model_config = {"from_attributes": True}