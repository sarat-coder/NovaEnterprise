# Phase 15 — Interview Questions and Answers

## Evaluation and Quality

**Q: Why do you have an evaluation suite with hard thresholds instead of just running unit tests?**

A: Unit tests verify that code behaves correctly when given specific inputs. They can't tell you whether the AI's answers are actually useful. The evaluation suite addresses a different question: "Given real research questions, does the system retrieve the right evidence and produce a cited answer?" We use five representative questions with known ground truth — we know which documents and SQL tables should appear in the answer. The thresholds are set below the observed scores on purpose: they catch regressions (the score drops) without failing on noise (the score varies slightly between runs). If SQL correctness drops from 1.0 to 0.8, the build fails and we investigate. If it's 0.99 due to a minor difference, it still passes.

---

**Q: Why set the retrieval relevance threshold at 0.80 instead of 1.00?**

A: Because not every eval case requires all document types. A simple question about data retention policy should score 1.0 on retrieval relevance — the right document is in the top results. But the canonical multi-part question involves four different stores; it's acceptable if one obscure supporting document isn't retrieved so long as the primary evidence is found. Setting the threshold at 0.80 allows the eval suite to cover a range of question types without requiring perfect recall on every case. 1.00 thresholds are reserved for correctness properties (SQL, citations) where any failure is a bug.

---

**Q: Why does the evaluation suite run with the fake LLM? Doesn't that mean the scores aren't realistic?**

