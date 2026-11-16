"""Stage 6 -- canary PII tests.

Synthetic markers are seeded into the fixture database. The assertions below
say those markers must not appear in tool output, in logs, or in exception
messages. These unit tests enumerate the application's TOOLS dictionary and
call its Python wrappers directly, not the MCP interface. Protocol discovery,
schemas and serialized results are covered separately in test_mcp_protocol.py.

What this catches: a known field escaping an application field allowlist, a
payload reaching a log, a row leaking through an exception string.

What it does not catch: anything in free text, and absence in general. A test
that passes is evidence, not proof. Saying so is part of shipping it.
"""

import json
import logging
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "after"))

import audit  # noqa: E402
import shaping  # noqa: E402
from after import server as after_server  # noqa: E402
from fixtures.seed import CANARY_MARKERS, CANARY_OTHER, CANARY_SELF  # noqa: E402
from session import Session  # noqa: E402

OTHER_ORDER = f"HW-C{CANARY_OTHER['id'][-4:]}"
SELF_ORDER = f"HW-C{CANARY_SELF['id'][-4:]}"


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.text = ""

    def emit(self, record):
        self.text += record.getMessage()
        for key in ("tool", "tool_args", "result", "event"):
            if hasattr(record, key):
                self.text += str(getattr(record, key))


def _leaks(blob: str) -> list[str]:
    return [m for m in CANARY_MARKERS if m in blob]


@pytest.fixture(autouse=True)
def _clean():
    audit.clear()
    yield


def _call_all(order_ref: str, ticket_ref: str = "HW-T0000"):
    """Invoke each application wrapper using this fixture's argument cases."""
    out = []
    for name, fn in after_server.TOOLS.items():
        try:
            if name == "send_reply":
                out.append(fn(ticket_ref, "test body"))
            elif name == "get_open_ticket":
                out.append(fn())
            else:
                out.append(fn(order_ref))
        except Exception as exc:  # noqa: BLE001 -- the message is the subject
            out.append({"exception": f"{type(exc).__name__}: {exc}"})
    return out


def test_no_other_subject_in_output():
    """Application wrappers exclude another customer's private canaries."""
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        results = _call_all(OTHER_ORDER)
    found = _leaks(json.dumps(results))
    assert not [m for m in found if "other" in m or "Canaryb" in m
                or "Othermark" in m or m == CANARY_OTHER["phone"]
                or m == CANARY_OTHER["address_line1"]], found


def test_no_undeclared_self_fields_in_output():
    """The subject's email, phone and full address stay out of these results."""
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        results = _call_all(SELF_ORDER)
    blob = json.dumps(results)
    assert CANARY_SELF["email"] not in blob
    assert CANARY_SELF["phone"] not in blob
    assert CANARY_SELF["address_line1"] not in blob


def test_no_canary_in_logs():
    capture = Capture()
    for name in ("havenware.audit", "havenware.mcp"):
        logging.getLogger(name).addHandler(capture)
        logging.getLogger(name).setLevel(logging.DEBUG)
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        _call_all(SELF_ORDER)
    for name in ("havenware.audit", "havenware.mcp"):
        logging.getLogger(name).removeHandler(capture)
    assert not _leaks(capture.text)


@pytest.mark.parametrize("bad_ref", [
    "", "'; DROP TABLE orders; --", "HW-" + "9" * 400, None, 12345,
    "../../etc/passwd", "HW-C" + CANARY_OTHER["id"],
])
def test_no_canary_in_exception_messages(bad_ref):
    """Error paths are where leaks actually happen and nobody tests them."""
    messages = []
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        for name, fn in after_server.TOOLS.items():
            try:
                fn(bad_ref, "body") if name == "send_reply" else (
                    fn() if name == "get_open_ticket" else fn(bad_ref))
            except Exception as exc:  # noqa: BLE001
                messages.append(f"{type(exc).__name__}: {exc}")
    assert not _leaks(" ".join(messages)), messages


