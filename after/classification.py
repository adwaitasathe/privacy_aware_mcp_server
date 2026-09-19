"""Stage 1 -- classify every column the server can reach.

The registry lives beside the schema and is checked in. `audit_coverage()` runs
in CI and fails the build when a column has no entry, which is what catches
schema drift: the column somebody added six months ago that nobody classified.
"""

import enum
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                  "fixtures", "havenware.db")


class Class(enum.StrEnum):
    DIRECT = "direct_identifier"        # identifies a person on its own
    QUASI = "quasi_identifier"          # identifies in combination
    SENSITIVE = "sensitive_by_content"  # the value's meaning is sensitive
    THIRD_PARTY = "third_party"         # describes someone who is not the subject
    FREE_TEXT = "free_text_unclassified"  # a human typed whatever they wanted
    NON_PERSONAL = "non_personal"


REGISTRY: dict[str, Class] = {
    # customers
    "customers.id": Class.QUASI,
    "customers.email": Class.DIRECT,
    "customers.phone": Class.DIRECT,
    "customers.first_name": Class.DIRECT,
    "customers.last_name": Class.DIRECT,
    "customers.dob": Class.QUASI,
    "customers.address_line1": Class.DIRECT,
    "customers.city": Class.QUASI,
    "customers.region": Class.QUASI,
    "customers.postal_code": Class.QUASI,
    "customers.country": Class.QUASI,
    "customers.plan_tier": Class.QUASI,
    "customers.lifetime_value_cents": Class.QUASI,
    "customers.marketing_consent_email": Class.NON_PERSONAL,
    "customers.marketing_consent_sms": Class.NON_PERSONAL,
    "customers.cs_notes": Class.FREE_TEXT,
    "customers.created_at": Class.QUASI,

    # orders
    "orders.order_ref": Class.QUASI,
    "orders.customer_id": Class.QUASI,
    "orders.placed_at": Class.NON_PERSONAL,
    "orders.status": Class.NON_PERSONAL,
    "orders.total_cents": Class.NON_PERSONAL,
    "orders.is_gift": Class.NON_PERSONAL,
    "orders.gift_recipient_name": Class.THIRD_PARTY,
    "orders.gift_message": Class.THIRD_PARTY,
    "orders.ship_line1": Class.DIRECT,
    "orders.ship_city": Class.QUASI,
    "orders.ship_region": Class.QUASI,
    "orders.ship_postal": Class.QUASI,

    # order_items -- not identifiers, but a grab rail or a pregnancy test says
    # more about a person than their address does.
    "order_items.id": Class.NON_PERSONAL,
    "order_items.order_ref": Class.QUASI,
    "order_items.sku": Class.SENSITIVE,
    "order_items.product_name": Class.SENSITIVE,
    "order_items.qty": Class.NON_PERSONAL,
    "order_items.unit_price_cents": Class.NON_PERSONAL,

    # shipments -- a tracking number looks opaque, but it is a public lookup
    # key that resolves to a delivery address on the carrier's own site.
    "shipments.order_ref": Class.QUASI,
    "shipments.carrier": Class.NON_PERSONAL,
    "shipments.tracking_number": Class.QUASI,
    "shipments.promised_date": Class.NON_PERSONAL,
    "shipments.status": Class.NON_PERSONAL,
    "shipments.last_event_at": Class.NON_PERSONAL,
    "shipments.last_event_desc": Class.NON_PERSONAL,
    "shipments.delivery_address_snapshot": Class.DIRECT,

    # tickets
    "tickets.ticket_ref": Class.QUASI,
    "tickets.customer_id": Class.QUASI,
    "tickets.order_ref": Class.QUASI,
    "tickets.subject": Class.FREE_TEXT,
    "tickets.status": Class.NON_PERSONAL,
    "tickets.priority": Class.NON_PERSONAL,
    "tickets.created_at": Class.NON_PERSONAL,
    "ticket_messages.id": Class.NON_PERSONAL,
    "ticket_messages.ticket_ref": Class.QUASI,
    "ticket_messages.author_type": Class.NON_PERSONAL,
    "ticket_messages.body": Class.FREE_TEXT,
    "ticket_messages.created_at": Class.NON_PERSONAL,

    # charges
    "charges.order_ref": Class.QUASI,
    "charges.amount_cents": Class.NON_PERSONAL,
    "charges.card_brand": Class.NON_PERSONAL,
    "charges.card_last4": Class.QUASI,
    "charges.billing_postal": Class.QUASI,
    "charges.status": Class.NON_PERSONAL,
    "charges.decline_reason": Class.SENSITIVE,
}

PERSONAL = {Class.DIRECT, Class.QUASI, Class.SENSITIVE,
            Class.THIRD_PARTY, Class.FREE_TEXT}


def classify(column: str) -> Class:
    try:
        return REGISTRY[column]
    except KeyError:
        raise KeyError(f"{column} is not classified; add it to REGISTRY")


def audit_coverage(db_path: str = DB) -> list[str]:
    """Return every reachable column with no entry in the registry."""
    con = sqlite3.connect(db_path)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'")]
    missing = []
    for table in tables:
        for row in con.execute(f"PRAGMA table_info({table})"):
            column = f"{table}.{row[1]}"
            if column not in REGISTRY:
                missing.append(column)
    con.close()
    return missing


if __name__ == "__main__":
    import sys
    gaps = audit_coverage()
    if gaps:
        print("unclassified columns reachable from a tool:")
        for g in gaps:
            print(f"  {g}")
        sys.exit(1)
    print(f"all {len(REGISTRY)} reachable columns classified")
