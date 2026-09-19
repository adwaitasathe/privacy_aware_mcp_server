"""Stage 4 -- guard the model boundary.

The rule, in one line: the agent gets a handle, the server holds the value, and
actions take handles.

The boundary is asymmetric, and that is worth saying out loud. Outbound --
server to model -- is yours to govern, and everything below governs it.
Inbound -- customer to model -- is not. By the time a customer has typed a
health disclosure into the chat box it is already in context, and no server
design prevents that. Inbound free text is a retention problem, handled in
Stage 5, not a boundary problem.
"""

import re
import secrets

# session_id -> {token: real value}
_vault: dict[str, dict[str, str]] = {}


def tokenise(session_id: str, value: str, kind: str = "ref") -> str:
    """Give the model a stable handle for a value it must reason about.

    Stable within a session so the model can correlate, meaningless outside it,
    and never written to a log.
    """
    bucket = _vault.setdefault(session_id, {})
    for token, existing in bucket.items():
        if existing == value:
            return token
    token = f"{kind}_{secrets.token_hex(3)}"
    bucket[token] = value
    return token


def resolve(session_id: str, token: str) -> str:
    """Turn a handle back into a value, server side, at the moment of use."""
    try:
        return _vault[session_id][token]
    except KeyError:
        raise KeyError("unknown handle")


def discard(session_id: str) -> None:
    """Drop the reverse map. Called when the session ends; the TTL is the
    session, not a retention period."""
    _vault.pop(session_id, None)


def address_confirmation(line1: str, postal: str) -> str:
    """Render an address so the person who entered it recognises it and nobody
    else learns it.

    "412 Oak St" / "97214" -> "the address on Oak St ending 97214"

    This is the shape most confirmations actually need. The customer is
    checking we have the right address, not reading it out.
    """
    street = re.sub(r"^\d+\s+", "", line1).strip()
    return f"the address on {street} ending {postal}"


def card_confirmation(brand: str, last4: str) -> str:
    return f"the {brand} card ending {last4}"


_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email removed]"),
    (re.compile(r"\b\d{3}[-.\s]?\d{4}\b"), "[phone removed]"),
    (re.compile(r"\b\d{1,5}\s+\w+\s+(St|Ave|Rd|Way|Ln|Blvd)\b"),
     "[address removed]"),
]


def scrub_free_text(text: str, limit: int = 240) -> str:
    """Backstop for text a human wrote, and only a backstop.

    A detector cannot be the control. The control is not returning the raw
    thread at all -- this runs over the one bounded snippet that does cross,
    and catches the contact details customers paste into tickets.
    """
    out = text
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out[:limit]
