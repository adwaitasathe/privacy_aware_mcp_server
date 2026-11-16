"""Stage 3 -- row caps and session budgets apply at every level.

Purpose tools return objects, and the rows they carry usually sit in a list
inside the object. These tests make sure a nested list is capped per call and
counted against the session budget item by item.
"""

import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "after"))

import internal_api  # noqa: E402
import shaping  # noqa: E402
from after import server as after_server  # noqa: E402
from fixtures.seed import SUBJECT_ID  # noqa: E402
from session import Session  # noqa: E402

ORDER = "HW-4581"
BIG = shaping.ROW_CAP + 15


@pytest.fixture
def big_order(monkeypatch):
    """The subject's own order, with more items than one call may return."""
    real = internal_api.get_order

    def get_order(ref):
        order = real(ref)
        if order and ref == ORDER:
            order["items"] = [{"product_name": f"item {i}", "qty": 1,
                               "sku": f"SKU-{i}"} for i in range(BIG)]
        return order

    monkeypatch.setattr(internal_api, "get_order", get_order)


def test_nested_list_is_capped_per_call(big_order):
    with Session(SUBJECT_ID) as s:
        shaping.reset_budget(s.session_id)
        result = after_server.list_order_items(ORDER)
    assert len(result["items"]) == shaping.ROW_CAP


def test_nested_rows_count_against_session_budget(big_order):
    with Session(SUBJECT_ID) as s:
        shaping.reset_budget(s.session_id)
        after_server.list_order_items(ORDER)
        assert shaping.spent(s.session_id) == shaping.ROW_CAP


def test_budget_stops_repeated_nested_calls(big_order):
    """Total rows across a session cannot exceed the budget."""
    calls = shaping.SESSION_ROW_BUDGET // shaping.ROW_CAP
    with Session(SUBJECT_ID) as s:
        shaping.reset_budget(s.session_id)
        for _ in range(calls):
            after_server.list_order_items(ORDER)
        with pytest.raises(shaping.BudgetExceeded):
            after_server.list_order_items(ORDER)
        assert shaping.spent(s.session_id) <= shaping.SESSION_ROW_BUDGET


def test_row_count_rules():
    count = shaping._row_count
    assert count({"a": 1}) == 1
    assert count([{"a": 1}, {"a": 2}]) == 2
    assert count({"order_ref": "x", "items": [{}, {}, {}]}) == 3
    assert count({"order_ref": "x", "items": []}) == 1
    assert count([{"items": [{}, {}]}, {"items": [{}]}]) == 3
