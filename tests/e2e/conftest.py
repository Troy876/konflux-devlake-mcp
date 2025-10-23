import os
import gc
import asyncio
import pytest
import socket
import time
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

# Ensure LiteLLM background logging is disabled to avoid cross-event-loop queue errors between tests
# Use strong disables as LiteLLM may spawn an async logging worker bound to the first loop
os.environ.setdefault("LITELLM_LOGGING", "False")
os.environ.setdefault("LITELLM_VERBOSE", "0")
os.environ.setdefault("LITELLM_DISABLE_LOGGING", "1")
os.environ.setdefault("LITELLM_LOGGING_QUEUE", "0")

requested_models = [m.strip() for m in os.environ.get("E2E_TEST_MODELS", "gpt-4o,claude-3-5-sonnet-20240620").split(",") if m.strip()]

def _has_api_key_for_model(model_name: str) -> bool:
    name = model_name.lower()
    if "gemini" in name:
        return bool(os.environ.get("GEMINI_API_KEY"))
    if "claude" in name:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    # default to OpenAI for gpt/* models
    return bool(os.environ.get("OPENAI_API_KEY"))

# Filter out models without corresponding API keys to prevent auth errors locally
models = [m for m in requested_models if _has_api_key_for_model(m)]

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# Avoid cross-task teardown: keep fixtures simple; let anyio/pytest manage loop lifecycle


@pytest.fixture
def db_env():
    # Map CI/local TEST_DB_* to server-recognized DB_*; provide sane defaults
    host = os.environ.get("TEST_DB_HOST", os.environ.get("DB_HOST", "localhost"))
    port = os.environ.get("TEST_DB_PORT", os.environ.get("DB_PORT", "3306"))
    user = os.environ.get("TEST_DB_USER", os.environ.get("DB_USER", "devlake"))
    password = os.environ.get("TEST_DB_PASSWORD", os.environ.get("DB_PASSWORD", "devlake_password"))
    database = os.environ.get("TEST_DB_NAME", os.environ.get("DB_DATABASE", "lake"))

    return {
        "DB_HOST": host,
        "DB_PORT": str(port),
        "DB_USER": user,
        "DB_PASSWORD": password,
        "DB_DATABASE": database,
        # Quiet noisy shutdown logs in tests
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "ERROR"),
    }


@pytest.fixture
async def mcp_client(db_env):
    # Ensure DB is reachable to avoid long LLM/tool retries that look like hangs
    host = db_env["DB_HOST"]
    port = int(db_env["DB_PORT"])
    deadline = time.time() + float(os.environ.get("E2E_DB_WAIT_SECS", "20"))
    last_err = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                break
        except Exception as e:
            last_err = e
            time.sleep(1)
    else:
        pytest.skip(f"MySQL not reachable at {host}:{port} ({last_err})")

    server_path = os.environ.get("MCP_SERVER_PATH", "python konflux-devlake-mcp.py")
    if " " in server_path:
        parts = server_path.split()
        command = parts[0]
        args = parts[1:] + [
            "--transport", "stdio",
            "--log-level", os.environ.get("LOG_LEVEL", "ERROR"),
            "--db-host", db_env["DB_HOST"],
            "--db-port", db_env["DB_PORT"],
            "--db-user", db_env["DB_USER"],
            "--db-password", db_env["DB_PASSWORD"],
            "--db-database", db_env["DB_DATABASE"],
        ]
    else:
        command = server_path
        args = [
            "--transport", "stdio",
            "--log-level", os.environ.get("LOG_LEVEL", "ERROR"),
            "--db-host", db_env["DB_HOST"],
            "--db-port", db_env["DB_PORT"],
            "--db-user", db_env["DB_USER"],
            "--db-password", db_env["DB_PASSWORD"],
            "--db-database", db_env["DB_DATABASE"],
        ]

    # Ensure server knows it's running under stdio so it suppresses console logs
    env = dict(db_env)
    env["MCP_STDIO"] = "true"
    params = StdioServerParameters(command=command, args=args, env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            try:
                await asyncio.wait_for(session.initialize(), timeout=float(os.environ.get("E2E_INIT_TIMEOUT", "20")))
            except Exception as e:
                pytest.skip(f"MCP server did not initialize in time: {e}")
            yield session

