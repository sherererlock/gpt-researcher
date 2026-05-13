"""LangChain-compatible wrapper for the TowerAI SDK."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import model_validator

# Path to the TowerAI SDK root (directory containing the `towerai` package).
_TOWERAI_SDK_PATH = os.environ.get(
    "TOWERAI_PATH", r"E:\workspace\GitRepository\TowerAI"
)


def _get_client():
    if _TOWERAI_SDK_PATH and _TOWERAI_SDK_PATH not in sys.path:
        sys.path.insert(0, _TOWERAI_SDK_PATH)
    from towerai import create_client  # type: ignore[import]

    return create_client()


def _to_towerai_messages(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    role_map = {
        HumanMessage: "user",
        AIMessage: "assistant",
        SystemMessage: "system",
    }
    result = []
    for msg in messages:
        role = role_map.get(type(msg), "user")
        if isinstance(msg.content, str):
            content = msg.content
        else:
            content = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in msg.content
            )
        result.append({"role": role, "content": content})
    return result


class ChatTowerAI(BaseChatModel):
    """LangChain chat model backed by the TowerAI gateway."""

    model: str = "gpt-5.5"
    temperature: Optional[float] = 0.7

    @model_validator(mode="after")
    def _validate(self) -> "ChatTowerAI":
        return self

    @property
    def _llm_type(self) -> str:
        return "towerai"

    def _build_kwargs(self) -> Dict[str, Any]:
        kw: Dict[str, Any] = {"model": self.model}
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        return kw

    # ------------------------------------------------------------------ sync

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        client = _get_client()
        try:
            response = client.chat.completions.create(
                messages=_to_towerai_messages(messages),
                **self._build_kwargs(),
            )
            content = response.choices[0].message.content or ""
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=content))]
            )
        finally:
            client.close()

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        client = _get_client()
        try:
            for chunk in client.chat.completions.create(
                messages=_to_towerai_messages(messages),
                stream=True,
                **self._build_kwargs(),
            ):
                if chunk.choices and chunk.choices[0].delta.content:
                    yield ChatGenerationChunk(
                        message=AIMessageChunk(content=chunk.choices[0].delta.content)
                    )
        finally:
            client.close()

    # ----------------------------------------------------------------- async

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._generate(messages, stop)
        )

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ):
        loop = asyncio.get_event_loop()

        def _collect() -> List[ChatGenerationChunk]:
            return list(self._stream(messages, stop))

        chunks = await loop.run_in_executor(None, _collect)
        for chunk in chunks:
            yield chunk
