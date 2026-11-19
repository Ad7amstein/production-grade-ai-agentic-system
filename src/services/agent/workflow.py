"""LangChain agent for the web assistant, built with `create_agent` and middleware."""

import time
from uuid import uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import AgentState, InputAgentState, OutputAgentState
from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from config.settings import settings
from data.models.graph import GraphContext
from data.models.user import UserRead
from services.agent.tools.search import tavily_search
from services.llm import MODEL_PROFILES, build_chat_model
from system.logs import logger


def _turn_start(messages: list[AnyMessage]) -> int:
    """Return the index of the latest user message, where the current turn begins.

    Args:
        messages (list[AnyMessage]): Full conversation history.

    Returns:
        int: Index of the last `HumanMessage`, or 0 if there is none.
    """
    return max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=0)


class AgenticWorkflow:
    """Tool-calling agent built with `create_agent` and LangChain's prebuilt middleware.

    Conversations and long-term memories are kept in process memory, so a restart clears them.
    """

    def __init__(self):
        self._tools = [tavily_search]
        self._chat_model = build_chat_model(
            model=settings.GENERATION_MODEL,
            model_provider=settings.GENERATION_MODEL_PROVIDER,
            profile=MODEL_PROFILES[f"{settings.GENERATION_MODEL_PROFILE_PROVIDER}/{settings.GENERATION_MODEL}"],
            max_tokens=settings.DEFAULT_GENERATION_MAX_TOKENS,
            max_retries=0,
        )

        self._graph: CompiledStateGraph[AgentState, GraphContext, InputAgentState, OutputAgentState] = create_agent(
            model=self._chat_model, tools=self._tools, checkpointer=InMemorySaver(), context_schema=GraphContext
        )
        logger.info("agent_initialized")

    async def get_response(self, content: str, chat_session_id: str, user: UserRead) -> str:
        """Send a user message into a chat session and return the agent's reply.

        Args:
            content (str): The user's message.
            chat_session_id (str): Chat session used as the checkpointer thread id.
            user (UserRead): Authenticated user whose profile is shown to the model.

        Returns:
            str: Text of the final assistant message.
        """
        config: RunnableConfig = {"configurable": {"thread_id": chat_session_id}}
        message_id = str(uuid4())
        started = time.perf_counter()
        result = await self._graph.ainvoke(
            {"messages": [HumanMessage(content=content, id=message_id)]},  # type: ignore
            config=config,
            context=GraphContext(user=user),
        )

        messages = result["messages"]
        turn = messages[_turn_start(messages) :]
        logger.info(
            "agent_response_completed",
            chat_session_id=chat_session_id,
            tool_calls=sum(len(getattr(m, "tool_calls", [])) for m in turn),
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        return messages[-1].text

    async def delete_history(self, chat_session_id: str) -> None:
        """Delete every checkpoint stored for a chat session.

        Args:
            chat_session_id (str): Chat session used as the checkpointer thread id.
        """
        await self._graph.checkpointer.adelete_thread(chat_session_id)  # type: ignore[union-attr]


agent = AgenticWorkflow()
