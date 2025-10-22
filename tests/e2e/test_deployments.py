import pytest
from litellm import Message
from mcp import ClientSession

from ..e2e.utils import get_converted_tools, outcome_based_test
from ..e2e.conftest import models


pytestmark = pytest.mark.anyio


PROMPT = (
    "You are a DevLake assistant. Use tools immediately and summarize results after tool calls."
)


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_deployments_all(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(role="user", content="List all available deployments."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["deployment"]
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_deployments_by_project(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(role="user", content="List deployments for project Konflux_Pilot_Team."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["deployment"]
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_deployments_by_environment(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(role="user", content="List PRODUCTION deployments."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["deployment", "production"]
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_deployments_by_date_range(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(role="user", content="List deployments in January 2024 (use 2024-01-01 to 2024-01-31)."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["deployment"]
    )
    assert len(answer) > 10

