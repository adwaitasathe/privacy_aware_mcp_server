"""Havenware support MCP server -- after the runbook.

The tool list is not derived from the schema. It is derived from the ticket
reasons the support team already tracks: the six things customers actually
write in about. That is the bounding rule that keeps purpose-scoping from
turning into one tool per field.

The internal REST API underneath is unchanged. It did not need to change.
"""

import sys
from pathlib import Path

from fastmcp import FastMCP

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "after"))

import internal_api  # noqa: E402
import boundary  # noqa: E402
from session import Session, current_subject, current_session  # noqa: E402
from shaping import shaped  # noqa: E402

mcp = FastMCP("havenware-support")


def _own_order(order_ref: str) -> dict | None:
    """Every lookup is fenced by the session subject, not by an argument."""
    order = internal_api.get_order(order_ref)
    if not order or order["customer_id"] != current_subject():
        return None
    return order


# --- "where is my order" ------------------------------------------------
@shaped(
    returns={"order_ref": 1, "status": 1, "promised_date": 1,
             "last_event_desc": 1, "last_event_at": 1, "delivering_to": 1},
    columns={"order_ref": "orders.order_ref",
             "status": "shipments.status",
             "promised_date": "shipments.promised_date",
             "last_event_desc": "shipments.last_event_desc",
             "last_event_at": "shipments.last_event_at",
             "delivering_to": "orders.ship_postal"},
    purpose="delivery_status",
)
def get_shipment_status(order_ref: str) -> dict | None:
    """Check where a delivery has got to."""
    order = _own_order(order_ref)
    if not order or not order["shipment"]:
        return None
    s = order["shipment"]
    return {
        "order_ref": order["order_ref"],
        "status": s["status"],
        "promised_date": s["promised_date"],
        "last_event_desc": s["last_event_desc"],
        "last_event_at": s["last_event_at"],
        # Not the address. The confirmation form of the address.
        "delivering_to": boundary.address_confirmation(
            order["ship_line1"], order["ship_postal"]),
    }


# --- "what did I order" -------------------------------------------------
@shaped(
    returns={"order_ref": 1, "placed_at": 1, "status": 1, "item_count": 1,
             "is_gift": 1},
    columns={"order_ref": "orders.order_ref", "placed_at": "orders.placed_at",
             "status": "orders.status", "item_count": "order_items.qty",
             "is_gift": "orders.is_gift"},
    purpose="order_summary",
)
def get_order_summary(order_ref: str) -> dict | None:
    """Summarise an order without listing what was in it.

    Item names are classified sensitive_by_content. A grab rail or a pregnancy
    test says more about someone than their address does, so the default
    summary counts items rather than naming them. A customer who asks what was
    in the box gets `list_order_items`, which is a different purpose.
    """
    order = _own_order(order_ref)
    if not order:
        return None
    return {
        "order_ref": order["order_ref"],
        "placed_at": order["placed_at"],
        "status": order["status"],
        "item_count": sum(i["qty"] for i in order["items"]),
        # A gift order contains a third party's name and address. The model is
        # told one exists; it is not told who.
        "is_gift": bool(order["is_gift"]),
    }


# --- "what was in the box" ----------------------------------------------
@shaped(
    returns={"order_ref": 1, "items": {"product_name": 1, "qty": 1}},
    columns={"order_ref": "orders.order_ref",
             "product_name": "order_items.product_name",
             "qty": "order_items.qty"},
    purpose="order_contents",
)
def list_order_items(order_ref: str) -> dict | None:
    """List what was in an order, when the customer has asked."""
    order = _own_order(order_ref)
    if not order:
        return None
    return {"order_ref": order["order_ref"],
            "items": [{"product_name": i["product_name"], "qty": i["qty"]}
                      for i in order["items"]]}


# --- "where's my refund" ------------------------------------------------
@shaped(
    returns={"order_ref": 1, "status": 1, "paid_with": 1},
    columns={"order_ref": "charges.order_ref", "status": "charges.status",
             "paid_with": "charges.card_last4"},
    purpose="refund_status",
)
def get_refund_status(order_ref: str) -> dict | None:
    """Check the payment or refund state of an order."""
    order = _own_order(order_ref)
    if not order or not order["charge"]:
        return None
    c = order["charge"]
    return {"order_ref": order["order_ref"], "status": c["status"],
            "paid_with": boundary.card_confirmation(c["card_brand"],
                                                    c["card_last4"])}


# --- "what did I write in" about ----------------------------------------
@shaped(
    returns={"ticket_ref": 1, "status": 1, "opened": 1, "order_ref": 1,
             "latest_message": 1},
    columns={"ticket_ref": "tickets.ticket_ref", "status": "tickets.status",
             "opened": "tickets.created_at", "order_ref": "tickets.order_ref",
             "latest_message": "ticket_messages.body"},
    purpose="ticket_context",
)
def get_open_ticket() -> dict | None:
    """Fetch the customer's currently open ticket, if there is one.

    One ticket, not a history. The last message, not the thread. The snippet
    that does cross is scrubbed as a backstop -- customers paste contact
    details into tickets constantly, and no classification catches that.
    """
    tickets = [t for t in internal_api.list_tickets(current_subject())
               if t["status"] == "open"]
    if not tickets:
        return None
    t = tickets[0]
    last = t["messages"][-1] if t["messages"] else None
    return {
        "ticket_ref": t["ticket_ref"],
        "status": t["status"],
        "opened": t["created_at"],
        "order_ref": t["order_ref"],
        "latest_message": boundary.scrub_free_text(last["body"]) if last else "",
    }


# --- "get me a human" / reply -------------------------------------------
FIRST_NAME_PLACEHOLDER = "{first_name}"


@shaped(
    returns={"delivered": 1, "ticket_ref": 1},
    columns={"delivered": "tickets.status", "ticket_ref": "tickets.ticket_ref"},
    purpose="reply",
)
def send_reply(ticket_ref: str, body: str) -> dict:
    """Reply to the customer on their open ticket.

    The address is resolved inside the internal API, at the moment of sending.
    It is never a parameter, never a return value, and never in context.

    The customer's first name is handled the same way. The model only needs it
    in the outgoing message, not to reason about the task, so it writes the
    placeholder {first_name} and the server fills it in here. The name never
    enters context.
    """
    ticket = internal_api.get_ticket(ticket_ref)
    if not ticket or ticket["customer_id"] != current_subject():
        # Fenced by the session subject, like every order lookup. Without this
        # the server would fill in this customer's name and send it to
        # whoever owns the ticket.
        return {"delivered": False, "ticket_ref": ticket_ref}
    customer = internal_api.get_customer(current_subject())
    body = body.replace(FIRST_NAME_PLACEHOLDER, customer["first_name"])
    return internal_api.post_reply(ticket_ref, body)


TOOLS = {
    "get_shipment_status": get_shipment_status,
    "get_order_summary": get_order_summary,
    "list_order_items": list_order_items,
    "get_refund_status": get_refund_status,
    "get_open_ticket": get_open_ticket,
    "send_reply": send_reply,
}

for _name, _fn in TOOLS.items():
    mcp.tool(_fn)


if __name__ == "__main__":
    # Demo entry point. A real deployment resolves the subject from the
    # chat widget's verified session; here we bind one fixture customer so
    # the server can be pointed at an MCP client and poked by hand.
    from fixtures.seed import SUBJECT_ID

    with Session(SUBJECT_ID):
        mcp.run()
