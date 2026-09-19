"""Deterministic synthetic fixtures for the Havenware example.

Everything here is invented. No real personal data is used anywhere in this
repository. The seed is fixed so that every number quoted in the article
reproduces exactly.
"""

import os
import random
import sqlite3
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "havenware.db")
SEED = 20260913

SCHEMA = """
DROP TABLE IF EXISTS customers;
CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    email TEXT, phone TEXT, first_name TEXT, last_name TEXT, dob TEXT,
    address_line1 TEXT, city TEXT, region TEXT, postal_code TEXT, country TEXT,
    plan_tier TEXT, lifetime_value_cents INTEGER,
    marketing_consent_email INTEGER, marketing_consent_sms INTEGER,
    cs_notes TEXT, created_at TEXT
);

DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
    order_ref TEXT PRIMARY KEY, customer_id TEXT, placed_at TEXT, status TEXT,
    total_cents INTEGER, is_gift INTEGER,
    gift_recipient_name TEXT, gift_message TEXT,
    ship_line1 TEXT, ship_city TEXT, ship_region TEXT, ship_postal TEXT
);

DROP TABLE IF EXISTS order_items;
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY, order_ref TEXT, sku TEXT,
    product_name TEXT, qty INTEGER, unit_price_cents INTEGER
);

DROP TABLE IF EXISTS shipments;
CREATE TABLE shipments (
    order_ref TEXT PRIMARY KEY, carrier TEXT, tracking_number TEXT,
    promised_date TEXT, status TEXT, last_event_at TEXT, last_event_desc TEXT,
    delivery_address_snapshot TEXT
);

DROP TABLE IF EXISTS tickets;
CREATE TABLE tickets (
    ticket_ref TEXT PRIMARY KEY, customer_id TEXT, order_ref TEXT,
    subject TEXT, status TEXT, priority TEXT, created_at TEXT
);

DROP TABLE IF EXISTS ticket_messages;
CREATE TABLE ticket_messages (
    id INTEGER PRIMARY KEY, ticket_ref TEXT, author_type TEXT,
    body TEXT, created_at TEXT
);

DROP TABLE IF EXISTS charges;
CREATE TABLE charges (
    order_ref TEXT PRIMARY KEY, amount_cents INTEGER, card_brand TEXT,
    card_last4 TEXT, billing_postal TEXT, status TEXT, decline_reason TEXT
);
"""

FIRST = ["Dana", "Marcus", "Priya", "Tomas", "Ingrid", "Omar", "Leah", "Nikhil",
         "Sofia", "Ben", "Amara", "Ravi", "Clara", "Jonas", "Mei"]
LAST = ["Okafor", "Lindqvist", "Raman", "Duarte", "Halvorsen", "Bekele",
        "Novak", "Castellanos", "Thorne", "Abadi"]
CITIES = [("Portland", "OR", "97214"), ("Austin", "TX", "78704"),
          ("Madison", "WI", "53703"), ("Asheville", "NC", "28801"),
          ("Providence", "RI", "02906"), ("Boise", "ID", "83702")]
STREETS = ["Oak St", "Cedar Ave", "Larkspur Way", "Bellhaven Rd", "Mill Ln"]

PRODUCTS = [
    ("HW-LMP-011", "Ceramic table lamp", 8900),
    ("HW-RUG-204", "Wool area rug, 5x8", 24900),
    ("HW-CSH-077", "Linen cushion cover", 3400),
    ("HW-SHF-150", "Oak wall shelf", 11900),
    ("HW-THR-032", "Merino throw blanket", 9800),
    ("HW-VSE-088", "Stoneware vase", 4600),
    ("HW-MIR-119", "Arched hallway mirror", 18900),
    ("HW-GRB-041", "Bathroom grab rail, brushed steel", 5400),
    ("HW-BSK-066", "Seagrass storage basket", 3900),
    ("HW-CDL-023", "Beeswax pillar candle set", 2900),
]

TICKET_SUBJECTS = [
    "Damaged on arrival", "Wrong item shipped", "Return request",
    "Delivery delayed", "Missing part", "Refund not received",
    "Change of address", "Duplicate charge", "Question about care",
]

CUSTOMER_BODIES = [
    "The box arrived with a crushed corner and the item inside is chipped.",
    "I ordered two of these but only one turned up.",
    "Can I return this? It doesn't fit the room the way I hoped.",
    "Still hasn't arrived and the tracking hasn't updated in four days.",
    "There are no wall anchors in the package.",
    "The refund was approved two weeks ago but nothing has come through.",
    "I've moved. Can you send this to my new place instead?",
    "I think I was charged twice for the same order.",
    "Is this safe to put in the washing machine?",
]

