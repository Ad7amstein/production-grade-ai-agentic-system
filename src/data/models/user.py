"""Pydantic DTO schemas for the User domain.

Defines the request/response shapes for user data. Intentionally decoupled
from the SQLAlchemy ORM model — ``hashed_password`` is never exposed here.
"""

import re
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


class UserBase(BaseModel):
    """Shared fields present on every user schema.

    Attributes:
        first_name: User's first name, max 100 characters.
        last_name: User's last name, max 100 characters.
        email: User's unique email address.
    """

    first_name: str = Field(..., max_length=100, description="User's first name.")
    last_name: str = Field(..., max_length=100, description="User's last name.")
    email: EmailStr = Field(..., description="User's unique email address.")


class UserCreate(UserBase):
    """Schema for creating a new user account.

    Extends ``UserBase`` with a plain-text password that is validated
    before being hashed and persisted.

    Attributes:
        password: Plain-text password (8–64 chars). Must contain uppercase,
            lowercase, digit, and special character. Hashed before persistence.
    """

    password: SecretStr = Field(
        ..., min_length=8, max_length=64, description="Plain-text password (8–64 chars). Hashed before persistence."
    )

    @field_validator("password")
    @classmethod
    def validate_passowrd(cls, value: SecretStr) -> SecretStr:
        """Enforce password complexity rules.

        Raises ``ValueError`` if the password is missing any required
        character class: lowercase, uppercase, digit, or special character.
        """
        password = value.get_secret_value()

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", password):
            raise ValueError("Password must contain at least one lowercase letter")

        if not re.search(r"[0-9]", password):
            raise ValueError("Password must contain at least one number")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValueError("Password must contain at least one special character")

        return value


class UserUpdate(UserBase):
    """Schema for partial user profile updates.

    All fields are optional — only provided fields are applied.

    Attributes:
        first_name: Updated first name, max 100 characters.
        last_name: Updated last name, max 100 characters.
        email: Updated email address.
    """

    first_name: str | None = Field(None, max_length=100, description="Updated first name.")
    last_name: str | None = Field(None, max_length=100, description="Updated last name.")
    email: EmailStr | None = Field(None, description="Updated email address.")


class UserRead(UserBase):
    """Schema for returning user data to callers.

    Adds server-managed fields (``id``, ``is_active``, ``is_verified``).
    Never includes ``hashed_password``.

    Attributes:
        id: Unique user identifier (UUID).
        is_active: Whether the account is active.
        is_verified: Whether the email address has been verified.
    """

    id: UUID = Field(..., description="Unique user identifier.")
    is_active: bool = Field(..., description="Whether the account is active.")
    is_verified: bool = Field(..., description="Whether the email has been verified.")

    model_config = {"from_attributes": True}
