# Phase 1 — Runtime Skeleton: Plain-English Explanation

> **Audience:** Non-technical readers — recruiters, interviewers, managers, stakeholders.
> **Goal:** Explain what was built in Phase 1 so anyone can understand it after a single read.

---

## What is NovaEnterprise?

Imagine a smart research assistant for a large company. An employee types a business question — for example, *"Which customers were affected by the Payments API outage last quarter, and what did we do to fix it?"* — and within seconds receives a **clear, cited answer** pulled from internal documents, databases, and a knowledge map of how the company's systems connect.

NovaEnterprise is that assistant. It is a web application with a chat-like interface on the front and a powerful research engine on the back.

Phase 1 built the **skeleton** of that engine — the bare minimum needed to start the server, prove it is alive, and lay a clean foundation every future feature will build on.

---

## What is a "Runtime Skeleton"?

Think of building a house. Before you hang doors or lay carpet, you pour the foundation and erect the steel frame. That frame is invisible in the finished house, but nothing else holds together without it.

Phase 1 is that frame for NovaEnterprise. It has five pieces:

| # | Piece | What it is in plain words |
|---|-------|--------------------------|
| P1-1 | Settings + Logging | The app's control panel and diary |
| P1-2 | Health routes + Request ID | The app's heartbeat monitor and name tag |
| P1-3 | Test harness | The safety net that catches mistakes early |
| P1-4 | Makefile + Code style | The recipe book and spelling checker |
| P1-5 | CI pipeline | The automatic quality gate |

---

## P1-1 — Settings and Logging

### Settings (the control panel)

The application reads its instructions from a file called `.env` (think of it as a settings sheet). Things like:

- *Which AI provider should I use?* (default: "fake" — works without paying for any API)
- *Where is the database?* (default: a local file, no cloud needed)
- *How fast should I allow users to send questions?*

A special function called `get_settings()` reads this file once and remembers the answer. If a test needs to temporarily change a setting, it clears the memory so the new value takes effect — no server restart needed.

**Why this matters:** Every team member and every test can rely on exactly the same settings object. There is no guessing, no copy-pasting of environment variables scattered across the code.

### Logging (the diary)

Every time the server does something interesting — a request arrives, an error happens, a research job starts — it writes a note. That note is in **JSON format**, which looks like this:

```json
{"ts": "2026-11-21T10:30:00.000Z", "level": "INFO", "msg": "Startup complete", "request_id": "abc-123"}
```

JSON logs can be fed directly into monitoring dashboards (Datadog, Grafana, etc.) without any additional processing. Notice the `request_id` field — it ties every log line back to the specific user request that caused it.

---

## P1-2 — Health Routes and Request ID

### Health routes (the heartbeat monitor)

Three special web addresses (called "routes") let an external system check whether the application is alive:

| Route | Question it answers | Returns |
|-------|--------------------|-|
| `/health` | Is the process running? | `{"status": "ok"}` |
| `/health/live` | Should the container be restarted? | `{"status": "ok"}` |
| `/health/ready` | Is the app ready to serve traffic? | Full check report |

The `/health/ready` route runs a **check registry** — a list of tests (database connection, cache connection, AI provider, etc.) that each report their own status. Right now only an "app" check exists. Later phases add their own checks. If any check fails, the route reports a problem so the platform can route traffic away from that instance.

**Real-world analogy:** Kubernetes (the system that runs containers in production) pings `/health/live` every few seconds. If it stops responding, Kubernetes restarts the container. `/health/ready` tells Kubernetes whether to send users to this instance yet (useful during startup).

### X-Request-ID (the name tag)

Every web request gets a unique ID — like a ticket number at a deli counter. If the client (browser or app) sends its own ID, the server echoes it back. Otherwise the server generates one.

This ID appears in every log line and every response header. When something goes wrong, support engineers can type the ID into their log search tool and instantly find every related event across all servers.

---

## P1-3 — Offline Test Harness

### What is a test harness?

A test harness is a system for running automated checks. You write a check once ("when I call `/health`, I expect to get `200 OK` back"), and the harness re-runs every check in seconds every time code changes.

### "Offline" means no paid services needed

