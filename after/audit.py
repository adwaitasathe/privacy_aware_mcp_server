"""Stage 5 -- log what was touched, never what it said.

The event below is a typed record, not a dict. That matters: a dict grows a
`result` key the first time somebody is debugging at 2am, and then the log is
the largest store of personal data in the company. A typed event cannot grow
one without a code review.
"""

import dataclasses
import json
import logging

logger = logging.getLogger("havenware.audit")

_sink: list[dict] = []


@dataclasses.dataclass(frozen=True)
class AccessEvent:
    session_id: str
    subject_token: str
    tool: str
    purpose: str
    field_classes: tuple[str, ...]
    row_count: int
    budget_remaining: int

    def as_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)


def record(*, tool: str, purpose: str, rows: int, classes: list[str]) -> None:
    from session import current_session, current_subject
    from shaping import SESSION_ROW_BUDGET, spent
    from boundary import tokenise

    sid = current_session()
    event = AccessEvent(
        session_id=sid,
        # Even the audit trail gets a handle rather than the customer id.
        subject_token=tokenise(sid, current_subject(), kind="sub"),
        tool=tool,
        purpose=purpose,
        field_classes=tuple(classes),
        row_count=rows,
        budget_remaining=max(0, SESSION_ROW_BUDGET - spent(sid)),
    )
    _sink.append(dataclasses.asdict(event))
    logger.info("access", extra={"event": event.as_json()})


def events() -> list[dict]:
    return list(_sink)


def clear() -> None:
    _sink.clear()
