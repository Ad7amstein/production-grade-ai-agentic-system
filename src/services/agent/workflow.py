"""LangChain agent for the web assistant, built with `create_agent` and middleware."""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    InputAgentState,
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    ModelRequest,
    ModelResponse,
    ModelRetryMiddleware,
    OutputAgentState,
    PIIDetectionError,
    PIIMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
    dynamic_prompt,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from config.settings import settings
from data.models.graph import GraphContext
from data.models.user import UserRead
from services.agent.tools.memory import save_memory
from services.agent.tools.search import tavily_search
from services.llm import MODEL_PROFILES, build_chat_model
from services.prompts import render_assistant_system_prompt
from system.logs import logger


def _turn_start(messages: list[AnyMessage]) -> int:
    """Return the index of the latest user message, where the current turn begins.

    Args:
        messages (list[AnyMessage]): Full conversation history.

    Returns:
        int: Index of the last `HumanMessage`, or 0 if there is none.
    """
    return max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=0)


def _tool_error_message(error: Exception, request: ToolCallRequest) -> str:
    """Log a failed tool call and return a generic message for the model.

    Args:
        error (Exception): The exception raised by the tool.
        request (ToolCallRequest): The failed tool call.

    Returns:
        str: Message stored as the tool result in place of the error details.
    """
    logger.warning(
        "tool_call_failed", tool=request.tool_call["name"], error_type=type(error).__name__, error=str(error)
    )
    return f"The `{request.tool_call['name']}` tool failed. Answer without it and tell the user it failed."


@dynamic_prompt
def _system_prompt(request: ModelRequest[GraphContext]) -> str:
    """Write the user's profile, saved memories, and the current time into the system prompt before every model call.

    Args:
        request (ModelRequest[GraphContext]): Model call whose run context holds the user and the memory store.

    Returns:
        str: The rendered system prompt.
    """
    user = request.runtime.context.user
    items = request.runtime.store.search(("memories", str(user.id)), limit=100)  # type: ignore[union-attr]
    memories = "\n".join(f"- {item.value['content']}" for item in items) or "None."
    return render_assistant_system_prompt(
        user_profile=f"Name: {user.first_name} {user.last_name}; Email: {user.email}",
        long_term_memory=memories,
        current_date_and_time=datetime.now().strftime("%A, %Y-%m-%d %H:%M"),
    )


async def _log_model_call(
    request: ModelRequest[GraphContext], handler: Callable[[ModelRequest[GraphContext]], Awaitable[ModelResponse]]
) -> ModelResponse:
    """Log each model call before it is sent and after it returns.

    Args:
        request (ModelRequest[GraphContext]): The model call about to run.
        handler (Callable[[ModelRequest[GraphContext]], Awaitable[ModelResponse]]): Runs the model call.

    Returns:
        ModelResponse: The model's response, unchanged.
    """
    model = getattr(request.model, "model_name", type(request.model).__name__)
    logger.debug("model_call_started", model=model, messages=len(request.messages), tools=len(request.tools))
    started = time.perf_counter()
    response = await handler(request)
    reply = next((m for m in reversed(response.result) if isinstance(m, AIMessage)), None)
    logger.debug(
        "model_call_completed",
        model=model,
        duration_ms=round((time.perf_counter() - started) * 1000),
        tool_calls=[call["name"] for call in reply.tool_calls] if reply else [],
        usage=reply.usage_metadata if reply else None,
    )
    return response


async def _log_tool_call(
    request: ToolCallRequest, handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]
) -> ToolMessage | Command:
    """Log each tool call before it runs and after it returns.

    Args:
        request (ToolCallRequest): The tool call about to run.
        handler (Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]): Runs the tool call.

    Returns:
        ToolMessage | Command: The tool's result, unchanged.
    """
    call = request.tool_call
    logger.debug("tool_call_started", tool=call["name"], tool_call_id=call["id"], args=call["args"])
    started = time.perf_counter()
    result = await handler(request)
    logger.debug(
        "tool_call_completed",
        tool=call["name"],
        tool_call_id=call["id"],
        duration_ms=round((time.perf_counter() - started) * 1000),
        status=result.status if isinstance(result, ToolMessage) else None,
    )
    return result


