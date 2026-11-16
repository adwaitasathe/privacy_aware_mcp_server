"""Stage 3 -- minimise every response.

Two ideas here.

The first is that minimisation is a server-side invariant, not per-handler
discipline. A tool declares the fields it returns; the decorator intersects the
handler's return value with that declaration. A handler that grows a new field
does not leak it, because the declaration did not change.

The second is that a per-call row cap is not a limit. An agent that can call a
tool ten times can have ten times the cap. Budgets are per session; caps are
per call; you need both.
"""

import collections
import functools
import typing

from pydantic import ConfigDict, with_config

from classification import PERSONAL, classify

ROW_CAP = 10          # rows one call may return
SESSION_ROW_BUDGET = 40   # rows one session may return in total

_spent: dict[str, int] = collections.defaultdict(int)


class BudgetExceeded(RuntimeError):
    """Raised when a session has drawn down its row budget.

    Carries no data, because exception messages are logged and surfaced.
    """


def _prune(value, allowed: dict):
    """Recursively keep only declared fields."""
    if isinstance(value, list):
        return [_prune(v, allowed) for v in value]
    if not isinstance(value, dict):
        return value
    out = {}
    for key, spec in allowed.items():
        if key not in value:
            continue
        out[key] = _prune(value[key], spec) if isinstance(spec, dict) \
            else value[key]
    return out


def _row_count(value) -> int:
    if isinstance(value, list):
        return max(1, len(value))
    return 1


def contract(cls):
    """Mark a TypedDict as a tool's output contract.

    The contract is closed: its JSON schema says `additionalProperties: false`,
    so an MCP client reading the tool definition is told that no other field
    will appear. Contracts nest -- a field typed as another contract, or a list
    of one, is described field by field too.
    """
    return with_config(ConfigDict(extra="forbid"))(cls)


def _is_contract(tp) -> bool:
    return isinstance(tp, type) and typing.is_typeddict(tp)


def allowlist(cls) -> dict:
    """Turn a contract into the nested allowlist `_prune` enforces.

    One declaration, two uses: this allowlist is what the middleware keeps, and
    the same TypedDict, as the tool's return type, is what FastMCP publishes as
    the tool's MCP `outputSchema`. They cannot drift apart.
    """
    out = {}
    for name, tp in typing.get_type_hints(cls).items():
        tp = _unwrap(tp)
        if _is_contract(tp):
            out[name] = allowlist(tp)
        elif typing.get_origin(tp) is list and typing.get_args(tp) \
                and _is_contract(_unwrap(typing.get_args(tp)[0])):
            out[name] = allowlist(_unwrap(typing.get_args(tp)[0]))
        else:
            out[name] = 1
    return out


def _unwrap(tp):
    """Strip NotRequired[...] / Required[...] so the inner type is visible."""
    while typing.get_origin(tp) in (typing.NotRequired, typing.Required):
        tp = typing.get_args(tp)[0]
    return tp


def shaped(*, returns: type, columns: dict[str, str], purpose: str):
    """Declare a tool's output contract.

    `returns` is a TypedDict marked with @contract. The middleware keeps only
    the fields it declares, and the decorated function must use the same
    TypedDict as its return type so the MCP tool definition advertises exactly
    the fields that can cross.
    `columns` maps each returned field to the source column it came from, so
    the audit trail can record which data classes crossed the boundary without
    recording any values.
    """
    if not _is_contract(returns):
        raise TypeError("returns must be a TypedDict output contract")
    fields = allowlist(returns)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            from session import current_session

            result = fn(*args, **kwargs)
            if result is None:
                return None

            shaped_result = _prune(result, fields)

            if isinstance(shaped_result, list) and len(shaped_result) > ROW_CAP:
                shaped_result = shaped_result[:ROW_CAP]

            sid = current_session()
            rows = _row_count(shaped_result)
            if _spent[sid] + rows > SESSION_ROW_BUDGET:
                raise BudgetExceeded(
                    "session row budget exhausted; narrow the request")
            _spent[sid] += rows

            from audit import record
            record(tool=fn.__name__, purpose=purpose, rows=rows,
                   classes=sorted({str(cls) for c in columns.values()
                                   for cls in classify(c) & PERSONAL}))
            return shaped_result

        wrapper.returns = returns
        wrapper.allowlist = fields
        wrapper.columns = columns
        wrapper.purpose = purpose
        return wrapper
    return decorator


def reset_budget(session_id: str) -> None:
    _spent.pop(session_id, None)


def spent(session_id: str) -> int:
    return _spent.get(session_id, 0)