def test_every_tool_declares_a_field_allowlist():
    """Require application metadata; this is not an MCP schema assertion."""
    undeclared = [name for name, fn in after_server.TOOLS.items()
                  if not getattr(fn, "returns", None)]
    assert not undeclared, f"tools with no field allowlist: {undeclared}"


SELF_TICKET = f"HW-TC{CANARY_SELF['id'][-4:]}"
OTHER_TICKET = f"HW-TC{CANARY_OTHER['id'][-4:]}"


def test_reply_fills_first_name_on_server():
    """The model writes a placeholder; the name is filled in server side.

    The name reaches the stored reply, and never the tool result.
    """
    import internal_api
    import boundary
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        # The handle get_open_ticket would hand the model for this ticket.
        handle = boundary.tokenise(s.session_id, SELF_TICKET, kind="tkt")
        result = after_server.send_reply(
            handle, "Hi {first_name}, your order is on its way.")
    assert result["delivered"] is True
    assert CANARY_SELF["first_name"] not in json.dumps(result)
    sent = internal_api.get_ticket(SELF_TICKET)["messages"][-1]["body"]
    assert sent == f"Hi {CANARY_SELF['first_name']}, your order is on its way."


def test_reply_refuses_another_customers_ticket():
    """send_reply is fenced by the session subject, like every order lookup."""
    import internal_api
    before = len(internal_api.get_ticket(OTHER_TICKET)["messages"])
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        result = after_server.send_reply(OTHER_TICKET, "Hi {first_name}")
    assert result["delivered"] is False
    after = internal_api.get_ticket(OTHER_TICKET)["messages"]
    assert len(after) == before


def _messages(ticket_ref):
    import internal_api
    return len(internal_api.get_ticket(ticket_ref)["messages"])


def test_reply_refuses_a_raw_internal_ref():
    """Actions take the handle the server issued, not the internal ref."""
    before = _messages(SELF_TICKET)
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        result = after_server.send_reply(SELF_TICKET, "Hi {first_name}")
    assert result["delivered"] is False
    assert _messages(SELF_TICKET) == before


def test_reply_refuses_a_handle_from_another_session():
    import boundary
    with Session(CANARY_SELF["id"]) as first:
        handle = boundary.tokenise(first.session_id, SELF_TICKET, kind="tkt")
        before = _messages(SELF_TICKET)
        with Session(CANARY_SELF["id"]) as second:
            shaping.reset_budget(second.session_id)
            result = after_server.send_reply(handle, "Hi {first_name}")
    assert result["delivered"] is False
    assert _messages(SELF_TICKET) == before


def test_reply_refuses_a_handle_after_the_session_closes():
    import boundary
    with Session(CANARY_SELF["id"]) as s:
        handle = boundary.tokenise(s.session_id, SELF_TICKET, kind="tkt")
    before = _messages(SELF_TICKET)
    with Session(CANARY_SELF["id"]) as later:
        shaping.reset_budget(later.session_id)
        result = after_server.send_reply(handle, "Hi {first_name}")
    assert result["delivered"] is False
    assert _messages(SELF_TICKET) == before


def test_reply_checks_ownership_even_for_an_issued_handle():
    """A handle issued in this session for someone else's ticket is still
    refused: resolving the handle is not the same as authorising the ticket."""
    import boundary
    before = _messages(OTHER_TICKET)
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        handle = boundary.tokenise(s.session_id, OTHER_TICKET, kind="tkt")
        result = after_server.send_reply(handle, "Hi {first_name}")
    assert result["delivered"] is False
    assert _messages(OTHER_TICKET) == before


def test_reply_returns_the_handle_never_the_internal_ref():
    import boundary
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        handle = boundary.tokenise(s.session_id, SELF_TICKET, kind="tkt")
        result = after_server.send_reply(handle, "test body")
    assert result == {"delivered": True, "ticket_ref": handle}
