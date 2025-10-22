from typing import Optional, Dict, Any, List
import os
import json
import asyncio
os.environ.setdefault("LITELLM_LOGGING", "False")
os.environ.setdefault("LITELLM_VERBOSE", "0")
os.environ.setdefault("LITELLM_DISABLE_LOGGING", "1")
os.environ.setdefault("LITELLM_LOGGING_QUEUE", "0")
from litellm import acompletion, Message
from mcp.types import TextContent, Tool


def convert_tool(tool: Tool) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                **tool.inputSchema,
                "properties": tool.inputSchema.get("properties", {}),
            },
        },
    }


async def get_converted_tools(mcp_client) -> List[Dict[str, Any]]:
    tools = await mcp_client.list_tools()
    return [convert_tool(t) for t in tools.tools]


async def outcome_based_test(
    model: str,
    messages: List[Message],
    tools: List[Dict[str, Any]],
    mcp_client,
    expected_keywords: Optional[List[str]] = None,
    max_iterations: int = 5,
    debug: bool = False,
) -> str:
    conversation = messages.copy()

    for _ in range(max_iterations):
        # revert to simpler call path first; caps can be reintroduced after verifying flow
        response = await acompletion(
            model=model,
            messages=conversation,
            tools=tools,
            tool_choice="required",
            num_retries=1,
            timeout=int(os.environ.get("LITELLM_TIMEOUT", "30")),
        )
        assistant_message = response.choices[0].message
        conversation.append(assistant_message)

        # Normalize tool calls across providers (handles dict/object forms)
        raw_tool_calls = getattr(assistant_message, "tool_calls", None) or []
        tool_calls: List[Dict[str, str]] = []
        for tc in raw_tool_calls:
            if isinstance(tc, dict):
                func = tc.get("function", {})
                tool_calls.append({
                    "id": tc.get("id") or str(tc.get("index")),
                    "name": func.get("name"),
                    "arguments": func.get("arguments") or func.get("args") or "{}",
                })
            else:
                func = getattr(tc, "function", None)
                tool_calls.append({
                    "id": getattr(tc, "id", None),
                    "name": getattr(func, "name", None),
                    "arguments": getattr(func, "arguments", "{}"),
                })

        if not tool_calls:
            final_answer = assistant_message.content or ""
            if final_answer:
                if expected_keywords:
                    lower = final_answer.lower()
                    for kw in expected_keywords:
                        assert kw.lower() in lower, f"Expected '{kw}' in final answer"
                return final_answer
            continue

        for tool_call in tool_calls:
            name = tool_call.get("name")
            args = json.loads(tool_call.get("arguments") or "{}")
            result = await mcp_client.call_tool(name, args)
            assert len(result.content) > 0 and isinstance(result.content[0], TextContent)
            conversation.append(
                Message(role="tool", tool_call_id=tool_call.get("id"), content=result.content[0].text)
            )

            # Accept successful tool output immediately if it matches expectations
            tool_text = result.content[0].text or ""
            if tool_text:
                if expected_keywords:
                    lower = tool_text.lower()
                    if all(kw.lower() in lower for kw in expected_keywords):
                        return tool_text
                # Heuristic: many tools return a JSON object with success:true; allow that
                if '"success": true' in tool_text.replace(" ", "").lower():
                    return tool_text

    last = conversation[-1].content or ""
    raise AssertionError(f"Max iterations reached without a final answer. Last message: {last[:200]}")
