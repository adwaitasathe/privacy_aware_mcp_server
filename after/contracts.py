"""JSON output contracts published by the MCP tools.

The shaping decorator's ``returns`` metadata is a local field allowlist. These
schemas are the separate, typed contract a client discovers with ``tools/list``
and uses to validate ``tools/call`` structured results. Objects are closed at
every level, including objects inside arrays.

These FastMCP contracts use an object root. The five lookup tools can return
``None``, so their structured output uses ``{"result": object | null}``.
FastMCP's wrap-result extension serializes the existing handler return into
that envelope without changing direct Python calls or the measurement harness.
"""


def _object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable_result(properties: dict) -> dict:
    schema = _object({"result": {"anyOf": [
        _object(properties), {"type": "null"},
    ]}})
    schema["x-fastmcp-wrap-result"] = True
    return schema


OUTPUT_SCHEMAS = {
    "get_shipment_status": _nullable_result({
        "order_ref": {"type": "string"},
        "status": {"type": "string"},
        "promised_date": {"type": "string"},
        "last_event_desc": {"type": "string"},
        "last_event_at": {"type": "string"},
        "delivering_to": {"type": "string"},
    }),
    "get_order_summary": _nullable_result({
        "order_ref": {"type": "string"},
        "placed_at": {"type": "string"},
        "status": {"type": "string"},
        "item_count": {"type": "integer"},
        "is_gift": {"type": "boolean"},
    }),
    "list_order_items": _nullable_result({
        "order_ref": {"type": "string"},
        "items": {"type": "array", "items": _object({
            "product_name": {"type": "string"},
            "qty": {"type": "integer"},
        })},
    }),
    "get_refund_status": _nullable_result({
        "order_ref": {"type": "string"},
        "status": {"type": "string"},
        "paid_with": {"type": "string"},
    }),
    "get_open_ticket": _nullable_result({
        "ticket_ref": {"type": "string"},
        "status": {"type": "string"},
        "opened": {"type": "string"},
        "order_ref": {"type": "string"},
        "latest_message": {"type": "string"},
    }),
    "send_reply": _object({
        "delivered": {"type": "boolean"},
        "ticket_ref": {"type": "string"},
    }),
}
