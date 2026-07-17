"""Pydantic DTO schemas for the Session domain.

Defines the request/response shapes for session data. Intentionally decoupled
from the SQLAlchemy ORM model.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class ChatSessionBase(BaseModel):
    """Shared fields present on every chat session schema.

    Attributes:
        title: Chat session title, max 255 characters.
    """

    title: str = Field(..., min_length=1, max_length=255, description="Chat session title.")


class ChatSessionCreate(ChatSessionBase):
    """Schema for creating a new chat session.

    Inherits ``title`` from ``ChatSessionBase`` with no additional fields.
    """


class ChatSessionUpdate(ChatSessionBase):
    """Schema for partial chat session updates.

    All fields are optional — only provided fields are applied.

    Attributes:
        title: Updated chat session title, max 255 characters.
    """

    title: str | None = Field(None, min_length=1, max_length=255, description="Updated chat session title.")


class ChatSessionRead(ChatSessionBase):
    """Schema for returning chat session data to callers.

    Adds server-managed fields (``id``, ``user_id``).

    Attributes:
        id: Unique chat session identifier (UUID).
        user_id: UUID of the owning user.
    """

    id: UUID = Field(..., description="Unique chat session identifier.")
    user_id: UUID = Field(..., description="UUID of the owning user.")

    model_config = {"from_attributes": True}
