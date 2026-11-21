"""AI provider factory for LLMs and embedding models (N2).

Design rule: selecting a real provider without a key fails at call time
with a clear ValueError — never at import time, never silently.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from app.core.config import get_settings
from app.core.health import register_check

# ---------------------------------------------------------------------------
# Fake provider — deterministic, no API key, no network (N1)
# ---------------------------------------------------------------------------


class FakeChatModel:
    """Deterministic fake chat model for offline testing (N1, N2).

    Implements the minimal LangChain Runnable interface so agents can call
    .invoke() without caring which provider is active.  Returns a fixed
    string keyed on the content hash of the last message.
    """

    model_name: str = "fake"

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        from langchain_core.messages import AIMessage  # noqa: PLC0415

        content = _last_content(messages)
        h = hashlib.md5(content.encode()).hexdigest()[:8]
        response = f"[fake-{h}] Research analysis complete. No external calls made."
        return AIMessage(content=response)

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return self.invoke(messages, **kwargs)

    def stream(self, messages: Any, **kwargs: Any):
        result = self.invoke(messages, **kwargs)
        yield result

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeChatModel:
        return self

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _FakeStructuredModel:
        return _FakeStructuredModel(schema=schema)

    @property
    def _llm_type(self) -> str:
        return "fake"


class _FakeStructuredModel:
    """Fake structured-output wrapper; returns a zeroed instance of the schema."""

    def __init__(self, schema: Any) -> None:
        self._schema = schema

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        # Return a minimal valid instance so callers don't crash.
        try:
            return self._schema()
        except Exception:
            return {}

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return self.invoke(messages, **kwargs)


class FakeEmbeddings:
    """Deterministic unit-normalised fake embeddings for offline testing (N1, N2).

    Same text always produces the same vector; different texts produce
    different vectors. Vectors are unit-normalised (cosine similarity ready).
    """

    dimensions: int = 1536

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(self.dimensions)]
        magnitude = sum(x * x for x in vec) ** 0.5
        return [x / magnitude for x in vec] if magnitude > 0 else vec


# ---------------------------------------------------------------------------
# Provider factories
# ---------------------------------------------------------------------------

_KNOWN_LLM_PROVIDERS = frozenset(
    {"fake", "openai", "anthropic", "azure", "google", "cohere", "mistral", "ollama"}
)
_KNOWN_EMBEDDING_PROVIDERS = frozenset(
    {"fake", "openai", "anthropic", "cohere", "google", "ollama"}
)


def get_llm(provider: str | None = None) -> Any:
    """Return a chat model for the configured (or given) provider.

    Providers other than 'fake' require LLM_API_KEY (except 'ollama').
    Import errors for optional packages are surfaced as ImportError with
    an install hint, not at module load time.
    """
    settings = get_settings()
    p = (provider or settings.llm_provider).lower()

    if p == "fake":
        return FakeChatModel()

    if p not in _KNOWN_LLM_PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider {p!r}. Choose from: {', '.join(sorted(_KNOWN_LLM_PROVIDERS))}"
        )

    # --- real providers below: validate key first -------------------------
    if p != "ollama" and not settings.llm_api_key:
        raise ValueError(
            f"LLM_API_KEY must be set when using the {p!r} provider. "
            "Add it to .env and restart the backend."
        )

    if p == "openai":
        try:
            from langchain_openai import ChatOpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-openai") from exc
        return ChatOpenAI(
            api_key=settings.llm_api_key,
            model=settings.llm_model or "gpt-4o",
        )

    if p == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-anthropic") from exc
        return ChatAnthropic(
            api_key=settings.llm_api_key,
            model=settings.llm_model or "claude-opus-4-5",
        )

    if p == "azure":
        try:
            from langchain_openai import AzureChatOpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-openai") from exc
        return AzureChatOpenAI(
            api_key=settings.llm_api_key,
            model=settings.llm_model or "gpt-4o",
        )

    if p == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-google-genai") from exc
        return ChatGoogleGenerativeAI(
            google_api_key=settings.llm_api_key,
            model=settings.llm_model or "gemini-pro",
        )

    if p == "cohere":
        try:
            from langchain_cohere import ChatCohere  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-cohere") from exc
        return ChatCohere(
            cohere_api_key=settings.llm_api_key,
            model=settings.llm_model or "command-r-plus",
        )

    if p == "mistral":
        try:
            from langchain_mistralai import ChatMistralAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-mistralai") from exc
        return ChatMistralAI(
            api_key=settings.llm_api_key,
            model=settings.llm_model or "mistral-large-latest",
        )

    if p == "ollama":
        try:
            from langchain_ollama import ChatOllama  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-ollama") from exc
        return ChatOllama(model=settings.llm_model or "llama3")

    # Unreachable — kept for type-checker completeness.
    raise ValueError(f"Unhandled provider: {p!r}")  # pragma: no cover


def get_embedding_model(provider: str | None = None) -> Any:
    """Return an embedding model for the configured (or given) provider."""
    settings = get_settings()
    p = (provider or settings.embedding_provider).lower()

    if p == "fake":
        return FakeEmbeddings()

    if p not in _KNOWN_EMBEDDING_PROVIDERS:
        raise ValueError(
            f"Unknown embedding provider {p!r}. "
            f"Choose from: {', '.join(sorted(_KNOWN_EMBEDDING_PROVIDERS))}"
        )

    if p != "ollama" and not settings.llm_api_key:
        raise ValueError(
            f"LLM_API_KEY must be set when using the {p!r} embedding provider. "
            "Add it to .env and restart the backend."
        )

    if p == "openai":
        try:
            from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-openai") from exc
        return OpenAIEmbeddings(
            api_key=settings.llm_api_key,
            model=settings.embedding_model or "text-embedding-3-small",
        )

    if p == "anthropic":
        # Anthropic uses Voyage AI for embeddings
        try:
            from langchain_voyageai import VoyageAIEmbeddings  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-voyageai") from exc
        return VoyageAIEmbeddings(
            voyage_api_key=settings.llm_api_key,
            model=settings.embedding_model or "voyage-3",
        )

    if p == "cohere":
        try:
            from langchain_cohere import CohereEmbeddings  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-cohere") from exc
        return CohereEmbeddings(
            cohere_api_key=settings.llm_api_key,
            model=settings.embedding_model or "embed-english-v3.0",
        )

    if p == "google":
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-google-genai") from exc
        return GoogleGenerativeAIEmbeddings(
            google_api_key=settings.llm_api_key,
            model=settings.embedding_model or "models/embedding-001",
        )

    if p == "ollama":
        try:
            from langchain_ollama import OllamaEmbeddings  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add langchain-ollama") from exc
        return OllamaEmbeddings(model=settings.embedding_model or "nomic-embed-text")

    raise ValueError(f"Unhandled embedding provider: {p!r}")  # pragma: no cover


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def register_llm_check() -> None:
    """Register the LLM readiness check. Called once at startup."""

    def _check() -> dict[str, str]:
        try:
            get_llm()  # instantiates the configured provider
            return {"status": "ok", "detail": get_settings().llm_provider}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    register_check("llm", _check)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _last_content(messages: Any) -> str:
    """Extract string content from the last message in a list or single message."""
    if isinstance(messages, list):
        last = messages[-1] if messages else None
        if last is None:
            return ""
        content = getattr(last, "content", last)
        return str(content) if content is not None else ""
    content = getattr(messages, "content", messages)
    return str(content) if content is not None else ""
