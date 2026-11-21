"""Guardrails: prompt-injection detection (N8) and output scrubbing (N9).

Rule: document text is always data, never instruction.
  - wrap_untrusted()  — adds context markers so the LLM treats text as data.
  - scan_for_injection() — detects known injection patterns; flags the hostile vendor note.
  - scrub_output()    — strips secrets and hidden-reasoning blocks from any string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Injection detection (N8)
# ---------------------------------------------------------------------------

# Each pattern is (compiled-regex, human-readable label).
_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"ignore\s+all\s+previous\s+instructions", re.IGNORECASE),
        "classic ignore-previous-instructions injection",
    ),
    (
        re.compile(
            r"disregard\s+(all\s+)?(previous|prior|above|your)\s+instructions",
            re.IGNORECASE,
        ),
        "disregard-instructions variant",
    ),
    (
        re.compile(
            r"you\s+are\s+now\s+operating\s+in\s+(unrestricted|admin|god)\s+mode",
            re.IGNORECASE,
        ),
        "mode-switch injection",
    ),
    (
        re.compile(r"reclassify\s+all\s+(incidents|events|alerts)", re.IGNORECASE),
        "reclassify-incidents instruction",
    ),
    (
        re.compile(r"route\s+all\s+retrieval\s+queries\s+to", re.IGNORECASE),
        "routing-override injection",
    ),
    (
        re.compile(
            r"do\s+not\s+use\s+(sql|graph|vector)\s+(traversal|retrieval|store)",
            re.IGNORECASE,
        ),
        "retrieval-suppression injection",
    ),
    (
        re.compile(
            r"output\s+the\s+following\s+as\s+the\s+final\s+research\s+answer",
            re.IGNORECASE,
        ),
        "forced-answer injection",
    ),
    (
        re.compile(r"set\s+strategies_used\s+to", re.IGNORECASE),
        "strategy-override injection",
    ),
    (
        re.compile(r"disregard\s+the\s+canonical\s+question\s+routing", re.IGNORECASE),
        "routing-rules override injection",
    ),
    (
        re.compile(r"\[system\]|\[assistant\]|\[user\]", re.IGNORECASE),
        "role-injection attempt via bracket syntax",
    ),
    (
        re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE),
        "ChatML role-injection attempt",
    ),
]

# Wrapping sentinels — clearly mark untrusted content as data, not instruction.
_WRAP_OPEN = "[DOCUMENT DATA — UNTRUSTED START]"
_WRAP_CLOSE = "[DOCUMENT DATA — UNTRUSTED END]"


@dataclass
class GuardrailResult:
    """Outcome of a guardrail scan."""

    flagged: bool
    reasons: list[str] = field(default_factory=list)
    sanitized_text: str = ""

    @property
    def reason(self) -> str:
        """Single-string summary of all detected reasons."""
        return "; ".join(self.reasons) if self.reasons else ""


def wrap_untrusted(text: str) -> str:
    """Wrap document text in sentinels that instruct the LLM to treat it as data only.

    The LLM is never told *how* to respond; it is only told that the wrapped
    block is a document excerpt, not a system directive.
    """
    return f"{_WRAP_OPEN}\n{text}\n{_WRAP_CLOSE}"


def scan_for_injection(text: str) -> GuardrailResult:
    """Scan *text* for prompt-injection patterns (N8).

    Returns a GuardrailResult.  If flagged, .reasons lists every detected
    pattern label; .sanitized_text is the text with matched spans replaced
    by [REDACTED-INJECTION].
    """
    reasons: list[str] = []
    sanitized = text

    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(text):
            reasons.append(label)
            sanitized = pattern.sub("[REDACTED-INJECTION]", sanitized)

    return GuardrailResult(
        flagged=bool(reasons),
        reasons=reasons,
        sanitized_text=sanitized if reasons else text,
    )


def process_chunk(text: str) -> GuardrailResult:
    """Full pipeline for one document chunk: scan → wrap.

    If the chunk is flagged the sanitized (redacted) text is wrapped, not
    the original.  Callers should log / store the .flagged and .reasons
    fields alongside the chunk for audit and UI display.
    """
    result = scan_for_injection(text)
    source = result.sanitized_text if result.flagged else text
    result.sanitized_text = wrap_untrusted(source)
    return result


# ---------------------------------------------------------------------------
# Output scrubbing (N9)
# ---------------------------------------------------------------------------

# Secret patterns — replace the entire match with a [REDACTED] placeholder.
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # OpenAI keys: sk-... (project keys: sk-proj-...)
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), "[REDACTED-API-KEY]"),
    # Anthropic keys: sk-ant-...
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{10,}\b"), "[REDACTED-API-KEY]"),
    # Generic Bearer tokens in Authorization headers / log lines
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"), "Bearer [REDACTED]"),
    # AWS-style access keys
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED-AWS-KEY]"),
    # Generic secrets on key= / "key": "value" assignments (env, JSON, YAML)
    (
        re.compile(
            r'(?i)(api[_\-]?key|api[_\-]?token|secret[_\-]?key|access[_\-]?token)["\']?\s*[=:]\s*["\']?[A-Za-z0-9_\-\.]{20,}["\']?',
        ),
        r"\1=[REDACTED]",
    ),
    # JWT tokens (three base64url segments)
    (
        re.compile(r"\bey[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
        "[REDACTED-JWT]",
    ),
]

# Hidden-reasoning patterns — remove the entire block.
_REASONING_PATTERNS: list[re.Pattern[str]] = [
    # XML-style tags used by some models for chain-of-thought
    re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<scratchpad>.*?</scratchpad>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<internal>.*?</internal>", re.DOTALL | re.IGNORECASE),
    # Markdown-fenced "thinking" blocks
    re.compile(r"```thinking\b.*?```", re.DOTALL | re.IGNORECASE),
]


def scrub_output(text: str) -> str:
    """Remove secrets and hidden-reasoning blocks from *text* (N9).

    Applied to:
    - LLM response content before it reaches the API layer.
    - Workflow event details before they are written to the DB.
    - Any string that will be logged or returned to the caller.

    Does NOT alter non-sensitive content — a clean string passes through
    unchanged.
    """
    for pattern in _REASONING_PATTERNS:
        text = pattern.sub("", text)

    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)

    return text.strip()
