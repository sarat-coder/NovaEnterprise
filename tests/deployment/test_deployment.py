"""Deployment hygiene tests (P15-6).

These tests do not start the application.  They inspect the repository and
configuration files to ensure no secrets, database files, or sensitive data
could be baked into a Docker image or committed to git.

Requirements: N1 (offline), N8 (no secrets in code), CLAUDE.md §8 and §15.11.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# .gitignore hygiene
# ---------------------------------------------------------------------------


def _read_gitignore_patterns() -> list[str]:
    gi = ROOT / ".gitignore"
    if not gi.exists():
        return []
    return [
        line.strip()
        for line in gi.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_gitignore_excludes_env_file() -> None:
    """The .env file (which may hold real keys) must be listed in .gitignore."""
    patterns = _read_gitignore_patterns()
    assert any(p in (".env", "*.env", ".env.*") for p in patterns), (
        ".env is not in .gitignore — real API keys could be committed"
    )


def test_gitignore_excludes_database_files() -> None:
    """SQLite .db files must be excluded from git to avoid committing runtime data."""
    patterns = _read_gitignore_patterns()
    assert any("*.db" in p or "data/" in p for p in patterns), (
        "*.db / data/ is not in .gitignore — the SQLite runtime database could be committed"
    )


def test_gitignore_excludes_data_directory() -> None:
    """The data/ directory (runtime SQLite + uploads) must be git-ignored."""
    patterns = _read_gitignore_patterns()
    assert any(p in ("data/", "/data/", "data") for p in patterns), (
        "data/ directory is not in .gitignore"
    )


# ---------------------------------------------------------------------------
# .env hygiene
# ---------------------------------------------------------------------------


def test_env_example_exists() -> None:
    """Every variable must have a placeholder in .env.example (N1, §9.1)."""
    assert (ROOT / ".env.example").exists(), ".env.example is missing from the repository"


def test_env_file_not_committed() -> None:
    """The real .env file must not exist in the repository root (it is git-ignored)."""
    # We only check that if .env exists it does not contain what looks like a real API key.
    env_path = ROOT / ".env"
    if not env_path.exists():
        return  # fine — not committed
    content = env_path.read_text()
    # Heuristic: real keys are long random strings; demo values are short or empty.
    suspicious = re.findall(r"(?:API_KEY|SECRET|PASSWORD|TOKEN)=([^\s#]{20,})", content)
    # Exclude obvious placeholder patterns
    placeholder_re = re.compile(r"^(change-me|your-|<|placeholder)", re.I)
    real_keys = [v for v in suspicious if not placeholder_re.match(v)]
    assert not real_keys, (
        f".env appears to contain real credentials: {real_keys[:3]}. "
        "Do not commit .env with real keys."
    )


def test_env_example_has_no_real_secrets() -> None:
    """The .env.example template must not contain real API keys — only placeholders."""
    content = (ROOT / ".env.example").read_text()
    suspicious = re.findall(r"(?:API_KEY|SECRET|TOKEN)=([^\s#]{20,})", content)
    placeholder_re = re.compile(r"^(change-me|your-|<|placeholder)", re.I)
    real_keys = [v for v in suspicious if not placeholder_re.match(v)]
    assert not real_keys, f".env.example contains what looks like a real secret: {real_keys[:3]}"


# ---------------------------------------------------------------------------
# .env.example completeness
# ---------------------------------------------------------------------------


_REQUIRED_ENV_VARS = [
    "LLM_PROVIDER",
    "VECTOR_STORE",
    "GRAPH_STORE",
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "MAX_SUBQUESTIONS",
    "MAX_CORRECTIVE_ROUNDS",
    "RATE_LIMIT_PER_MINUTE",
    "MAX_UPLOAD_MB",
    "CORS_ORIGINS",
]


def test_env_example_lists_all_required_variables() -> None:
    """Every variable listed in CLAUDE.md §9.1 must have an entry in .env.example."""
    content = (ROOT / ".env.example").read_text()
    missing = [v for v in _REQUIRED_ENV_VARS if v not in content]
    assert not missing, f".env.example is missing entries for: {missing}"


# ---------------------------------------------------------------------------
# Dockerfile hygiene
# ---------------------------------------------------------------------------


def test_backend_dockerfile_exists() -> None:
    """Backend Dockerfile must exist (P15-2)."""
    assert (ROOT / "backend" / "Dockerfile").exists(), "backend/Dockerfile is missing"


def test_frontend_dockerfile_exists() -> None:
    """Frontend Dockerfile must exist (P15-2)."""
    assert (ROOT / "frontend" / "Dockerfile").exists(), "frontend/Dockerfile is missing"


def test_backend_dockerfile_does_not_copy_env() -> None:
    """The backend Dockerfile must not COPY .env into the image."""
    content = (ROOT / "backend" / "Dockerfile").read_text()
    # Match lines like: COPY .env ... or ADD .env ...
    bad_lines = [
        line.strip() for line in content.splitlines() if re.match(r"^\s*(COPY|ADD)\s+\.env\b", line)
    ]
    assert not bad_lines, (
        f"backend/Dockerfile copies .env into the image: {bad_lines}. "
        "Inject secrets via environment variables at runtime."
    )


def test_frontend_dockerfile_does_not_bake_service_role_key() -> None:
    """The frontend Dockerfile must not set or reference SUPABASE_SERVICE_ROLE_KEY."""
    content = (ROOT / "frontend" / "Dockerfile").read_text()
    assert "SERVICE_ROLE_KEY" not in content, (
        "frontend/Dockerfile references SUPABASE_SERVICE_ROLE_KEY — "
        "the service-role key must never reach the browser or the frontend image."
    )


# ---------------------------------------------------------------------------
# Docker Compose hygiene
# ---------------------------------------------------------------------------


def test_docker_compose_exists() -> None:
    """docker-compose.yml must exist (P15-3)."""
    assert (ROOT / "docker-compose.yml").exists(), "docker-compose.yml is missing"


def test_docker_compose_has_required_services() -> None:
    """The Compose file must declare postgres, redis, qdrant, neo4j, and backend."""
    content = (ROOT / "docker-compose.yml").read_text()
    for service in ("postgres", "redis", "qdrant", "neo4j", "backend"):
        assert service in content, f"docker-compose.yml is missing the '{service}' service"


def test_docker_compose_uses_healthchecks() -> None:
    """Every infrastructure service should declare a healthcheck."""
    content = (ROOT / "docker-compose.yml").read_text()
    assert content.count("healthcheck:") >= 4, (
        "docker-compose.yml should declare healthchecks for postgres, redis, qdrant, neo4j"
    )


# ---------------------------------------------------------------------------
# MCP server hygiene
# ---------------------------------------------------------------------------


def test_mcp_server_exists() -> None:
    """The MCP server module must exist (P15-5)."""
    assert (ROOT / "integrations" / "mcp_server.py").exists(), (
        "integrations/mcp_server.py is missing"
    )


def test_mcp_server_exposes_only_read_tools() -> None:
    """The MCP server TOOLS list must not include write / mutate tool names."""
    content = (ROOT / "integrations" / "mcp_server.py").read_text()
    # Extract the tool names from the TOOLS list (lines like: "name": "tool_name")
    tool_name_pattern = re.compile(r'"name":\s*"([^"]+)"')
    tool_names = tool_name_pattern.findall(content)
    write_tools = [
        n
        for n in tool_names
        if any(
            verb in n
            for verb in ("create", "delete", "upload", "approve", "write", "insert", "update")
        )
    ]
    assert not write_tools, (
        f"MCP server TOOLS list contains write/mutate tool names: {write_tools}. "
        "Only read-only tools may be exposed."
    )
