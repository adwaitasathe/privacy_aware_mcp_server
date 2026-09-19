"""Havenware's internal REST API.

This module stands in for an HTTP service that has existed since long before
anyone at Havenware had heard of MCP. It backs the internal admin console,
where a support rep sits behind SSO looking at a screen.

Its response shapes are not a mistake. A human triaging an account needs the
whole record in front of them, and paginating an admin screen at ten rows
would make the tool worse. Every endpoint below is a reasonable answer to the
question it was built to answer.

Nothing in this file changes anywhere in the article. The point is that it
should not have to.
"""

import os
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "fixtures", "havenware.db")


def _conn():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


# GET /internal/v1/customers/{id}
def get_customer(customer_id: str) -> dict | None:
    with _conn() as con:
        cur = con.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        row = cur.fetchone()
        return dict(row) if row else None


# GET /internal/v1/customers?email=
def find_customer_by_email(email: str) -> dict | None:
    with _conn() as con:
        cur = con.execute("SELECT * FROM customers WHERE email = ?", (email,))
        row = cur.fetchone()
        return dict(row) if row else None


# GET /internal/v1/customers/{id}/orders
def list_orders(customer_id: str) -> list[dict]:
    with _conn() as con:
        orders = _rows(con.execute(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY placed_at DESC",
            (customer_id,)))
        for o in orders:
            o["items"] = _rows(con.execute(
                "SELECT * FROM order_items WHERE order_ref = ?",
                (o["order_ref"],)))
            ship = con.execute(
                "SELECT * FROM shipments WHERE order_ref = ?",
                (o["order_ref"],)).fetchone()
            o["shipment"] = dict(ship) if ship else None
            chg = con.execute(
                "SELECT * FROM charges WHERE order_ref = ?",
                (o["order_ref"],)).fetchone()
            o["charge"] = dict(chg) if chg else None
        return orders


# GET /internal/v1/orders/{ref}
def get_order(order_ref: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM orders WHERE order_ref = ?",
                          (order_ref,)).fetchone()
        if not row:
            return None
        o = dict(row)
        o["items"] = _rows(con.execute(
            "SELECT * FROM order_items WHERE order_ref = ?", (order_ref,)))
        ship = con.execute("SELECT * FROM shipments WHERE order_ref = ?",
                           (order_ref,)).fetchone()
        o["shipment"] = dict(ship) if ship else None
        chg = con.execute("SELECT * FROM charges WHERE order_ref = ?",
                          (order_ref,)).fetchone()
        o["charge"] = dict(chg) if chg else None
        return o


# GET /internal/v1/customers/{id}/tickets
def list_tickets(customer_id: str) -> list[dict]:
    with _conn() as con:
        tickets = _rows(con.execute(
            "SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,)))
        for t in tickets:
            t["messages"] = _rows(con.execute(
                "SELECT * FROM ticket_messages WHERE ticket_ref = ? "
                "ORDER BY id", (t["ticket_ref"],)))
        return tickets


# GET /internal/v1/tickets/{ref}
def get_ticket(ticket_ref: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM tickets WHERE ticket_ref = ?",
                          (ticket_ref,)).fetchone()
        if not row:
            return None
        t = dict(row)
        t["messages"] = _rows(con.execute(
            "SELECT * FROM ticket_messages WHERE ticket_ref = ? ORDER BY id",
            (ticket_ref,)))
        return t


# POST /internal/v1/tickets/{ref}/reply
def post_reply(ticket_ref: str, body: str) -> dict:
    """Sends a reply to whatever address is on file for the ticket's customer.

    The caller never needs to know the address. It never did -- the admin UI
    passed a ticket reference too.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT c.email FROM tickets t JOIN customers c "
            "ON c.id = t.customer_id WHERE t.ticket_ref = ?",
            (ticket_ref,)).fetchone()
        if not row:
            return {"delivered": False, "reason": "unknown_ticket"}
        con.execute(
            "INSERT INTO ticket_messages (ticket_ref, author_type, body, "
            "created_at) VALUES (?, 'agent', ?, date('now'))",
            (ticket_ref, body))
        return {"delivered": True, "ticket_ref": ticket_ref}
