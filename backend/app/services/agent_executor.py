"""LangChain tool-calling agent runtime with event streaming.

`AgentRuntime.stream()` yields plain dict events, consumed by the SSE chat
endpoint and (via `run()`) by the chain runner:

    {"type": "token",      "content": "..."}
    {"type": "tool_start", "run_id": "...", "tool_name": "...", "input": {...}}
    {"type": "tool_end",   "run_id": "...", "tool_name": "...", "output": ..., "error": ..., "duration_ms": 12.3}
    {"type": "retrieval",  "chunks": [{text, source_file, score, ...}]}
    {"type": "final",      "content": "...", "tool_calls": [...]}
"""

import json
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config import Settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.models.agent import AgentPublic
from app.models.conversation import ToolCallRecord
from app.services.rag_pipeline import RAGPipeline
from app.services.tool_registry import get_tools, tool_result

logger = get_logger(__name__)

RETRIEVAL_TOOL_NAME = "retrieve_context"

_KB_INSTRUCTIONS = (
    "\n\nYou have access to a knowledge base through the `retrieve_context` tool. "
    "Use it whenever the user's question could be answered from their documents, and "
    "cite the source file names you relied on. If the knowledge base has nothing "
    "relevant, say so instead of guessing."
)

AgentEvent = dict[str, Any]


@dataclass
class AgentRunResult:
    output: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


