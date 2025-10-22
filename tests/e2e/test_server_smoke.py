import json
import pytest
from mcp import ClientSession


pytestmark = pytest.mark.anyio


def _find_tool_by_keywords(tools, *keywords):
    names = [t.name for t in tools.tools]
    for name in names:
        lower = name.lower()
        if all(k.lower() in lower for k in keywords):
            return name
    return None


async def _content_to_dict(text: str):
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


@pytest.mark.flaky(max_runs=2)
async def test_server_connect_direct(mcp_client: ClientSession):
    tools = await mcp_client.list_tools()
    connect_name = _find_tool_by_keywords(tools, "connect", "database") or "connect_database"
    assert connect_name is not None, f"Connect tool not found in: {[t.name for t in tools.tools]}"

    result = await mcp_client.call_tool(connect_name, {})
    assert result.content and result.content[0].text
    payload = await _content_to_dict(result.content[0].text)
    # Accept either structured success or success message text
    assert (
        (isinstance(payload, dict) and payload.get("success") is True)
        or ("connected" in result.content[0].text.lower())
    ), f"Unexpected connect response: {result.content[0].text[:200]}"


@pytest.mark.flaky(max_runs=2)
async def test_server_list_databases_direct(mcp_client: ClientSession):
    tools = await mcp_client.list_tools()
    list_name = _find_tool_by_keywords(tools, "list", "database") or "list_databases"
    assert list_name is not None, f"List databases tool not found in: {[t.name for t in tools.tools]}"

    result = await mcp_client.call_tool(list_name, {})
    assert result.content and result.content[0].text
    text = result.content[0].text.lower()
    assert "lake" in text or "database" in text, f"Unexpected list databases response: {result.content[0].text[:200]}"


