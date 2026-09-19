"""Havenware support MCP server -- baseline.

A thin wrapper over the existing internal REST API, exposing it to the support
agent behind the customer chat widget.

Note what is already right here. The subject identity comes from the verified
session, never from a tool argument, so there is no confused-deputy hole and no
cross-tenant exposure: a caller cannot reach another customer's data by asking.
Every tool is typed, documented and tested. This code passed review.

It still leaks.
"""

import json
import logging
import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import internal_api  # noqa: E402
from session import Session, current_subject  # noqa: E402

logger = logging.getLogger("havenware.mcp")

mcp = FastMCP("havenware-support")


@mcp.tool
def get_customer() -> dict:
    """Look up the signed-in customer's account record."""
    return internal_api.get_customer(current_subject())


@mcp.tool
def search_orders(query: str | None = None) -> list[dict]:
    """List the signed-in customer's orders, most recent first."""
    orders = internal_api.list_orders(current_subject())
    if query:
        q = query.lower()
        orders = [o for o in orders
                  if any(q in i["product_name"].lower() for i in o["items"])]
    return orders


@mcp.tool
def get_ticket_history(limit: int = 100) -> list[dict]:
    """Retrieve the signed-in customer's support tickets and their messages."""
    return internal_api.list_tickets(current_subject())[:limit]


@mcp.tool
def send_reply(ticket_ref: str, body: str) -> dict:
    """Post a reply on a support ticket."""
    return internal_api.post_reply(ticket_ref, body)


def log_tool_response(tool_name: str, args: dict, result) -> None:
    """Observability hook, wired into the server's middleware.

    One line, and it ships in more or less every service at Havenware.
    """
    logger.debug(
        "tool_response",
        extra={"tool": tool_name, "tool_args": args,
               "result": json.dumps(result)},
    )


TOOLS = {
    "get_customer": get_customer,
    "search_orders": search_orders,
    "get_ticket_history": get_ticket_history,
    "send_reply": send_reply,
}


if __name__ == "__main__":
    # Demo entry point. A real deployment resolves the subject from the
    # chat widget's verified session; here we bind one fixture customer so
    # the server can be pointed at an MCP client and poked by hand.
    from fixtures.seed import SUBJECT_ID

    with Session(SUBJECT_ID):
        mcp.run()
