"""Stage 6 -- canary PII tests.

Synthetic markers are seeded into the fixture database. The assertions below
say those markers must not appear in tool output, in logs, or in exception
messages -- and the tools under test are enumerated from the server's own
registry, so a tool added next quarter is covered without anyone remembering.

What this catches: a known field escaping through a declared output schema, a
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
    """Invoke every registered tool, whatever it is."""
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
    """A caller cannot reach another customer through any registered tool."""
    with Session(CANARY_SELF["id"]) as s:
        shaping.reset_budget(s.session_id)
        results = _call_all(OTHER_ORDER)
    found = _leaks(json.dumps(results))
    assert not [m for m in found if "other" in m or "Canaryb" in m
                or "Othermark" in m or m == CANARY_OTHER["phone"]
                or m == CANARY_OTHER["address_line1"]], found


def test_no_undeclared_self_fields_in_output():
    """Even the subject's own record only crosses where a schema declared it."""
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


def test_every_tool_declares_an_output_schema():
    """Fail closed: a tool without a declared schema is a build failure."""
    undeclared = [name for name, fn in after_server.TOOLS.items()
                  if not getattr(fn, "returns", None)]
    assert not undeclared, f"tools with no output schema: {undeclared}"
