import pytest
from litellm import Message
from mcp import ClientSession

from ..e2e.utils import get_converted_tools, outcome_based_test
from ..e2e.conftest import models


pytestmark = pytest.mark.anyio


PROMPT = (
    "You are a DevLake assistant. Use tools immediately, assume reasonable date ranges, and summarize results."
)


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_incidents_recent(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(role="user", content="Show incidents from the last 30 days."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["incident"]
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_incidents_by_component(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(role="user", content="Incidents for component 'build-service' in the last month."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["incident"]
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_incidents_by_status(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(role="user", content="List OPEN incidents from the last 30 days."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["incident", "open"]
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_incidents_by_date_range(model: str, mcp_client: ClientSession):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(role="user", content="Show incidents in January 2024 (use 2024-01-01 to 2024-01-31)."),
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=["incident", "2024"]
    )
    assert len(answer) > 10

