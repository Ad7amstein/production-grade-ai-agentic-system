"""Runtime context schema for the agent."""

from dataclasses import dataclass

from data.models.user import UserRead


@dataclass
class GraphContext:
    """Per-invocation context; unlike state, it is never checkpointed.

    Attributes:
        user (UserRead): Authenticated user, shown to the model as their profile and owning the memories read.
    """

    user: UserRead
