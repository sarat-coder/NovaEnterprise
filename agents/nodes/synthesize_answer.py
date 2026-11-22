"""Node: synthesize_answer — produce a cited answer using collected evidence (F11)."""

from __future__ import annotations

from agents.state import ResearchState
from app.core.guardrails import wrap_untrusted
from app.core.llm import get_llm


def synthesize_answer(state: ResearchState) -> ResearchState:
    llm = get_llm()
    evidence = state.get("evidence", [])

    if not evidence:
        return {
            **state,
            "answer": "No evidence was collected for this question.",
            "citations_valid": False,
        }

    # Build evidence block — wrap each item so LLM treats content as data
    evidence_lines = []
    for ev in evidence:
        num = ev.metadata.get("citation_number", "?")
        safe_content = wrap_untrusted(ev.content)
        evidence_lines.append(f"[{num}] ({ev.source_type}) {safe_content}")
    evidence_block = "\n".join(evidence_lines)

    prompt = (
        f"Question: {state['question']}\n\n"
        f"Evidence:\n{evidence_block}\n\n"
        "Write a comprehensive cited answer. Use [n] markers for each fact. "
        "Every claim must cite at least one evidence item."
    )

    from langchain_core.messages import HumanMessage  # noqa: PLC0415

    result = llm.invoke([HumanMessage(content=prompt)])
    answer = result.content if hasattr(result, "content") else str(result)

    return {**state, "answer": answer}
