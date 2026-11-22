# Phase 11 — Project System Design Evolution

## Starting Point: What Existed Before Phase 11

After Phases 1–10 we had:
- A fully configured FastAPI backend with auth, middleware, and health checks
- Four data stores: SQLite (SQL), MemoryVectorStore (documents), MemoryGraphStore (graph), Redis/fakeredis (memory)
- Complete retrieval tools: hybrid vector search, SQL templates, typed Cypher traversals
- Four memory scopes: organizational, conversation, session, analyst
- Guardrails for injection detection and output scrubbing
- A `ResearchSessionOut` schema waiting for a workflow to fill it

**Missing:** The workflow that actually runs — the agent brain that connects questions to answers.

---

## Design Stage 1: The Research State (TypedDict)

Before writing any node, we needed to define the shared state that flows through every step.

```mermaid
classDiagram
    class ResearchState {
        session_id: str
        question: str
        intent: str
        entities: list~str~
        time_range: dict
        needs_relationships: bool
        needs_aggregation: bool
        complexity: str
        sub_questions: list~SubQuestionState~
        evidence: list~Evidence~
        missing_evidence_keys: list~str~
        corrective_rounds: int
        answer: str
        citations_valid: bool
        strategies_used: list~str~
        error: str
    }

    class SubQuestionState {
        id: str
        question: str
        strategy: str
        status: str
        evidence_ids: list~str~
        error_detail: str
    }

    ResearchState "1" --> "0..*" SubQuestionState
```

**Design choice:** Use a Python `TypedDict` (not a Pydantic model, not a class) because:
- LangGraph expects dict-compatible state
- TypedDict provides IDE autocomplete and type checking at zero runtime cost
- The same dict can be spread with `{**state, "new_key": value}` to create updated copies

---

## Design Stage 2: Rules Layer — Deterministic Logic

The first file written was `agents/rules.py`. It answers: "What do we always do, regardless of the AI?"

```mermaid
flowchart TD
    Q["Question text"] --> A["analyze_question()"]
    A --> ENT["Extract entities\n(service names)"]
    A --> TR["Detect time range\n(last quarter → Q3 dates)"]
    A --> REL["needs_relationships?\n(which customers / which teams)"]
    
    ENT --> SCORE["classify_complexity()\nScore = relationships×2 + time×1 + entities×1 + strategies×2"]
    TR --> SCORE
    REL --> SCORE
    
    SCORE --> |"score ≤ 1"| SIMPLE["simple"]
    SCORE --> |"score 2–3"| MOD["moderate"]
    SCORE --> |"score ≥ 4"| COMPLEX["complex"]
    
    COMPLEX --> |"canonical pattern?"| FAST["_decompose_canonical()\n4 fixed sub-questions"]
    COMPLEX --> |"general"| GEN["General decomposition\nbased on flags"]
    SIMPLE --> ONE["1 sub-question\nvector only"]
```

**Key guarantee from CLAUDE.md:** A relationship question is **never** routed vector-only.  
`correct_routing()` is called after decomposition and hard-overrides any strategy that violates this.

---

## Design Stage 3: The 14-Node Workflow

Each node is a pure function: `(ResearchState) → ResearchState`. Nodes don't call HTTP, don't
hold persistent state, and don't know about each other.

```mermaid
flowchart TD
    START([Question]) --> AQ[analyze_query]
    AQ --> AC[assess_complexity]
    AC --> D[decompose]
    D --> RR[route_retrieval]
    RR --> VR[vector_retrieval]
    RR --> SR[sql_retrieval]
    RR --> GR[graph_retrieval]
    RR --> HR[hybrid_retrieval]
    VR --> CE[collect_evidence]
    SR --> CE
    GR --> CE
    HR --> CE
    CE --> CME[check_missing_evidence]
    CME --> |"missing & rounds < MAX"| CR[corrective_retrieval]
    CR --> CE
    CME --> |"complete"| VE[verify_evidence]
    VE --> SA[synthesize_answer]
    SA --> VC[verify_citations]
    VC --> END([Answer + citations_valid])
```

---

## Design Stage 4: Routing Decision Logic

The routing node is where the "rules beat AI" guarantee is enforced.

