"""Stage 3 / Stage 6 -- the contract a client sees is the contract enforced.

These tests talk to the server the way a host does, over MCP, rather than
calling the Python functions. They check that every tool's advertised
outputSchema is closed and lists exactly the fields @shaped keeps, and that
what comes back over the protocol carries no canary values.
"""

import asyncio
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "after"))

from fastmcp import Client  # noqa: E402

import shaping  # noqa: E402
from after import server as after_server  # noqa: E402
from fixtures.seed import CANARY_MARKERS, CANARY_SELF  # noqa: E402
from session import Session  # noqa: E402

SELF_ORDER = f"HW-C{CANARY_SELF['id'][-4:]}"


def _object_schema(schema: dict) -> dict:
    """The object branch of FastMCP's wrapped `T | None` result schema."""
    if schema.get("x-fastmcp-wrap-result"):
        schema = schema["properties"]["result"]
    for branch in schema.get("anyOf", [schema]):
        if branch.get("type") == "object":
            return branch
    raise AssertionError(f"no object schema in {schema}")


def _schema_fields(obj: dict) -> dict:
    """Mirror of shaping.allowlist(), read back from the published schema."""
    assert obj.get("additionalProperties") is False, \
        "output schema is open: clients are not told the field list is closed"
    out = {}
    for name, prop in obj["properties"].items():
        if prop.get("type") == "object":
            out[name] = _schema_fields(prop)
        elif prop.get("type") == "array" and \
                prop.get("items", {}).get("type") == "object":
            out[name] = _schema_fields(prop["items"])
        else:
            out[name] = 1
    return out


async def _list_tools():
    async with Client(after_server.mcp) as client:
        return await client.list_tools()


def test_every_tool_advertises_a_closed_output_schema():
    tools = asyncio.run(_list_tools())
    assert {t.name for t in tools} == set(after_server.TOOLS)
    for tool in tools:
        assert tool.output_schema, f"{tool.name} advertises no outputSchema"
        _schema_fields(_object_schema(tool.output_schema))


def test_advertised_schema_matches_enforced_allowlist():
    """The fields a client is promised are the fields the middleware keeps."""
    for tool in asyncio.run(_list_tools()):
        advertised = _schema_fields(_object_schema(tool.output_schema))
        enforced = after_server.TOOLS[tool.name].allowlist
        assert advertised == enforced, tool.name


def _args_for(name: str) -> dict:
    if name == "send_reply":
        return {"ticket_ref": "HW-T0000", "body": "test body"}
    if name == "get_open_ticket":
        return {}
    return {"order_ref": SELF_ORDER}


async def _call_all():
    out = {}
    async with Client(after_server.mcp) as client:
        for tool in await client.list_tools():
            out[tool.name] = await client.call_tool(
                tool.name, _args_for(tool.name), raise_on_error=False)
    return out


def test_no_canary_over_mcp():
    """What crosses the protocol, serialized, carries no canary values."""
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        results = asyncio.run(_call_all())
    # The calls must really run as the canary customer, or this test passes
    # on error strings and proves nothing.
    shipment = results["get_shipment_status"]
    assert not shipment.is_error, shipment.content
    assert shipment.structured_content["result"]["order_ref"] == SELF_ORDER
    blob = " ".join(json.dumps(r.structured_content or {})
                    + " ".join(str(c) for c in r.content)
                    for r in results.values())
    leaked = [m for m in CANARY_MARKERS if m in blob]
    assert not leaked, leaked
