import pytest
from litellm import Message
from mcp import ClientSession

from ..e2e.utils import get_converted_tools, outcome_based_test
from ..e2e.conftest import models  # reuse model matrix and stdio client


pytestmark = pytest.mark.anyio


DIRECTIVE_SYSTEM_PROMPT = (
    "You are a helpful database assistant. "
    "When asked, call tools immediately, make reasonable assumptions, and always summarize after tool calls."
)


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_db_connect(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(role="user", content="Connect to the DevLake database and summarize connection details."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["host", "database"]
    )
    assert len(answer) > 20


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_list_databases(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(role="user", content="List the databases available on the server."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["lake"]
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_list_tables(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(role="user", content="Show tables in the 'lake' database."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["cicd"]
    )
    assert any(t in answer.lower() for t in ["incidents", "deployments", "cicd"])  # flexible


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_get_table_schema(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(role="user", content="Describe the columns of table 'incidents' in database 'lake'."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["incidents", "status"]
    )
    assert len(answer) > 10

