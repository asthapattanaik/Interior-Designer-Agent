"""Shared ChatOpenAI construction for agent LLM stages."""

from __future__ import annotations

from typing import TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import Settings, SettingsError, load_settings

T = TypeVar("T", bound=BaseModel)


class LlmError(RuntimeError):
    """Raised when an LLM stage cannot run or returns unusable output."""


def build_chat_model(settings: Settings | None = None) -> ChatOpenAI:
    """Build ChatOpenAI from validated settings. OPENAI_API_KEY is required."""
    cfg = settings or load_settings()
    if not cfg.openai_api_key.strip():
        raise SettingsError("OPENAI_API_KEY is required")
    return ChatOpenAI(model=cfg.openai_model, api_key=cfg.openai_api_key)


def build_structured_model(schema: type[T], settings: Settings | None = None):
    """Return a ChatOpenAI runnable with structured output for `schema`."""
    return build_chat_model(settings).with_structured_output(schema)


def invoke_structured(runner, messages: list | dict | str, *, stage: str, schema: type[T]) -> T:
    """Invoke a structured LLM runnable and validate the result as `schema`."""
    try:
        result = runner.invoke(messages)
    except SettingsError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface provider errors clearly
        raise LlmError(
            f"LLM stage '{stage}' failed. Check OPENAI_API_KEY and OPENAI_MODEL. "
            f"Details: {exc}"
        ) from exc
    if isinstance(result, schema):
        return result
    try:
        return schema.model_validate(result)
    except Exception as exc:  # noqa: BLE001
        raise LlmError(
            f"LLM stage '{stage}' returned output that does not match {schema.__name__}: {exc}"
        ) from exc