By default, NovaEnterprise uses:
- A **fake AI** that returns pre-set responses (no OpenAI or Anthropic API key needed)
- An **in-memory database** (no PostgreSQL installation needed)
- A **fake Redis** (no Redis server needed)

This means any developer — or the automated CI server — can run all tests with a single command on a laptop, with zero external dependencies and zero cost.

### What was tested in Phase 1?

Eight tests:

1. `GET /health` returns HTTP 200
2. `GET /health/live` returns HTTP 200
3. `GET /health/ready` returns a JSON body with `status` and `checks`
4. The `app` check inside `/health/ready` reports `ok`
5. Every response has an `X-Request-ID` header
6. When the client sends their own ID, it comes back unchanged
7. Two different requests get different IDs
8. Even a 404 (page not found) response includes the ID

---

## P1-4 — Makefile and Code Style

### Makefile (the recipe book)

A `Makefile` is a file of one-line commands for common tasks. Instead of remembering a long setup command, a developer types:

```
make setup    # create virtual environment and install all packages
make backend  # start the server on port 8001
make test     # run all tests
make lint     # check code style
```

This keeps every developer — and the automated CI server — running the same commands, so "it works on my machine" problems disappear.

### Ruff (the spelling checker)

`Ruff` is a code style and quality tool. It automatically:
- Catches unused imports
- Flags inconsistent formatting
- Detects common bugs
- Sorts import statements

When a developer runs `make lint`, they see zero warnings if everything is correct. The CI pipeline enforces this — a pull request with style issues is blocked from merging automatically.

### `.env.example` (the setup guide)

A template file that lists every setting the app understands, with safe placeholder values. New developers copy it to `.env` and fill in their own values. Because `.env.example` is in git (but `.env` is not), sensitive values like API keys never accidentally end up in the codebase.

---

## P1-5 — Continuous Integration (CI)

### What is CI?

Continuous Integration means every time a developer pushes code, an automated system runs all the checks and reports back within minutes. It is the guardrail that prevents one developer's change from accidentally breaking everyone else's work.

### The Phase 1 CI pipeline

When a developer opens a pull request to merge code into the `development` branch, GitHub automatically:

1. Checks out the code on a fresh Linux server
2. Installs Python 3.12 and all packages
3. Runs `ruff check .` — if any style issues exist, the pipeline fails and the PR is blocked
4. Runs `ruff format --check .` — same, for formatting
5. Runs `pytest tests/` — if any tests fail, the PR is blocked

Only when all five steps pass does GitHub show a green checkmark and allow the merge.

---

## How it all fits together

```
Developer writes code
        ↓
make lint  →  ruff checks style  →  ✅ or ❌
        ↓
make test  →  pytest runs 8 tests  →  ✅ or ❌
        ↓
git push  →  GitHub CI runs both automatically  →  PR gets ✅ or ❌
        ↓  (if ✅)
make backend  →  FastAPI starts on :8001
        ↓
curl localhost:8001/health  →  {"status": "ok"} with X-Request-ID header
```

---

## What is NOT in Phase 1 yet?

Phase 1 deliberately excludes everything that is not strictly foundational:

- No database (coming in Phase 2)
- No login or user accounts (coming in Phase 3)
- No AI or search capability (coming in Phases 4–8)
- No web interface (coming in Phase 13)

This is intentional. A clean foundation means every later piece can be added without having to revisit the core. Each phase of this project builds on the one before it.

---

## Summary for the interview board

**What did Phase 1 accomplish?**

We turned an empty repository into a working FastAPI server that:
1. Reads all its configuration from one place (settings)
2. Writes structured JSON logs that production monitoring tools can consume
3. Answers health checks so infrastructure knows it is alive
4. Tags every request with a unique ID for end-to-end traceability
5. Can run all 8 tests in under a second on any laptop, with zero external services
6. Enforces code quality automatically on every pull request

**Why does this matter?**

Every startup is tempted to skip foundations and jump straight to features. This project deliberately does not. A reliable skeleton means that when we add an AI search engine, a graph database, and a multi-step research workflow in later phases, we can be confident the foundation will hold.