AGENT_BODIES = [
    "Sorry about that. I've raised a replacement, no need to send the old one back.",
    "Thanks for flagging. I've shipped the missing unit today.",
    "No problem at all, I've emailed you a prepaid return label.",
    "I've chased the carrier and asked them to prioritise it.",
    "The anchors ship separately, I've expedited them for you.",
    "Confirmed, the refund is back on your card within three working days.",
    "Updated. Anything not yet dispatched will go to the new address.",
    "You're right, I've voided the duplicate authorisation.",
    "Cold wash, flat dry. I'd avoid the tumble dryer.",
]

# The customer the article follows.
SUBJECT_ID = "cus_3f9a2b81"

# The message the whole article hangs off.
TRIGGER_BODY = (
    "Where's my order? It was supposed to arrive Friday and I need it "
    "before my mother's surgery on the 14th."
)

# Canary markers. Deliberately unmistakable so a substring search cannot miss
# them, and deliberately in reserved ranges so they can never reach anyone.
CANARY_SELF = {
    "id": "cus_canary_self",
    "email": "canary-self-9d41d2@example.invalid",
    "phone": "555-0142",
    "first_name": "Canarya", "last_name": "Selfmark",
    "address_line1": "1 Canary Row",
}
CANARY_OTHER = {
    "id": "cus_canary_other",
    "email": "canary-other-77b3ce@example.invalid",
    "phone": "555-0199",
    "first_name": "Canaryb", "last_name": "Othermark",
    "address_line1": "2 Canary Row",
}
CANARY_MARKERS = [
    CANARY_SELF["email"], CANARY_SELF["phone"], CANARY_SELF["address_line1"],
    CANARY_OTHER["email"], CANARY_OTHER["phone"], CANARY_OTHER["address_line1"],
    "Canarya", "Canaryb", "Selfmark", "Othermark",
]


def _mk_customer(rng, cid, first=None, last=None, addr=None, email=None,
                 phone=None):
    city, region, postal = rng.choice(CITIES)
    first = first or rng.choice(FIRST)
    last = last or rng.choice(LAST)
    return (
        cid,
        email or f"{first.lower()}.{last.lower()}@example.invalid",
        phone or f"555-0{rng.randint(200, 899)}",
        first, last,
        str(date(rng.randint(1962, 1998), rng.randint(1, 12), rng.randint(1, 28))),
        addr or f"{rng.randint(1, 980)} {rng.choice(STREETS)}",
        city, region, postal, "US",
        rng.choice(["standard", "standard", "standard", "plus"]),
        rng.randint(4000, 480000),
        rng.randint(0, 1), rng.randint(0, 1),
        rng.choice([
            "", "",
            "Called in Jan about a delayed pallet, was understanding.",
            "Prefers email contact, said phone calls are difficult for her.",
            "Asked us not to leave parcels with the neighbour at number 12.",
        ]),
        str(date(2021, 4, 2) + timedelta(days=rng.randint(0, 1400))),
    )


