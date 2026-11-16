# Article Listing 4: authorize the ticket before replying

The article's shortened `send_reply` example forwards the ticket reference
directly to `internal_api.post_reply`, omitting the ownership check already
present in `after/server.py`. Use the excerpt below to make that check explicit
in Listing 4. Keep the separate `address_confirmation` example below it.

This is a documentation correction. The runtime ownership check was introduced
in [PR #1](https://github.com/adwaitasathe/privacy_aware_mcp_server/pull/1).
The surrounding server supplies `shaped`, `current_subject`, `internal_api`, and
the existing `ReplyResult` output contract.

```python
@shaped(
    returns=ReplyResult,
    columns={"delivered": "tickets.status", "ticket_ref": "tickets.ticket_ref"},
    purpose="reply",
)
def send_reply(ticket_ref: str, body: str) -> ReplyResult:
    """Authorize the ticket before personalizing or sending a reply."""
    ticket = internal_api.get_ticket(ticket_ref)
    if not ticket or ticket["customer_id"] != current_subject():
        return {"delivered": False, "ticket_ref": ticket_ref}

    customer = internal_api.get_customer(current_subject())
    body = body.replace("{first_name}", customer["first_name"])
    return internal_api.post_reply(ticket_ref, body)
```

Add this explanation after the listing:

> A ticket reference identifies a record; it does not authorize access to it.
> Before personalizing or sending a reply, the server checks that the ticket
> belongs to the authenticated session subject. That subject comes from the
> verified session, never from a model-supplied customer identifier. Missing
> and unauthorized ticket references produce the same non-delivery response
> shape. Only a ticket owned by the session subject reaches
> `internal_api.post_reply`, which resolves the recipient address without
> exposing it to the model.

The internal API's recipient lookup does not enforce ownership; the MCP wrapper
must perform the check before invoking that action. The reference demo binds a
fixture subject. Production must bind the subject from verified authentication.
This example checks ownership, not whether the ticket is open.

Existing coverage:

- `tests/test_canary.py::test_reply_refuses_another_customers_ticket` checks
  that a foreign ticket is rejected and its message count does not change.
- `tests/test_canary.py::test_reply_fills_first_name_on_server` checks the
  authorized reply path without returning the customer's name to the model.
- `tests/test_mcp_protocol.py::test_mcp_results_for_every_registered_tool`
  checks successful, foreign and missing ticket references through MCP.

These tests bind synthetic sessions; they do not test upstream authentication.
