# Phase 14 — Project System Design Evolution

## Overview

Phase 14 completes the NovaEnterprise frontend, wiring the AI research engine and knowledge graph directly into the browser. The backend is unchanged; all evolution is in the Next.js client layer.

---

## Stage 1: Before Phase 14 — Console shell with placeholders

After Phase 13 the frontend had:
- Working browse pages (customers, incidents, decisions, documents list)
- A partially functional search page
- A research session page with basic sub-question and evidence rendering
- **Placeholder** knowledge-graph and documents pages

```mermaid
graph LR
    Browser["Browser :3001"]
    Nav["Navigation bar"]
    Login["Login page"]
    Browse["Browse pages\ncustomers/incidents/decisions"]
    Search["Search page\n(partial)"]
    Research["Research session\n(partial)"]
    KG["Knowledge Graph\n⚠ placeholder"]
    Docs["Documents\n⚠ list only"]
    API["FastAPI :8001\n/api/v1/*"]

    Browser --> Nav
    Nav --> Browse
    Nav --> Search
    Nav --> KG
    Nav --> Docs
    Search --> Research
    Browse --> API
    Research --> API
```

---

## Stage 2: Completing the Research Session Page

The first gap to fill was the research session page. It needed to show everything the API returns.

### What was added

| Section | Before | After |
|---------|--------|-------|
| Sub-questions | Showed ID, strategy, status, text | Unchanged (already correct) |
| Queries executed | Missing | SQL in green boxes + Cypher in purple boxes, derived from evidence |
| Answer | Showed text | Now shows verification ratio and citation count |
| Evidence | Showed source type + content | Same; now SQL/graph locators also shown in queries panel |
| Memory scopes | Missing | Organisational / Conversation / Session / Analyst scopes shown |
| Event timeline | Showed node name + event type | Now shows formatted timing per step |

```mermaid
graph TD
    subgraph "Research Session Page — final state"
        Header["Question + status + strategies"]
        SubQ["Sub-questions\nID · strategy · status"]
        Queries["Queries executed\nSQL (green) · Cypher (purple)"]
        Answer["Answer\ncitations verified · verification ratio"]
        Evidence["Evidence\n[n] · source_type · score · content"]
        Memory["Memory scopes\n4 panels: organizational / conversation / session / analyst"]
        Timeline["Event timeline\nms · node label · event type"]
    end

    Header --> SubQ --> Queries --> Answer --> Evidence --> Memory --> Timeline
```

**Key design insight**: the SQL queries and Cypher statements are derived from the `evidence` list already returned by the API — `evidence.locator` holds the query text, and `evidence.source_type` discriminates SQL from graph. No new API endpoint is needed.

---

## Stage 3: Knowledge Graph Explorer

This was the most complex new page. It needed to work without a visual canvas library (no D3 or Cytoscape added) while still being interactive.

### Design: text-based node browser

```mermaid
graph LR
    subgraph "Knowledge Graph Page"
        Stats["Stats bar\nnodes · edges"]
        Filter["Label filter\nService / Incident / Customer…"]
        NodeList["Node list\n(scrollable, clickable)"]
        NeighborPanel["Neighbour panel\nproperties + connected nodes"]
        Cypher["Cypher console\n(analyst+ only)"]
    end

    Filter -->|GET /graph/nodes?label=| NodeList
    NodeList -->|click| NeighborPanel
    NeighborPanel -->|GET /graph/nodes/{id}/neighbors| NeighborPanel
    NeighborPanel -->|click neighbour| NeighborPanel
    Cypher -->|POST /graph/cypher| Cypher
```

### Interaction flow

```mermaid
sequenceDiagram
    participant U as User
    participant Page as KnowledgeGraphPage
    participant API as FastAPI /graph

    U->>Page: Select "Service" from filter
    Page->>API: GET /graph/nodes?label=Service
    API-->>Page: [ServiceNodes]
    U->>Page: Click "Payments API" node
    Page->>API: GET /graph/nodes/payments-api/neighbors?direction=both
    API-->>Page: {node, neighbors, edges}
    Page-->>U: Show properties + connected nodes with relationships
    U->>Page: Click a neighbour (e.g. INC-2031)
    Page->>API: GET /graph/nodes/inc-2031/neighbors?direction=both
    API-->>Page: {node, neighbors, edges}
    Page-->>U: Updated neighbour panel
```

### Role enforcement on Cypher console

