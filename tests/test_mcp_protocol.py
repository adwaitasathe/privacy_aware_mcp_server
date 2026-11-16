"""Privacy checks on tools/list and tools/call across real stdio JSON-RPC.

These complement test_canary.py's direct Python policy tests. This module does
not enumerate TOOLS or call its functions; new registrations require explicit
test arguments and an independently reviewed expected field contract.
"""

import asyncio
import json
import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fixtures.seed import CANARY_MARKERS, CANARY_SELF, build  # noqa: E402

SELF_ORDER = "HW-Cself"
OTHER_ORDER = "HW-Cther"
SELF_TICKET = "HW-TCself"
OTHER_TICKET = "HW-TCther"

# This test-side contract is independent of the server's declarations. Checking
# only that outputSchema exists would accept a generic, unrestricted dict.
FIELDS = {
    "get_shipment_status": {"order_ref", "status", "promised_date",
                            "last_event_desc", "last_event_at", "delivering_to"},
    "get_order_summary": {"order_ref", "placed_at", "status", "item_count",
                          "is_gift"},
    "list_order_items": {"order_ref", "items"},
    "get_refund_status": {"order_ref", "status", "paid_with"},
    "get_open_ticket": {"ticket_ref", "status", "opened", "order_ref",
                        "latest_message"},
    "send_reply": {"delivered", "ticket_ref"},
}


def assert_private(blob):
    found = [marker for marker in CANARY_MARKERS if marker in blob]
    assert not found, f"private canaries escaped: {found}"


@pytest.fixture
def database(tmp_path):
    db = tmp_path / "havenware.db"
    build(str(db))
    # The stock canary tickets are closed. Open this one so get_open_ticket
    # exercises its actual result and contact-detail scrubbing, not just null.
    with sqlite3.connect(db) as con:
        con.execute("UPDATE tickets SET status = 'open' WHERE ticket_ref = ?",
                    (SELF_TICKET,))
    return db


@asynccontextmanager
async def connected(database, tmp_path, mode="after", check_logs=True):
    stderr = tmp_path / f"{mode}-stderr.log"
    transport = StdioTransport(
        command=sys.executable,
        args=[str(ROOT / "tests" / "stdio_server.py"), mode, str(database)],
        cwd=str(ROOT), keep_alive=False, log_file=stderr,
    )
    try:
        async with Client(transport, timeout=15, init_timeout=15) as client:
            yield client
    finally:
        if check_logs:
            assert_private(stderr.read_text())


def payload_schema(schema, name):
    if name == "send_reply":
        return schema
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"result"}
    assert schema["required"] == ["result"]
    variants = schema["properties"]["result"]["anyOf"]
    assert any(v.get("type") == "null" for v in variants)
    return next(v for v in variants if v.get("type") == "object")


def check_result(tool, result):
    # Scan the complete protocol object, including both content channels and
    # metadata; inspecting Client's hydrated .data would miss these surfaces.
    assert_private(result.model_dump_json(by_alias=True))
    assert result.is_error is False
    Draft202012Validator(tool.output_schema).validate(result.structured_content)
    payload = (result.structured_content if tool.name == "send_reply"
               else result.structured_content["result"])
    if payload is None:
        assert result.content == []
    else:
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        text_payload = json.loads(result.content[0].text)
        assert text_payload == payload
    if payload is not None:
        assert set(payload) == FIELDS[tool.name]
        if tool.name == "list_order_items":
            assert payload["items"]
            assert all(set(item) == {"product_name", "qty"}
                       for item in payload["items"])
    return payload


def arguments_for(name, order=SELF_ORDER, ticket=SELF_TICKET):
    if name == "get_open_ticket":
        return {}
    if name == "send_reply":
        return {"ticket_ref": ticket, "body": "Hi {first_name}, thanks."}
    return {"order_ref": order}


def test_mcp_catalog_advertises_closed_schemas(database, tmp_path):
    async def run():
        async with connected(database, tmp_path) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == set(FIELDS), (
                "update the protocol test cases when MCP registrations change")
            for tool in tools:
                assert tool.output_schema, tool.name
                Draft202012Validator.check_schema(tool.output_schema)
                Draft202012Validator.check_schema(tool.input_schema)
                expected_inputs = (set() if tool.name == "get_open_ticket" else
                                   {"ticket_ref", "body"} if tool.name == "send_reply"
                                   else {"order_ref"})
                assert set(tool.input_schema.get("properties", {})) == expected_inputs
                schema = payload_schema(tool.output_schema, tool.name)
                assert schema["type"] == "object"
                assert schema["additionalProperties"] is False
                assert set(schema["properties"]) == FIELDS[tool.name]
                assert set(schema["required"]) == FIELDS[tool.name]
                if tool.name == "list_order_items":
                    item = schema["properties"]["items"]["items"]
                    assert item["additionalProperties"] is False
                    assert set(item["properties"]) == {"product_name", "qty"}
    asyncio.run(run())


