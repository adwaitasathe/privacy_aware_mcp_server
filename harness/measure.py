"""Measure what crosses the boundary, before and after.

The agent's tool *choices* depend on the model. What each tool hands back does
not -- it is a property of the server. So this harness fixes the tool calls to
the ones the task requires and measures the payload, which is the part the
article is making claims about.

Task: ticket HW-T4812. "Where's my order? It was supposed to arrive Friday and
I need it before my mother's surgery on the 14th."
"""

import json
import logging
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "after"))
sys.path.insert(0, str(_root / "before"))

from session import Session  # noqa: E402
import audit  # noqa: E402
import boundary  # noqa: E402
import shaping  # noqa: E402
from classification import PERSONAL, REGISTRY, Class, classify  # noqa: E402
from fixtures.seed import SUBJECT_ID, TRIGGER_BODY  # noqa: E402

SUBJECT_ORDER = "HW-4581"
SUBJECT_TICKET = "HW-T4812"

# Field name -> source column, for the baseline's pass-through responses.
_BASELINE_COLUMNS = {}
for _col in REGISTRY:
    _BASELINE_COLUMNS.setdefault(_col.split(".", 1)[1], _col)


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        parts = [record.getMessage()]
        for key in ("tool", "tool_args", "result", "event"):
            if hasattr(record, key):
                parts.append(str(getattr(record, key)))
        self.lines.append(" ".join(parts))


def walk(value, path=""):
    """Yield (field_name, value) for every leaf in a response."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from walk(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v, path)
    else:
        yield path, value


def profile(payloads: list, columns_for) -> dict:
    fields, classes, rows, subjects = set(), set(), 0, set()
    for payload in payloads:
        rows += len(payload) if isinstance(payload, list) else 1
        for name, value in walk(payload):
            fields.add(name)
            col = columns_for(name)
            if col:
                try:
                    cls = classify(col)
                except KeyError:
                    continue
                classes.update(str(c) for c in cls & PERSONAL)
                # A third party is counted by the value that identifies them,
                # not by every column that describes them.
                if {Class.THIRD_PARTY, Class.DIRECT} <= cls and value:
                    subjects.add(str(value))
    blob = json.dumps(payloads)
    return {
        "tool_calls": len(payloads),
        "rows": rows,
        "distinct_fields": len(fields),
        "personal_classes": sorted(classes),
        "third_party_subjects": len(subjects),
        "bytes_into_context": len(blob),
        "health_disclosure_present": "surgery" in blob,
    }


def run_baseline():
    import server as before_server

    capture = LogCapture()
    log = logging.getLogger("havenware.mcp")
    log.setLevel(logging.DEBUG)
    log.addHandler(capture)

    payloads = []
    with Session(SUBJECT_ID):
        for name in ("get_customer", "search_orders", "get_ticket_history"):
            fn = before_server.TOOLS[name]
            result = fn()
            before_server.log_tool_response(name, {}, result)
            payloads.append(result)

    log.removeHandler(capture)
    stats = profile(payloads, lambda f: _BASELINE_COLUMNS.get(f))
    stats["log_bytes"] = sum(len(line) for line in capture.lines)
    stats["log_contains_payload"] = any("surgery" in line
                                        for line in capture.lines)
    return stats


def run_after():
    import importlib
    after_server = importlib.import_module("after.server")

    audit.clear()
    capture = LogCapture()
    log = logging.getLogger("havenware.audit")
    log.setLevel(logging.INFO)
    log.addHandler(capture)

    payloads = []
    with Session(SUBJECT_ID) as s:
        shaping.reset_budget(s.session_id)
        payloads.append(after_server.get_open_ticket())
        payloads.append(after_server.get_shipment_status(SUBJECT_ORDER))
        boundary.discard(s.session_id)

    log.removeHandler(capture)

    def columns_for(field):
        for fn in after_server.TOOLS.values():
            if field in fn.columns:
                return fn.columns[field]
        return None

    stats = profile([p for p in payloads if p], columns_for)
    stats["log_bytes"] = sum(len(line) for line in capture.lines)
    stats["log_contains_payload"] = any("surgery" in line
                                        for line in capture.lines)
    stats["audit_events"] = len(audit.events())
    return stats


def main():
    print(f"task: {TRIGGER_BODY}\n")
    before, after = run_baseline(), run_after()

    keys = ["tool_calls", "rows", "distinct_fields", "third_party_subjects",
            "bytes_into_context", "log_bytes", "health_disclosure_present",
            "log_contains_payload"]
    print(f"{'metric':<28}{'before':>12}{'after':>12}")
    print("-" * 52)
    for k in keys:
        print(f"{k:<28}{str(before[k]):>12}{str(after[k]):>12}")
    print(f"\nbefore personal classes: {', '.join(before['personal_classes'])}")
    print(f"after  personal classes: {', '.join(after['personal_classes'])}")
    print(f"after  audit events:     {after['audit_events']}")

    ratio = before["bytes_into_context"] / max(1, after["bytes_into_context"])
    print(f"\ncontext payload reduced {ratio:.0f}x")
    return before, after


if __name__ == "__main__":
    main()
