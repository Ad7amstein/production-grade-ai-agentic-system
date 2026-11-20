"""Long-term memory tool for the agent."""

from uuid import uuid4

from langchain.tools import ToolRuntime, tool

from data.models.graph import GraphContext


@tool(parse_docstring=True)
def save_memory(content: str, runtime: ToolRuntime[GraphContext]) -> str:
    """Save a lasting fact about the user, such as their job, location, preferences, or goals.

    Args:
        content: The fact to remember, as one short sentence about the user.

    Returns:
        Confirmation that the fact was saved.
    """
    namespace = ("memories", str(runtime.context.user.id))
    runtime.store.put(namespace, str(uuid4()), {"content": content})  # type: ignore[union-attr]
    return "Saved."