```mermaid
flowchart TD
    SQ["sub-question text"] --> R1{"Contains\n'which customers'\n'impacted by'\n'which teams'\n'owned by'?"}
    R1 --> |YES| GRAPH["strategy = graph"]
    R1 --> |NO| R2{"Contains\n'incidents'\n'occurred'\n'last quarter'\n'records for'?"}
    R2 --> |YES| SQL["strategy = sql"]
    R2 --> |NO| R3{"Contains\n'policy'\n'postmortem'\n'decisions'\n'prevent recurrence'?"}
    R3 --> |YES + context| HYBRID["strategy = hybrid"]
    R3 --> |YES, no context| VECTOR["strategy = vector"]
    R3 --> |NO| PASS["keep original strategy"]
```

---

## Design Stage 5: Evidence Flow and Citation Model

```mermaid
sequenceDiagram
    participant VR as vector_retrieval
    participant SR as sql_retrieval
    participant GR as graph_retrieval
    participant HR as hybrid_retrieval
    participant CE as collect_evidence
    participant SA as synthesize_answer
    participant VC as verify_citations

    VR ->> CE: Evidence[source_type=document, id=ev-abc]
    SR ->> CE: Evidence[source_type=sql, id=sql-xyz-0]
    GR ->> CE: Evidence[source_type=graph, id=ev-graph-ab]
    HR ->> CE: Evidence[source_type=document, id=ev-def] + Evidence[source_type=graph, id=ev-graph-cd]

    CE ->> CE: deduplicate by id
    CE ->> CE: assign citation_number 1,2,3...
    CE ->> SA: deduped Evidence list

    SA ->> SA: wrap each item with untrusted-data sentinels
    SA ->> SA: prompt LLM with evidence + question
    SA ->> VC: answer = "...customers [1] were impacted [3]..."

    VC ->> VC: extract {1,3} from answer
    VC ->> VC: valid_set = {1,2,3,4,5} (len(evidence))
    VC ->> VC: invalid = {1,3} - {1,2,3,4,5} = {}
    VC -->> END: citations_valid = True
```

---

## Design Stage 6: Corrective Retrieval Loop

```mermaid
flowchart LR
    CE[collect_evidence] --> CME[check_missing_evidence]
    CME --> COND{missing_keys != []\nAND rounds < max?}
    COND --> |YES\nrounds += 1| CR[corrective_retrieval\nbroadened vector search]
    CR --> CE
    COND --> |NO| VE[verify_evidence]
```

**Bounded loop guarantee:** `MAX_CORRECTIVE_ROUNDS=1` (from settings).  
`should_correct()` checks `rounds < settings.max_corrective_rounds` before routing to `corrective_retrieval`.  
No matter what, the loop runs at most `max_corrective_rounds` extra times, then falls through to `verify_evidence`.

---

## Final Architecture After Phase 11

```mermaid
graph TD
    subgraph Backend ["FastAPI Backend"]
        API[api/ layer]
        SVC[services/ layer]
    end

    subgraph Agents ["agents/ layer - NEW in Phase 11"]
        STATE[state.py\nResearchState]
        RULES[rules.py\nDeterministic logic]
        NODES[nodes/\n14 node functions]
        PROMPTS[prompts.py\nLLM templates]
    end

    subgraph RAG ["rag/ layer"]
        RETR[retriever.py\nHybrid vector]
        SQL[sql_retrieval.py\nSQLRetriever]
        GRAPH[graph_store.py\nGraphStoreService]
    end

    subgraph Core ["app/core/"]
        LLM[llm.py\nget_llm]
        GUARD[guardrails.py\nwrap_untrusted]
        CONFIG[config.py\nget_settings]
    end

    API --> SVC
    SVC --> NODES
    NODES --> RULES
    NODES --> RETR
    NODES --> SQL
    NODES --> GRAPH
    NODES --> LLM
    NODES --> GUARD
    NODES --> CONFIG
```

**Layer rules strictly observed:**
- `agents/` imports from `rag/` and `app/core/` — not from `app/api/` or `app/services/`
- `app/core/` never imports `agents/` (would create a cycle)
- Each node is independently testable with fake stores
