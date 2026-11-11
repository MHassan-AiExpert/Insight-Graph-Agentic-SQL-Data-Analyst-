"""LLM provider abstraction.

Every agent step talks to the model through ``LLMClient.structured`` and
always receives a validated Pydantic object back.

* ``GroqLLM``     — production provider (LangChain ``ChatGroq`` + structured output)
* ``ScriptedLLM`` — deterministic provider used by the automated test-suite and
                    offline evaluation runs; it replays pre-defined responses,
                    so CI never needs network access or an API key.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, TypeVar

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when the language model call fails."""


class LLMClient(Protocol):
    provider: str
    model: str

    def structured(self, task: str, messages: list[BaseMessage], schema: type[T], *, key: str = "") -> T: ...


class GroqLLM:
    provider = "groq"

    def __init__(
        self,
        model: str,
        api_key: str | None,
        temperature: float = 0.0,
        timeout: float = 45.0,
        reasoning_effort: str | None = None,
    ):
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set. Add it to your .env file.")
        from langchain_groq import ChatGroq

        self.model = model
        extra: dict[str, Any] = {}
        if reasoning_effort and "gpt-oss" in model:
            extra["reasoning_effort"] = reasoning_effort
        self._chat = ChatGroq(
            model=model, api_key=api_key, temperature=temperature, timeout=timeout, max_retries=2, **extra
        )
        self._runnables: dict[type[BaseModel], Any] = {}

    def structured(self, task: str, messages: list[BaseMessage], schema: type[T], *, key: str = "") -> T:
        runnable = self._runnables.get(schema)
        if runnable is None:
            runnable = self._chat.with_structured_output(schema)
            self._runnables[schema] = runnable
        try:
            result = runnable.invoke(messages)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"{self.model} failed during '{task}': {exc}") from exc
        if result is None:
            raise LLMError(f"{self.model} returned no structured output for '{task}'.")
        return result if isinstance(result, schema) else schema.model_validate(result)


Responder = Callable[[str, list[BaseMessage], str], dict[str, Any]]


class ScriptedLLM:
    """Replays scripted responses per task.

    ``responses`` maps a task name (``intent``, ``tables``, ``sql``, ``insight``)
    to a list of payloads consumed in order. Alternatively ``scenarios`` maps a
    phrase contained in the question to its own ``responses`` dict.
    """

    provider = "scripted"
    model = "scripted-replay"

    def __init__(
        self,
        responses: dict[str, list[dict[str, Any]]] | None = None,
        scenarios: list[dict[str, Any]] | None = None,
    ):
        self._queues: dict[str, deque] = defaultdict(deque)
        for task, items in (responses or {}).items():
            self._queues[task].extend(items)
        self._scenarios = scenarios or []
        self._scenario_queues: dict[tuple[int, str], deque] = {}
        self.calls: list[tuple[str, str]] = []

    @classmethod
    def from_file(cls, path: str | Path) -> ScriptedLLM:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(responses=data.get("responses"), scenarios=data.get("scenarios"))

    def _scenario_payload(self, task: str, key: str) -> dict[str, Any] | None:
        lowered = key.lower()
        for idx, scenario in enumerate(self._scenarios):
            if scenario["match"].lower() in lowered:
                queue = self._scenario_queues.setdefault((idx, task), deque(scenario["responses"].get(task, [])))
                if not queue:
                    queue.extend(scenario["responses"].get(task, []))
                return queue.popleft() if queue else None
        return None

    def structured(self, task: str, messages: list[BaseMessage], schema: type[T], *, key: str = "") -> T:
        self.calls.append((task, key))
        payload = self._scenario_payload(task, key)
        if payload is None:
            if not self._queues[task]:
                raise LLMError(f"No scripted response left for task '{task}'.")
            payload = self._queues[task].popleft()
        return schema.model_validate(payload)


@lru_cache
def get_llm() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "scripted":
        if settings.scripted_responses_path:
            return ScriptedLLM.from_file(settings.scripted_responses_path)
        return ScriptedLLM()
    return GroqLLM(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        reasoning_effort=settings.llm_reasoning_effort,
    )