```mermaid
graph TD
    Role{Role?}
    Show["Show Cypher console\ntextarea + Run button"]
    Hide["Show notice:\n'Sign in as analyst or admin to run Cypher'"]
    Role -->|analyst or admin| Show
    Role -->|viewer or null| Hide
```

---

## Stage 4: Documents Page with Upload and Delete

```mermaid
graph TD
    subgraph "Documents Page"
        List["Document list\nfilename · chunks · size · status"]
        Upload["Upload form\nfile picker + Upload button\n(analyst+ only)"]
        DeleteBtn["Request delete button\n(analyst+ only, per row)"]
        PendingMsg["Awaiting admin approval\n(after request submitted)"]
    end

    Upload -->|POST /documents/upload| List
    DeleteBtn -->|confirm dialog| DeleteBtn
    DeleteBtn -->|DELETE /documents/{id}| PendingMsg
```

**Approval flow**:

```mermaid
sequenceDiagram
    participant A as Analyst
    participant UI as Documents Page
    participant BE as FastAPI
    participant Admin as Admin

    A->>UI: Clicks "Request delete"
    UI->>UI: window.confirm dialog
    A->>UI: Confirms
    UI->>BE: DELETE /api/v1/documents/{id}
    BE-->>UI: 202 ApprovalRequest
    UI-->>A: Row shows "Awaiting admin approval"
    Note over A,Admin: Document NOT yet deleted
    Admin->>BE: POST /api/v1/approvals/{id}/approve
    BE-->>Admin: Document marked deleted
```

---

## Stage 5: Types and API client extensions

The typed API client was extended to cover the new endpoints.

```mermaid
classDiagram
    class GraphNode {
        +node_id: string
        +label: string
        +properties: Record
    }
    class GraphEdge {
        +source_id: string
        +target_id: string
        +relationship: string
    }
    class GraphNeighbors {
        +node: GraphNode
        +neighbors: GraphNode[]
        +edges: GraphEdge[]
    }
    class CypherResult {
        +rows: Record[]
        +row_count: number
        +cypher: string
    }
    class GraphStats {
        +node_count: number
        +edge_count: number
    }
    class DocumentUploadResponse {
        +doc_id: string
        +chunk_count: number
        +flagged: boolean
    }
    class ApprovalRequest {
        +id: string
        +resource_id: string
        +status: string
    }

    GraphNeighbors --> GraphNode
    GraphNeighbors --> GraphEdge
```

---

## Final Architecture: Phase 14

```mermaid
graph TB
    subgraph "Frontend :3001"
        Login
        NavBar["Navigation (role-aware)"]
        Search["Search page\n/search"]
        Research["Research session\n/research/[id] — 2s poll"]
        KG["Knowledge Graph\n/knowledge-graph"]
        Documents["Documents\n/documents"]
        Browse["Browse pages\n/customers /incidents /decisions"]
        Client["Typed API client\nlib/api-client.ts"]
        Auth["Auth helpers\nlib/auth.ts"]
        Types["Shared types\nlib/types.ts"]
    end

    subgraph "Backend :8001 (unchanged)"
        ResearchAPI["/api/v1/research"]
        GraphAPI["/api/v1/graph"]
        DocsAPI["/api/v1/documents"]
        BrowseAPI["/api/v1/customers\n/incidents /decisions"]
        HealthAPI["/health/ready"]
    end

    Browser --> Login --> NavBar
    NavBar --> Search & KG & Documents & Browse
    Search -->|start → redirect| Research
    Research -->|polls| Client
    KG -->|browse, expand, Cypher| Client
    Documents -->|list, upload, delete| Client
    Browse --> Client
    Client --> Auth
    Client --> Types
    Client -->|JWT + X-Request-ID| ResearchAPI & GraphAPI & DocsAPI & BrowseAPI
    HealthAPI --> NavBar
```

---

## Summary of design decisions in Phase 14

| Decision | Alternative considered | Why chosen |
|----------|----------------------|------------|
| SQL/Cypher extracted from evidence.locator | Separate API endpoint for query log | Avoids a new backend endpoint; locator already carries query text |
| Text-based graph explorer | D3 / vis.js canvas | Zero extra dependencies; works in any browser; accessible |
| Tailwind static class names (no dynamic strings) | Template-literal class strings | Dynamic strings are purged by Tailwind's content scanner |
| `window.confirm` for delete | Custom modal component | Simple; appropriate for a low-frequency admin action |
| `sessionStorage` for JWT | `localStorage` | Clears automatically on tab close; reduces window of token theft |
| Polling every 2 s | WebSocket | Simpler; backend already emits events via REST polling endpoint |
