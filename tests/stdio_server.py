"""Test-only bootstrap: real registrations, synthetic identity, isolated DB.

This is not a production authentication mechanism. The demo entry points bind
SUBJECT_ID; the integration suite must instead exercise the seeded canaries.
"""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import internal_api  # noqa: E402
from fixtures.seed import CANARY_SELF  # noqa: E402
from session import Session  # noqa: E402


class AuditFormatter(logging.Formatter):
    def format(self, record):
        # Include audit extras and any exception traceback, not just "access".
        text = super().format(record)
        for key in ("event", "tool_args", "result"):
            if hasattr(record, key):
                text += " " + str(getattr(record, key))
        return text


if __name__ == "__main__":
    mode, db_path = sys.argv[1:]
    internal_api.DB = db_path
    if mode == "before":
        from before.server import mcp
    elif mode == "after":
        from after.server import mcp
    else:
        raise ValueError("unknown fixture server")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(AuditFormatter("%(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

    with Session(CANARY_SELF["id"]):
        mcp.run(transport="stdio", show_banner=False)