def build(db_path=DB_PATH):
    rng = random.Random(SEED)
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)

    customers, orders, items, shipments, tickets, messages, charges = (
        [], [], [], [], [], [], [])
    item_id, msg_id = 1, 1

    # --- the subject customer -------------------------------------------
    subject = _mk_customer(
        rng, SUBJECT_ID, first="Dana", last="Okafor",
        addr="412 Oak St", email="dana.okafor@example.invalid",
        phone="555-0331")
    subject = list(subject)
    subject[7], subject[8], subject[9] = "Portland", "OR", "97214"
    subject[11] = "plus"
    subject[12] = 218400
    subject[15] = "Prefers email contact, said phone calls are difficult for her."
    customers.append(tuple(subject))

    # 14 orders over two years, one of them a gift to her sister.
    for i in range(14):
        ref = f"HW-{4100 + i * 37}"
        placed = date(2024, 6, 1) + timedelta(days=i * 51)
        is_gift = 1 if i == 9 else 0
        if is_gift:
            ship = ("88 Larkspur Way", "Asheville", "NC", "28801")
            recip, gmsg = ("Adaeze Okafor",
                           "Happy birthday! Hope this brightens the new flat. D x")
        else:
            ship = ("412 Oak St", "Portland", "OR", "97214")
            recip, gmsg = ("", "")
        n_items = rng.randint(1, 3)
        total = 0
        for _ in range(n_items):
            sku, name, price = rng.choice(PRODUCTS)
            qty = rng.randint(1, 2)
            total += price * qty
            items.append((item_id, ref, sku, name, qty, price))
            item_id += 1
        status = "delivered" if i < 13 else "in_transit"
        orders.append((ref, SUBJECT_ID, str(placed), status, total, is_gift,
                       recip, gmsg, *ship))
        charges.append((ref, total, rng.choice(["visa", "mastercard"]),
                        f"{rng.randint(1000, 9999)}", ship[3], "succeeded", ""))
        if i == 13:
            shipments.append((ref, "Meridian Freight", "MF4471820993",
                              "2026-09-11", "in_transit", "2026-09-10T14:02:00Z",
                              "Delayed at regional sort facility",
                              "412 Oak St, Portland, OR 97214"))
        else:
            shipments.append((ref, "Meridian Freight",
                              f"MF{rng.randint(1000000000, 9999999999)}",
                              str(placed + timedelta(days=4)), "delivered",
                              str(placed + timedelta(days=4)) + "T11:20:00Z",
                              "Delivered, left in porch",
                              f"{ship[0]}, {ship[1]}, {ship[2]} {ship[3]}"))

    # 9 tickets, 31 messages. #4812 is the live one.
    for t in range(9):
        tref = f"HW-T{4700 + t * 13}"
        created = date(2024, 8, 3) + timedelta(days=t * 79)
        tickets.append((tref, SUBJECT_ID, f"HW-{4100 + t * 37}",
                        TICKET_SUBJECTS[t], "closed", "normal", str(created)))
        messages.append((msg_id, tref, "customer", CUSTOMER_BODIES[t],
                         str(created))); msg_id += 1
        messages.append((msg_id, tref, "agent", AGENT_BODIES[t],
                         str(created))); msg_id += 1
        messages.append((msg_id, tref, "customer", "That works, thank you.",
                         str(created))); msg_id += 1
        if t % 2 == 0:
            messages.append((msg_id, tref, "agent",
                             "Glad we got there. Closing this one off.",
                             str(created))); msg_id += 1

    tickets.append(("HW-T4812", SUBJECT_ID, "HW-4581", "Where is my order?",
                    "open", "normal", "2026-09-13"))
    messages.append((msg_id, "HW-T4812", "customer", TRIGGER_BODY,
                     "2026-09-13")); msg_id += 1

    # --- canaries --------------------------------------------------------
    for c in (CANARY_SELF, CANARY_OTHER):
        customers.append(_mk_customer(
            rng, c["id"], first=c["first_name"], last=c["last_name"],
            addr=c["address_line1"], email=c["email"], phone=c["phone"]))
        ref = f"HW-C{c['id'][-4:]}"
        orders.append((ref, c["id"], "2026-08-01", "delivered", 8900, 0, "", "",
                       c["address_line1"], "Portland", "OR", "97214"))
        items.append((item_id, ref, "HW-LMP-011", "Ceramic table lamp", 1, 8900))
        item_id += 1
        shipments.append((ref, "Meridian Freight", "MF0000000001", "2026-08-05",
                          "delivered", "2026-08-05T09:00:00Z", "Delivered",
                          f"{c['address_line1']}, Portland, OR 97214"))
        charges.append((ref, 8900, "visa", "4242", "97214", "succeeded", ""))
        tref = f"HW-TC{c['id'][-4:]}"
        tickets.append((tref, c["id"], ref, "Canary ticket", "closed", "low",
                        "2026-08-06"))
        messages.append((msg_id, tref, "customer",
                         f"Reach me at {c['email']} or {c['phone']}.",
                         "2026-08-06")); msg_id += 1

    # --- background population ------------------------------------------
    for n in range(147):
        cid = f"cus_{rng.getrandbits(32):08x}"
        customers.append(_mk_customer(rng, cid))
        for i in range(rng.randint(1, 6)):
            ref = f"HW-{9000 + n * 7 + i}"
            sku, name, price = rng.choice(PRODUCTS)
            orders.append((ref, cid, "2025-11-02", "delivered", price, 0, "", "",
                           f"{rng.randint(1, 980)} {rng.choice(STREETS)}",
                           "Austin", "TX", "78704"))
            items.append((item_id, ref, sku, name, 1, price)); item_id += 1

    con.executemany("INSERT INTO customers VALUES (%s)" % ",".join("?" * 17),
                    customers)
    con.executemany("INSERT INTO orders VALUES (%s)" % ",".join("?" * 12), orders)
    con.executemany("INSERT INTO order_items VALUES (?,?,?,?,?,?)", items)
    con.executemany("INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?)", shipments)
    con.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?,?)", tickets)
    con.executemany("INSERT INTO ticket_messages VALUES (?,?,?,?,?)", messages)
    con.executemany("INSERT INTO charges VALUES (?,?,?,?,?,?,?)", charges)
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    p = build()
    con = sqlite3.connect(p)
    for t in ("customers", "orders", "order_items", "shipments", "tickets",
              "ticket_messages", "charges"):
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t:16} {n}")
    n = con.execute("SELECT COUNT(*) FROM orders WHERE customer_id=?",
                    (SUBJECT_ID,)).fetchone()[0]
    m = con.execute(
        "SELECT COUNT(*) FROM ticket_messages WHERE ticket_ref IN "
        "(SELECT ticket_ref FROM tickets WHERE customer_id=?)",
        (SUBJECT_ID,)).fetchone()[0]
    print(f"\nsubject orders   {n}\nsubject messages {m}")
