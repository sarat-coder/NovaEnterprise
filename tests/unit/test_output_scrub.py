"""Tests for output scrubbing — secrets and hidden reasoning (N9).

Proves that:
- API keys matching common patterns are redacted
- Bearer tokens are redacted
- JWT tokens are redacted
- <thinking>…</thinking> blocks are removed
- <reasoning>…</reasoning> blocks are removed
- clean text passes through unchanged
- non-secret content is preserved
"""

from __future__ import annotations

from app.core.guardrails import scrub_output

# ---------------------------------------------------------------------------
# Secret scrubbing
# ---------------------------------------------------------------------------


class TestSecretScrubbing:
    def test_openai_key_redacted(self):
        """An OpenAI-style sk-... key is redacted (N9)."""
        text = "API key: sk-abcdefghijklmnopqrstuvwxyz1234567890"
        scrubbed = scrub_output(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in scrubbed
        assert "[REDACTED" in scrubbed

    def test_anthropic_key_redacted(self):
        """An Anthropic-style sk-ant-... key is redacted (N9)."""
        text = "Using key sk-ant-api03-abcdef1234567890ABCDEF-xyzxyz"
        scrubbed = scrub_output(text)
        assert "sk-ant-api03" not in scrubbed

    def test_bearer_token_redacted(self):
        """Bearer token in a log line is redacted (N9)."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.sig"
        scrubbed = scrub_output(text)
        assert "Bearer [REDACTED]" in scrubbed

    def test_jwt_token_redacted(self):
        """A three-segment JWT is redacted from free text (N9)."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        text = f"User token: {jwt}"
        scrubbed = scrub_output(text)
        assert jwt not in scrubbed
        assert "[REDACTED" in scrubbed

    def test_assignment_style_api_key_redacted(self):
        """api_key=<long-value> pattern is redacted (N9)."""
        text = 'config = {"api_key": "supersecretvalue12345678901234"}'
        scrubbed = scrub_output(text)
        assert "supersecretvalue" not in scrubbed

    def test_aws_access_key_redacted(self):
        """AWS AKIA... key is redacted (N9)."""
        text = "aws_access_key_id = AKIAIOSFODNN7EXAMPLE"
        scrubbed = scrub_output(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed


# ---------------------------------------------------------------------------
# Hidden reasoning removal
# ---------------------------------------------------------------------------


class TestHiddenReasoningRemoval:
    def test_thinking_block_removed(self):
        """<thinking>…</thinking> block is removed from output (N9)."""
        text = (
            "Here is my answer. "
            "<thinking>Let me first reason about this step by step.</thinking>"
            " The Payments API was affected by INC-2031."
        )
        scrubbed = scrub_output(text)
        assert "<thinking>" not in scrubbed
        assert "Let me first reason" not in scrubbed
        assert "The Payments API was affected" in scrubbed

    def test_reasoning_block_removed(self):
        """<reasoning>…</reasoning> block is stripped (N9)."""
        text = "<reasoning>Chain of thought here.</reasoning>Final answer."
        scrubbed = scrub_output(text)
        assert "<reasoning>" not in scrubbed
        assert "Chain of thought here" not in scrubbed
        assert "Final answer" in scrubbed

    def test_scratchpad_block_removed(self):
        """<scratchpad>…</scratchpad> block is stripped (N9)."""
        text = "<scratchpad>temp notes</scratchpad>Answer: 42"
        scrubbed = scrub_output(text)
        assert "temp notes" not in scrubbed
        assert "Answer: 42" in scrubbed

    def test_multiline_thinking_block_removed(self):
        """Multi-line <thinking> blocks (spanning newlines) are removed (N9)."""
        text = (
            "Public answer.\n"
            "<thinking>\n"
            "  Step 1: analyse the question.\n"
            "  Step 2: retrieve from SQL.\n"
            "</thinking>\n"
            "Here is the cited result."
        )
        scrubbed = scrub_output(text)
        assert "Step 1" not in scrubbed
        assert "Step 2" not in scrubbed
        assert "Here is the cited result" in scrubbed

    def test_fenced_thinking_block_removed(self):
        """Markdown ```thinking … ``` fenced block is stripped."""
        text = "Result: X\n```thinking\nmy private notes\n```\nEnd."
        scrubbed = scrub_output(text)
        assert "my private notes" not in scrubbed
        assert "Result: X" in scrubbed


# ---------------------------------------------------------------------------
# Clean text — no false positives
# ---------------------------------------------------------------------------


class TestCleanTextPreserved:
    def test_normal_research_answer_unchanged(self):
        """A clean research answer is returned unchanged (no false positives, N9)."""
        text = (
            "Three customers were impacted by the Payments API outage [1]: "
            "TechCorp, GlobalRetail, and FinanceHub. "
            "The root cause was a misconfigured load balancer [2]."
        )
        scrubbed = scrub_output(text)
        assert "TechCorp" in scrubbed
        assert "misconfigured load balancer" in scrubbed

    def test_citation_markers_preserved(self):
        """[1] style citation markers are not accidentally removed."""
        text = "Service owned by Payments Platform team [3]."
        scrubbed = scrub_output(text)
        assert "[3]" in scrubbed

    def test_empty_string_returns_empty(self):
        """scrub_output('') returns ''."""
        assert scrub_output("") == ""

    def test_short_alphanumeric_not_redacted(self):
        """Short strings that superficially look like keys but are too short are kept."""
        text = "version: sk-v2 token: abc123"
        scrubbed = scrub_output(text)
        # 'sk-v2' is 4 chars after sk- — below the 20-char minimum → preserved
        assert "sk-v2" in scrubbed


# ---------------------------------------------------------------------------
# Combined: secrets inside a reasoning block
# ---------------------------------------------------------------------------


def test_secret_inside_reasoning_block_removed():
    """An API key inside a <thinking> block is removed along with the block (N9)."""
    text = (
        "<thinking>I will use sk-abc123def456ghi789jkl012mno345 for the API call.</thinking>"
        "The answer is 42."
    )
    scrubbed = scrub_output(text)
    assert "sk-abc123def456" not in scrubbed
    assert "The answer is 42" in scrubbed