def _chunk_text(content: Any) -> str:
    """Normalise message content (str or list of content blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )
    return ""


def _parse_tool_output(raw: Any) -> tuple[Any, str | None]:
    """Unwrap our structured tool JSON into (output, error)."""
    raw = getattr(raw, "content", raw)  # ToolMessage -> str
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except ValueError:
            return raw, None
        if isinstance(data, dict) and "tool_name" in data:
            return data.get("output"), data.get("error")
        return data, None
    return raw, None


def history_to_messages(history: Sequence[dict[str, Any]]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for item in history:
        content = str(item.get("content", ""))
        if item.get("role") == "user":
            messages.append(HumanMessage(content=content))
        elif item.get("role") == "assistant" and content:
            messages.append(AIMessage(content=content))
    return messages


class AgentRuntime:
    def __init__(self, settings: Settings, rag: RAGPipeline) -> None:
        self._settings = settings
        self._rag = rag

    # ----------------------------------------------------------------- builders
    def _llm(self, agent: AgentPublic) -> ChatOpenAI:
        if not self._settings.openai_api_key:
            raise ExternalServiceError("LLM is not configured: set OPENAI_API_KEY (and MODEL_NAME) in .env")
        return ChatOpenAI(
            model=agent.model or self._settings.model_name,
            temperature=agent.temperature,
            api_key=SecretStr(self._settings.openai_api_key),
            base_url=self._settings.openai_base_url,
            streaming=True,
            timeout=self._settings.llm_timeout_seconds,
            max_retries=2,
        )

    def _retrieval_tool(self, knowledge_base_id: str) -> BaseTool:
        rag = self._rag

        @tool(RETRIEVAL_TOOL_NAME)
        async def retrieve_context(query: str) -> str:
            """Search the agent's knowledge base (the user's uploaded documents) and return
            the most relevant passages with their source file names and relevance scores."""
            args = {"query": query}
            try:
                chunks = await rag.retrieve(knowledge_base_id, query)
            except Exception as exc:
                logger.warning("retrieval_failed", error=str(exc), kb_id=knowledge_base_id)
                return tool_result(RETRIEVAL_TOOL_NAME, args, error=f"Retrieval failed: {exc}")
            return tool_result(RETRIEVAL_TOOL_NAME, args, [c.model_dump() for c in chunks])

        return retrieve_context

    def _tools(self, agent: AgentPublic) -> list[BaseTool]:
        tools = get_tools(list(agent.tools))
        if agent.knowledge_base_id:
            tools.append(self._retrieval_tool(agent.knowledge_base_id))
        return tools

    def _system_prompt(self, agent: AgentPublic) -> str:
        return agent.system_prompt + (_KB_INSTRUCTIONS if agent.knowledge_base_id else "")

    def _executor(self, agent: AgentPublic, llm: ChatOpenAI, tools: list[BaseTool]) -> AgentExecutor:
        # A SystemMessage instance (not a template string) so braces in user prompts are literal.
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self._system_prompt(agent)),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        return AgentExecutor(
            agent=create_tool_calling_agent(llm, tools, prompt),
            tools=tools,
            max_iterations=self._settings.agent_max_iterations,
            max_execution_time=180,
            handle_parsing_errors=True,
        )

    # ---------------------------------------------------------------- execution
    async def stream(
        self, agent: AgentPublic, user_message: str, history: Sequence[dict[str, Any]] = ()
    ) -> AsyncIterator[AgentEvent]:
        llm = self._llm(agent)
        tools = self._tools(agent)
        chat_history = history_to_messages(history)
        parts: list[str] = []
        tool_calls: list[ToolCallRecord] = []

        if not tools:
            # Plain chat: tool-calling APIs reject an empty tool list.
            messages = [SystemMessage(content=self._system_prompt(agent)), *chat_history, HumanMessage(user_message)]
            async for chunk in llm.astream(messages):
                text = _chunk_text(chunk.content)
                if text:
                    parts.append(text)
                    yield {"type": "token", "content": text}
            yield {"type": "final", "content": "".join(parts), "tool_calls": []}
            return

        executor = self._executor(agent, llm, tools)
        started: dict[str, tuple[float, str, Any]] = {}
        final_output: str | None = None

        async for event in executor.astream_events(
            {"input": user_message, "chat_history": chat_history}, version="v2"
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                text = _chunk_text(event["data"]["chunk"].content)
                if text:
                    parts.append(text)
                    yield {"type": "token", "content": text}

            elif kind == "on_tool_start":
                # Separate any "thinking out loud" text from the eventual answer.
                if parts and not parts[-1].endswith("\n"):
                    parts.append("\n\n")
                    yield {"type": "token", "content": "\n\n"}
                tool_input = event["data"].get("input")
                started[event["run_id"]] = (time.perf_counter(), event["name"], tool_input)
                yield {"type": "tool_start", "run_id": event["run_id"], "tool_name": event["name"], "input": tool_input}

            elif kind in {"on_tool_end", "on_tool_error"}:
                start, name, tool_input = started.pop(
                    event["run_id"], (time.perf_counter(), event["name"], event["data"].get("input"))
                )
                if kind == "on_tool_end":
                    output, error = _parse_tool_output(event["data"].get("output"))
                else:
                    output, error = None, str(event["data"].get("error"))
                duration_ms = round((time.perf_counter() - start) * 1000, 1)
                record = ToolCallRecord(
                    tool_name=name, input=tool_input, output=output, error=error, duration_ms=duration_ms
                )
                tool_calls.append(record)
                yield {"type": "tool_end", "run_id": event["run_id"], **record.model_dump()}
                if name == RETRIEVAL_TOOL_NAME and isinstance(output, list):
                    yield {"type": "retrieval", "chunks": output}

            elif kind == "on_chain_end" and not event.get("parent_ids"):
                output = event["data"].get("output")
                if isinstance(output, dict):
                    final_output = str(output.get("output", ""))

        content = "".join(parts).strip()
        if not content and final_output:
            # Provider didn't stream tokens; emit the whole answer at once.
            content = final_output
            yield {"type": "token", "content": final_output}
        yield {"type": "final", "content": content, "tool_calls": [tc.model_dump() for tc in tool_calls]}

    async def run(
        self, agent: AgentPublic, user_message: str, history: Sequence[dict[str, Any]] = ()
    ) -> AgentRunResult:
        """Non-streaming execution (used by multi-agent chains)."""
        result = AgentRunResult(output="")
        async for event in self.stream(agent, user_message, history):
            if event["type"] == "final":
                result.output = event["content"]
                result.tool_calls = [ToolCallRecord.model_validate(tc) for tc in event["tool_calls"]]
        return result
