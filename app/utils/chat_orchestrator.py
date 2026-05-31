"""Chat orchestrator: MiMo streaming + MCP tool execution (local or remote)."""
import json
import inspect
import logging
from datetime import datetime, UTC
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from app.mcp.context import _current_db_var, _current_user_var
from app.mcp.server import mcp as mcp_server
from app.models.auth import User
from app.utils.mimo_client import MiMoClient
from sqlalchemy.orm import Session


MAX_TOOL_LOOPS = 10

SYSTEM_PROMPT = """You are YuChat, a helpful AI assistant with access to the user's data through various tools.
You can help with:
- Financial data: accounts, transactions, categories, summaries, trends
- Blog posts: list, search, create, update
- User management (superuser only)
- And more!

Be concise and helpful. When using tools, explain what you found in natural language.
If a tool call fails, explain the error and suggest alternatives.

When any tool parameter expects a datetime/timestamp, always include time (ISO 8601 format, e.g. 2026-05-28T14:30:00+00:00). If the user only provides a date, ask what time. If the user says "now", use current time. Default timezone is UTC unless specified otherwise.

## Charts and Visualizations

When the user asks for a chart, graph, or visualization, output a fenced code block with language "chart" containing JSON. Supported types: bar, line, pie, area.

CRITICAL: Always use "label" for the category/string field and "value" for the numeric field. Do NOT use other field names.

Schema:
```chart
{
  "type": "bar"|"line"|"pie"|"area",
  "title": "Chart Title",
  "data": [
    {"label": "Category A", "value": 100},
    {"label": "Category B", "value": 200}
  ],
  "xLabels": ["Custom A", "Custom B"]
}
```

Rules:
- Always include "type", "title", and "data" fields
- Every data item MUST have "label" (string) and "value" (number) fields
- Use descriptive labels
- For multi-series charts, add extra numeric keys (e.g. {"label": "Jan", "income": 100, "expense": 200})
- Use "xLabels" array to override x-axis display text when the raw "label" values are not suitable for display (e.g. numeric IDs, codes, or when you want shorter/cleaner text)
- When showing financial data from tools, format the chart with the retrieved data"""


def _get_system_prompt() -> str:
    """Return system prompt with current date injected."""
    today = datetime.now(UTC).strftime("%A, %Y-%m-%d")
    return f"Current date: {today}\n\n{SYSTEM_PROMPT}"


def _build_local_tool_definitions() -> list[dict]:
    """Convert local MCP tool registrations to Anthropic tool format."""
    tools = []
    # NOTE: _tool_manager._tools is internal to FastMCP; pin mcp version if this breaks
    for tool_name, tool_obj in mcp_server._tool_manager._tools.items():
        func = tool_obj.fn
        hints = func.__annotations__.copy()
        hints.pop("return", None)

        sig = inspect.signature(func)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            prop = {}
            annotation = hints.get(param_name)
            if annotation == str:
                prop["type"] = "string"
            elif annotation == int:
                prop["type"] = "integer"
            elif annotation == float:
                prop["type"] = "number"
            elif annotation == bool:
                prop["type"] = "boolean"
            elif annotation == list[str]:
                prop["type"] = "array"
                prop["items"] = {"type": "string"}
            elif annotation == dict:
                prop["type"] = "object"
            else:
                prop["type"] = "string"

            if param.default is inspect.Parameter.empty:
                required.append(param_name)
            properties[param_name] = prop

        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required

        tools.append({
            "name": tool_name,
            "description": func.__doc__ or f"Tool: {tool_name}",
            "input_schema": schema,
        })
    return tools


async def _execute_local_tool(name: str, arguments: dict, user: User, db: Session) -> str:
    """Execute a local MCP tool by name with the given user/db context."""
    tool_obj = mcp_server._tool_manager._tools.get(name)
    if not tool_obj:
        return json.dumps({"error": f"Unknown tool: {name}"})

    token_user = _current_user_var.set(user)
    token_db = _current_db_var.set(db)
    try:
        result = await tool_obj.fn(**arguments)
        return json.dumps(result, default=str)
    except Exception as e:
        logger.exception(f"Tool execution failed: {name}")
        return json.dumps({"error": str(e)})
    finally:
        _current_user_var.reset(token_user)
        _current_db_var.reset(token_db)


async def run_chat(
    messages: list[dict],
    mimo: MiMoClient,
    user: User,
    db: Session,
    conn_map: dict | None = None,
    remote_tools: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """Run the chat orchestrator. Yields SSE-style events.

    If conn_map is provided (tool_name -> _PooledConnection mapping),
    uses remote MCP servers for tools with auto-reconnect. Otherwise
    falls back to local in-process MCP tools.

    Events:
        {"type": "text", "content": "..."}
        {"type": "tool_start", "id": "...", "name": "...", "arguments": {...}}
        {"type": "tool_end", "id": "...", "name": "...", "result": {...}}
        {"type": "error", "detail": "..."}
        {"type": "done"}
    """
    use_remote = conn_map is not None

    if use_remote:
        tools = remote_tools or []
    else:
        tools = _build_local_tool_definitions()

    conversation_messages = list(messages)

    for _ in range(MAX_TOOL_LOOPS):
        full_text = ""
        tool_uses = []

        try:
            async with mimo.client.messages.stream(
                model=mimo.model,
                messages=conversation_messages,
                max_tokens=4096,
                tools=tools,
                system=_get_system_prompt(),
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            tool_uses.append({
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input_json": "",
                            })
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            full_text += event.delta.text
                            yield {"type": "text", "content": event.delta.text}
                        elif event.delta.type == "input_json_delta":
                            if tool_uses:
                                tool_uses[-1]["input_json"] += event.delta.partial_json
                    elif event.type == "content_block_stop":
                        pass
        except Exception as e:
            yield {"type": "error", "detail": str(e)}
            return

        # Parse tool inputs
        for tu in tool_uses:
            try:
                tu["input"] = json.loads(tu["input_json"]) if tu["input_json"] else {}
            except json.JSONDecodeError:
                tu["input"] = {}
            del tu["input_json"]

        # No tool calls — we're done
        if not tool_uses:
            yield {"type": "done"}
            return

        # Build assistant message with text + tool_use blocks
        assistant_content = []
        if full_text:
            assistant_content.append({"type": "text", "text": full_text})
        for tu in tool_uses:
            assistant_content.append({
                "type": "tool_use",
                "id": tu["id"],
                "name": tu["name"],
                "input": tu["input"],
            })
        conversation_messages.append({"role": "assistant", "content": assistant_content})

        # Execute tools and build tool_result messages
        tool_results = []
        for tu in tool_uses:
            yield {"type": "tool_start", "id": tu["id"], "name": tu["name"], "arguments": tu["input"]}

            if use_remote:
                conn = conn_map.get(tu["name"])
                if conn:
                    result_str = await conn.call_tool_with_retry(tu["name"], tu["input"])
                else:
                    result_str = json.dumps({"error": f"No session for tool: {tu['name']}"})
            else:
                result_str = await _execute_local_tool(tu["name"], tu["input"], user, db)

            try:
                result_data = json.loads(result_str)
            except json.JSONDecodeError:
                result_data = {"raw": result_str}
            yield {"type": "tool_end", "id": tu["id"], "name": tu["name"], "result": result_data}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu["id"],
                "content": result_str,
            })

        conversation_messages.append({"role": "user", "content": tool_results})

    # Max loops reached
    yield {"type": "error", "detail": f"Max tool call loops ({MAX_TOOL_LOOPS}) reached"}
    yield {"type": "done"}
