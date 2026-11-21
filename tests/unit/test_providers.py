"""Tests for the LLM and embedding provider factory (N2).

Covers: get_llm(), get_embedding_model(), FakeChatModel, FakeEmbeddings,
and the LLM readiness check.  All tests run fully offline.
"""

from __future__ import annotations

import math

import pytest

from app.core.llm import (
    FakeChatModel,
    FakeEmbeddings,
    get_embedding_model,
    get_llm,
)

# ---------------------------------------------------------------------------
# FakeChatModel
# ---------------------------------------------------------------------------


class TestFakeChatModel:
    def test_invoke_returns_ai_message(self):
        """FakeChatModel.invoke() returns an object with a string .content (N2)."""
        llm = FakeChatModel()
        result = llm.invoke("What happened to the Payments API?")
        assert hasattr(result, "content")
        assert isinstance(result.content, str)
        assert len(result.content) > 0

    def test_deterministic_on_same_input(self):
        """Same input always produces the same output (N1)."""
        llm = FakeChatModel()
        r1 = llm.invoke("canonical question")
        r2 = llm.invoke("canonical question")
        assert r1.content == r2.content

    def test_different_inputs_produce_different_outputs(self):
        """Different inputs should produce different hash prefixes."""
        llm = FakeChatModel()
        r1 = llm.invoke("question A")
        r2 = llm.invoke("question B")
        assert r1.content != r2.content

    def test_invoke_with_message_list(self):
        """FakeChatModel accepts a list of message-like objects (N2)."""
        from langchain_core.messages import HumanMessage  # noqa: PLC0415

        llm = FakeChatModel()
        messages = [HumanMessage(content="Who owns the Payments API service?")]
        result = llm.invoke(messages)
        assert result.content

    def test_bind_tools_returns_self(self):
        """bind_tools() is a no-op for the fake model — returns self."""
        llm = FakeChatModel()
        bound = llm.bind_tools([])
        assert bound is llm

    def test_llm_type_is_fake(self):
        """_llm_type property returns 'fake'."""
        assert FakeChatModel()._llm_type == "fake"


# ---------------------------------------------------------------------------
# get_llm() factory
# ---------------------------------------------------------------------------


class TestGetLlm:
    def test_default_provider_is_fake(self, monkeypatch):
        """With LLM_PROVIDER=fake, get_llm() returns a FakeChatModel (N1)."""
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        from app.core.config import reset_settings_cache

        reset_settings_cache()
        llm = get_llm()
        assert isinstance(llm, FakeChatModel)

    def test_explicit_fake_provider(self):
        """get_llm('fake') always returns a FakeChatModel."""
        llm = get_llm(provider="fake")
        assert isinstance(llm, FakeChatModel)

    def test_real_provider_without_key_raises_value_error(self, monkeypatch):
        """openai without LLM_API_KEY raises ValueError at call time, not import (N2)."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_API_KEY", "")
        from app.core.config import reset_settings_cache

        reset_settings_cache()
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            get_llm()

    def test_anthropic_without_key_raises_value_error(self, monkeypatch):
        """anthropic without LLM_API_KEY raises ValueError."""
        monkeypatch.setenv("LLM_API_KEY", "")
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            get_llm(provider="anthropic")

    def test_unknown_provider_raises_value_error(self):
        """An unrecognised provider name raises ValueError with a helpful message."""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm(provider="nonexistent-ai")

    def test_provider_name_is_case_insensitive(self):
        """Provider lookup is case-insensitive (FAKE == fake)."""
        llm = get_llm(provider="FAKE")
        assert isinstance(llm, FakeChatModel)


# ---------------------------------------------------------------------------
# FakeEmbeddings
# ---------------------------------------------------------------------------


class TestFakeEmbeddings:
    def test_embed_query_returns_list_of_floats(self):
        """embed_query() returns a non-empty list of floats (N2)."""
        emb = FakeEmbeddings()
        vec = emb.embed_query("Payments API outage")
        assert isinstance(vec, list)
        assert len(vec) == 1536
        assert all(isinstance(v, float) for v in vec)

    def test_embed_query_deterministic(self):
        """Same text always yields the same vector (N1)."""
        emb = FakeEmbeddings()
        v1 = emb.embed_query("test sentence")
        v2 = emb.embed_query("test sentence")
        assert v1 == v2

    def test_embed_different_texts_differ(self):
        """Different texts produce different vectors."""
        emb = FakeEmbeddings()
        v1 = emb.embed_query("hello world")
        v2 = emb.embed_query("goodbye world")
        assert v1 != v2

    def test_embed_query_unit_normalised(self):
        """Embedding vectors are unit-normalised (magnitude ≈ 1.0)."""
        emb = FakeEmbeddings()
        vec = emb.embed_query("normalisation check")
        magnitude = math.sqrt(sum(v * v for v in vec))
        assert abs(magnitude - 1.0) < 1e-6

    def test_embed_documents_batch(self):
        """embed_documents() returns one vector per input text."""
        emb = FakeEmbeddings()
        texts = ["doc one", "doc two", "doc three"]
        vecs = emb.embed_documents(texts)
        assert len(vecs) == 3
        for v in vecs:
            assert len(v) == 1536

    def test_embed_documents_matches_embed_query(self):
        """embed_documents(['x'])[0] == embed_query('x')."""
        emb = FakeEmbeddings()
        text = "consistency check"
        assert emb.embed_documents([text])[0] == emb.embed_query(text)


# ---------------------------------------------------------------------------
# get_embedding_model() factory
# ---------------------------------------------------------------------------


class TestGetEmbeddingModel:
    def test_default_is_fake(self, monkeypatch):
        """With EMBEDDING_PROVIDER=fake, get_embedding_model() returns FakeEmbeddings."""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
        from app.core.config import reset_settings_cache

        reset_settings_cache()
        emb = get_embedding_model()
        assert isinstance(emb, FakeEmbeddings)

    def test_explicit_fake_provider(self):
        """get_embedding_model('fake') always returns FakeEmbeddings."""
        emb = get_embedding_model(provider="fake")
        assert isinstance(emb, FakeEmbeddings)

    def test_real_provider_without_key_raises_value_error(self, monkeypatch):
        """openai embedding without LLM_API_KEY raises ValueError."""
        monkeypatch.setenv("LLM_API_KEY", "")
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            get_embedding_model(provider="openai")

    def test_unknown_provider_raises_value_error(self):
        """Unrecognised embedding provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_model(provider="unknown-embed")


# ---------------------------------------------------------------------------
# LLM health check
# ---------------------------------------------------------------------------


class TestLlmHealthCheck:
    def test_health_check_reports_ok_for_fake(self, client):
        """GET /health/ready includes llm: ok when LLM_PROVIDER=fake (N2)."""
        response = client.get("/health/ready")
        assert response.status_code in (200, 503)
        body = response.json()
        assert "llm" in body["checks"]
        assert body["checks"]["llm"]["status"] == "ok"
        assert body["checks"]["llm"]["detail"] == "fake"