class AgenticWorkflow:
    """Tool-calling agent built with `create_agent` and LangChain's prebuilt middleware.

    Conversations and long-term memories are kept in process memory, so a restart clears them.
    """

    def __init__(self):
        self._tools = [tavily_search, save_memory]
        self._chat_model = build_chat_model(
            model=settings.GENERATION_MODEL,
            model_provider=settings.GENERATION_MODEL_PROVIDER,
            profile=MODEL_PROFILES[f"{settings.GENERATION_MODEL_PROFILE_PROVIDER}/{settings.GENERATION_MODEL}"],
            max_tokens=settings.DEFAULT_GENERATION_MAX_TOKENS,
            max_retries=0,
        )
        self._first_fallback_model = build_chat_model(
            model=settings.FALLBACK_MODEL_1,  # type: ignore
            model_provider=settings.FALLBACK_MODEL_1_PROVIDER,  # type: ignore
            profile=MODEL_PROFILES[f"{settings.FALLBACK_MODEL_1_PROFILE_PROVIDER}/{settings.FALLBACK_MODEL_1}"],
            max_tokens=settings.DEFAULT_GENERATION_MAX_TOKENS,
            max_retries=0,
        )
        self._second_fallback_model = build_chat_model(
            model=settings.FALLBACK_MODEL_2,  # type: ignore
            model_provider=settings.FALLBACK_MODEL_2_PROVIDER,  # type: ignore
            profile=MODEL_PROFILES[f"{settings.FALLBACK_MODEL_2_PROFILE_PROVIDER}/{settings.FALLBACK_MODEL_2}"],
            max_tokens=settings.DEFAULT_GENERATION_MAX_TOKENS,
            max_retries=0,
        )
        self._summary_model = build_chat_model(
            model=settings.SUMMARIZATION_MODEL,  # type: ignore
            model_provider=settings.SUMMARIZATION_MODEL_PROVIDER,  # type: ignore
            profile=MODEL_PROFILES[f"{settings.SUMMARIZATION_MODEL_PROFILE_PROVIDER}/{settings.SUMMARIZATION_MODEL}"],
            max_tokens=settings.SUMMARY_MAX_SUMMARY_TOKENS,
            reasoning_effort=settings.SUMMARIZATION_REASONING_EFFORT,
        )

        middleware: list[AgentMiddleware[Any, GraphContext]] = [
            _system_prompt,
            PIIMiddleware("credit_card", strategy="block"),
            PIIMiddleware("email", strategy="redact"),
            PIIMiddleware("ip", strategy="mask"),
            ModelCallLimitMiddleware(
                run_limit=settings.MODEL_CALL_RUN_LIMIT, thread_limit=settings.MODEL_CALL_THREAD_LIMIT or None
            ),
            ModelFallbackMiddleware(self._first_fallback_model, self._second_fallback_model),
            ModelRetryMiddleware(
                max_retries=settings.MODEL_CALL_MAX_RETRIES,
                initial_delay=settings.MODEL_CALL_RETRY_INITIAL_DELAY_SECONDS,
                on_failure="error",
            ),
            SummarizationMiddleware(
                model=self._summary_model,
                trigger=("tokens", settings.SUMMARY_MAX_TOKENS),
                keep=("tokens", settings.SUMMARY_MAX_TOKENS // 2),
            ),
            ToolCallLimitMiddleware(
                run_limit=settings.TOOL_CALL_RUN_LIMIT, thread_limit=settings.TOOL_CALL_THREAD_LIMIT or None
            ),
            ToolErrorMiddleware(on_error=_tool_error_message),
            # Innermost, so every retry and fallback attempt is logged with the model that served it.
            wrap_model_call(_log_model_call),
            wrap_tool_call(_log_tool_call),
        ]

        self._graph: CompiledStateGraph[AgentState, GraphContext, InputAgentState, OutputAgentState] = create_agent(
            model=self._chat_model,
            tools=self._tools,
            checkpointer=InMemorySaver(),
            context_schema=GraphContext,
            middleware=middleware,
            store=InMemoryStore(),
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
        try:
            result = await self._graph.ainvoke(
                {"messages": [HumanMessage(content=content, id=message_id)]},  # type: ignore
                config=config,
                context=GraphContext(user=user),
            )
        except PIIDetectionError as error:
            # The input is checkpointed before the block, so drop it or later turns would send it to the model.
            await self._graph.aupdate_state(config, {"messages": [RemoveMessage(id=message_id)]}, as_node="model")
            logger.warning("message_blocked", chat_session_id=chat_session_id, pii_type=error.pii_type)
            raise

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
