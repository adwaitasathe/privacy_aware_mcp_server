"""Session identity.

The chat widget authenticates the customer before the agent is reachable. The
MCP server resolves the subject from that verified session and from nowhere
else. No tool signature in this repository accepts a customer identifier.

This is the control that answers "may this caller see this data". It is
necessary, it is well covered elsewhere, and it is assumed correct throughout
the article.
"""

import contextvars
import secrets

_subject = contextvars.ContextVar("subject_id")
_session = contextvars.ContextVar("session_id")


class Session:
    """Binds a verified subject to a request scope."""

    def __init__(self, subject_id: str):
        self.subject_id = subject_id
        self.session_id = "ses_" + secrets.token_hex(6)
        self._tokens = []

    def __enter__(self):
        self._tokens = [_subject.set(self.subject_id),
                        _session.set(self.session_id)]
        return self

    def __exit__(self, *exc):
        _subject.reset(self._tokens[0])
        _session.reset(self._tokens[1])
        return False


def current_subject() -> str:
    try:
        return _subject.get()
    except LookupError:
        raise PermissionError("no authenticated subject in scope")


def current_session() -> str:
    try:
        return _session.get()
    except LookupError:
        raise PermissionError("no session in scope")
