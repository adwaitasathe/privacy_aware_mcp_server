"""Stage 4 / Stage 5 -- session state ends with the session.

The token vault maps handles back to real values, so it is personal data in
its own right. Its lifetime is the session: when the session closes, the
mapping and the row budget are dropped without anyone calling cleanup by hand.
"""

import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "after"))

import boundary  # noqa: E402
import shaping  # noqa: E402
from after import server as after_server  # noqa: E402,F401  registers hooks
from fixtures.seed import SUBJECT_ID  # noqa: E402
from session import Session  # noqa: E402


def test_token_vault_is_dropped_when_session_closes():
    with Session(SUBJECT_ID) as s:
        token = boundary.tokenise(s.session_id, "cus_3f9a2b81", kind="sub")
        assert boundary.resolve(s.session_id, token) == "cus_3f9a2b81"
    with pytest.raises(KeyError):
        boundary.resolve(s.session_id, token)


def test_tool_calls_leave_no_vault_or_budget_behind():
    """A real tool call tokenises (the audit subject handle) and spends budget;
    closing the session must clear both."""
    with Session(SUBJECT_ID) as s:
        after_server.get_shipment_status("HW-4581")
        assert s.session_id in boundary._vault
        assert shaping.spent(s.session_id) > 0
    assert s.session_id not in boundary._vault
    assert shaping.spent(s.session_id) == 0


def test_cleanup_runs_even_when_the_session_errors():
    with pytest.raises(RuntimeError):
        with Session(SUBJECT_ID) as s:
            after_server.get_shipment_status("HW-4581")
            raise RuntimeError("tool failed")
    assert s.session_id not in boundary._vault
