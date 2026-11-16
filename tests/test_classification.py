"""Stage 1 -- the registry's multi-class rules."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "after"))

from classification import (  # noqa: E402
    REGISTRY, STRICTNESS, Class, audit_coverage, classify, strictest)


def test_every_reachable_column_is_classified():
    assert audit_coverage() == []


def test_every_column_carries_at_least_one_class():
    assert all(REGISTRY.values())


def test_non_personal_is_never_combined():
    """A column is either non-personal or personal; never both."""
    mixed = [c for c, classes in REGISTRY.items()
             if Class.NON_PERSONAL in classes and len(classes) > 1]
    assert not mixed, mixed


def test_overlapping_classes_are_kept():
    assert classify("orders.gift_recipient_name") == {
        Class.THIRD_PARTY, Class.DIRECT}
    assert classify("orders.gift_message") == {
        Class.THIRD_PARTY, Class.FREE_TEXT}


def test_strictest_wins():
    assert strictest("orders.gift_recipient_name") is Class.THIRD_PARTY
    assert strictest("orders.gift_message") is Class.THIRD_PARTY
    assert strictest("customers.email") is Class.DIRECT


def test_strictness_covers_every_class():
    assert set(STRICTNESS) == set(Class)