A: The fake LLM is deterministic — it always produces the same output for the same input. This means the eval scores are reproducible across CI runs, which is what matters for a regression gate. What the eval is really testing is the retrieval layer, not the generation layer: did we find the right evidence? Did we route to the right retrieval strategy? Did we cite sources? None of these depend on the LLM generating high-quality prose. The generation quality is a concern for real deployments (where you'd use a real LLM), but it's out of scope for a regression gate that runs in 30 seconds with no API key.

---

## Docker and Containerisation

**Q: Why use a multi-stage Dockerfile instead of a single stage?**

A: Single-stage Dockerfiles tend to include everything used during the build — compilers, test frameworks, build tools — which makes the final image large and potentially insecure (more attack surface). Multi-stage builds solve this by separating the "how to build" from the "what to run". In our backend Dockerfile: stage 1 uses `uv` to install all Python dependencies into a virtualenv; stage 2 copies only that virtualenv into a fresh minimal image. The build tools never reach the runtime image. The result is a smaller, cleaner image that's easier to scan for vulnerabilities.

---

**Q: Why is there a non-root user in the container?**

A: Running as root inside a container is a security risk. If a vulnerability in the application allows an attacker to execute arbitrary commands, they would have root access inside the container — which could be used to break out of the container, write to mounted volumes, or escalate to the host. The `nova` user has no sudo privileges, owns only the `data/` directory it needs to write to, and can't do anything outside its working directory. This is called the **principle of least privilege** — give each process exactly what it needs and nothing more.

---

**Q: Why does the frontend Dockerfile use `npm run build` with the standalone output? What is standalone mode?**

A: Next.js's standalone output mode generates a minimal Node.js server that includes only the files needed to run the app in production — no `node_modules`, no development-only assets. The result is a directory containing a single `server.js` file and a minimal set of dependencies, often 90%+ smaller than the full `node_modules`. The Docker runner stage copies only this `standalone/` directory, so the final frontend image is very small. Without standalone mode, you'd have to copy all 400 MB of `node_modules` into the image.

---

**Q: What happens to the data if someone runs `docker compose down`?**

A: Named volumes in Docker Compose persist independently of the containers that use them. `docker compose down` stops and removes the containers but leaves the volumes (`postgres_data`, `redis_data`, `qdrant_data`, `neo4j_data`) intact. When you run `docker compose up` again, the containers start and re-mount the same volumes — your data is still there. To delete both containers and volumes (a full reset), you run `docker compose down -v`. This distinction matters in production: a routine container update (which removes and recreates containers) should not destroy the database.

---

## CI Pipeline

**Q: Why does the CI have four separate jobs instead of one big job that does everything?**

A: Separate jobs let GitHub Actions run them in parallel, so the total CI time is the duration of the slowest job, not the sum of all jobs. More importantly, separate jobs give clearer failure feedback. If the eval gate fails, the developer knows immediately that retrieval quality regressed — they don't have to scroll through a 500-line log to find where it failed. Each job also has a clear owner: the eval gate owns answer quality, the hygiene job owns deployment safety, the frontend job owns UI correctness.

---

**Q: The eval-gate job depends on lint-and-test. Why not run them in parallel?**

A: The eval-gate runs the research workflow end-to-end, which requires the application code to be importable. If the code doesn't lint or the basic tests fail, the eval run would fail with a confusing import error rather than the real problem. Requiring lint-and-test to pass first means the eval-gate only runs when the code is at least syntactically and logically valid. It also avoids burning eval compute time on code that has basic bugs.

---

## MCP Server

**Q: What is MCP and why expose the platform through it?**

A: MCP (Model Context Protocol) is an open standard for connecting AI models to external tools and data sources. Think of it like a universal adapter: any AI assistant that implements the MCP client side — Claude, GPT-based tools, custom agents — can talk to any MCP server without a custom integration. By exposing NovaEnterprise as an MCP server, we allow external AI agents to query the company's knowledge base, graph, and structured data as first-class tools in their workflows. This is particularly useful for enterprise setups where multiple AI tools need to access the same data.

---

**Q: Why does the MCP server only expose six tools? What about starting a research session?**

A: The MCP server is intentionally a **query interface**, not a research orchestration interface. The six tools map to direct data lookups: search documents, traverse the graph, run SQL, list incidents/customers, retrieve a session. Starting a research session is a long-running background operation (7+ seconds) with a polling model that doesn't fit the synchronous request-response model that MCP tools use. An external agent that needs research output should: (1) start a session via the REST API, (2) poll for completion, (3) retrieve the session via the MCP `get_research_session` tool. The MCP server handles step 3 only — the orchestration stays with the agent.

---

**Q: Why stdio instead of HTTP for the MCP transport?**

A: The stdio transport is the simplest possible option: the MCP server reads JSON-RPC messages from stdin and writes responses to stdout. This means it can be started as a subprocess by any MCP client without any network configuration — no port to open, no CORS to configure, no TLS to set up. It also means the MCP server and its data access are fully isolated to that subprocess's lifetime. HTTP/SSE transport would be needed for a production deployment where the MCP server is shared across many clients, but for the demo use case (one agent connecting to one platform), stdio is both simpler and more secure.

---

## Deployment Hygiene

**Q: Why write automated tests to check that .env isn't committed? Can't you just be careful?**

A: "Just be careful" is not a scalable security policy. Accidental credential commits happen constantly — it's one of the most common security incidents in software development. GitHub has had to retroactively revoke thousands of leaked keys found in public repositories. Automated tests give you a safety net: even if a developer forgets, the CI check catches it before the PR is merged. The tests are also self-documenting — they tell future contributors exactly what the rules are ("no .env in git, no SERVICE_ROLE_KEY in the frontend Dockerfile") without requiring them to read a long security guide.

---

**Q: What is the difference between `.gitignore` and `.dockerignore`?**

A: Both files list patterns for files to exclude, but they serve different tools. `.gitignore` tells `git` which files should never be committed to the repository — secrets, build artefacts, database files, local config. `.dockerignore` tells Docker's build context which files should not be sent to the Docker daemon when building an image — this affects both the image size and security. It's possible to have a file that is not in git (because it's git-ignored) but would still be copied into a Docker image if it's not in `.dockerignore`. That's why both files are needed: `.gitignore` protects the repository; `.dockerignore` protects the images.

---

**Q: What would happen if the SUPABASE_SERVICE_ROLE_KEY was baked into the frontend Docker image?**

A: The service-role key bypasses Postgres's Row Level Security (RLS) policies entirely — it's the equivalent of a database superuser credential. If it reached the frontend Docker image, any user who could pull and inspect the image (a Docker registry breach, a misconfigured public image, a disgruntled employee) would have unrestricted access to all the data in the database, bypassing all the RBAC and RLS rules we built. The frontend should never hold the service-role key: it needs only the public anon key (which is scoped by RLS). This is why the deployment hygiene test specifically checks that `SERVICE_ROLE_KEY` does not appear in the frontend Dockerfile.

---

## Big Picture

**Q: If you had to pick the single most important thing Phase 15 adds, what would it be?**

A: The evaluation suite. Everything else — Docker, Compose, CI jobs, MCP, hygiene tests — are engineering good practices that any professional project would have. But the evaluation suite is specific to this platform: it's the only mechanism that proves the AI is actually giving good answers, not just running without errors. A system where every test passes but the AI answers with hallucinations or missing citations is not a research platform — it's a confabulation machine. The eval gate is what turns "the code runs" into "the system works."