@pytest.mark.parametrize("target", ["self", "other", "missing"])
def test_mcp_results_for_every_registered_tool(database, tmp_path, target):
    async def run():
        order, ticket = {
            "self": (SELF_ORDER, SELF_TICKET),
            "other": (OTHER_ORDER, OTHER_TICKET),
            "missing": ("HW-missing", "HW-Tmissing"),
        }[target]
        async with connected(database, tmp_path) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == set(FIELDS)
            for tool in tools:
                result = await client.call_tool_mcp(
                    tool.name, arguments_for(tool.name, order, ticket))
                payload = check_result(tool, result)
                if tool.name == "send_reply":
                    assert payload["delivered"] is (target == "self")
                elif tool.name == "get_open_ticket":
                    assert payload["ticket_ref"] == SELF_TICKET
                    assert "[email removed]" in payload["latest_message"]
                elif target == "self":
                    assert payload["order_ref"] == SELF_ORDER
                else:
                    assert payload is None
    asyncio.run(run())


def test_mcp_no_open_ticket_is_null(database, tmp_path):
    with sqlite3.connect(database) as con:
        con.execute("UPDATE tickets SET status = 'closed' WHERE ticket_ref = ?",
                    (SELF_TICKET,))

    async def run():
        async with connected(database, tmp_path) as client:
            tool = next(t for t in await client.list_tools()
                        if t.name == "get_open_ticket")
            result = await client.call_tool_mcp(tool.name, {})
            assert check_result(tool, result) is None
    asyncio.run(run())


def test_mcp_validation_and_budget_errors_are_private(database, tmp_path):
    async def run():
        async with connected(database, tmp_path) as client:
            tools = await client.list_tools()
            for tool in tools:
                # All six tools reject a subject override at the MCP boundary.
                args = arguments_for(tool.name)
                args["customer_id"] = "untrusted-caller"
                result = await client.call_tool_mcp(tool.name, args)
                assert result.is_error is True
                assert_private(result.model_dump_json(by_alias=True))
                if tool.name == "get_open_ticket":
                    continue
                field = "ticket_ref" if tool.name == "send_reply" else "order_ref"
                for value in (None, 12345):
                    args = arguments_for(tool.name)
                    args[field] = value
                    result = await client.call_tool_mcp(tool.name, args)
                    assert result.is_error is True
                    assert_private(result.model_dump_json(by_alias=True))
                for value in ("", "'; DROP TABLE orders; --", "HW-" + "9" * 400):
                    args = arguments_for(tool.name)
                    args[field] = value
                    check_result(tool, await client.call_tool_mcp(tool.name, args))

        # A new process gives the budget test a fresh application session.
        async with connected(database, tmp_path) as client:
            tool = next(t for t in await client.list_tools()
                        if t.name == "get_order_summary")
            for _ in range(40):
                check_result(tool, await client.call_tool_mcp(
                    tool.name, {"order_ref": SELF_ORDER}))
            result = await client.call_tool_mcp(tool.name, {"order_ref": SELF_ORDER})
            assert result.is_error is True
            assert_private(result.model_dump_json(by_alias=True))
    asyncio.run(run())


def test_baseline_positive_control_reveals_five_markers(database, tmp_path):
    async def run():
        async with connected(database, tmp_path, mode="before",
                             check_logs=False) as client:
            result = await client.call_tool_mcp("get_customer", {})
            assert result.is_error is False
            expected = {CANARY_SELF[key] for key in
                        ("email", "phone", "address_line1", "first_name", "last_name")}
            # Verify both channels independently, so an empty/missing scan
            # cannot silently turn the positive control green.
            for value in (result.structured_content,
                          [block.model_dump(by_alias=True) for block in result.content]):
                blob = json.dumps(value)
                assert {m for m in CANARY_MARKERS if m in blob} == expected
                with pytest.raises(AssertionError, match="private canaries escaped"):
                    assert_private(blob)
    asyncio.run(run())
