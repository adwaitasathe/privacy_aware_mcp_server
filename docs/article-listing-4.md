# Article Listing 4: authorize the ticket before replying

The article's shortened `send_reply` example forwards the ticket reference
directly to `internal_api.post_reply`, omitting the ownership check already
present in `after/server.py`. Use the excerpt below to make that check explicit
in Listing 4. Keep the separate `address_confirmation` example below it.

This is a documentation correction. The runtime ownership check was introduced
in [PR #1](https://github.com/adwaitasathe/privacy_aware_mcp_server/pull/1).
The surrounding server supplies `shaped`, `boundary`, `current_session`,
`current_subject`, `internal_api`, and the existing `ReplyResult` output
contract. `ticket_ref` is the session-scoped handle (`tkt_...`) that
`get_open_ticket` returned, not the internal ticket reference. The full version
in `after/server.py` also checks the handle prefix.

```python
@shaped(
    returns=ReplyResult,
    columns={"delivered": "tickets.status", "ticket_ref": "tickets.ticket_ref"},
    purpose="reply",
)
def send_reply(ticket_ref: str, body: str) -> ReplyResult:
    """Resolve the handle, authorize the ticket, then personalize and send."""
    refused = {"delivered": False, "ticket_ref": ticket_ref}
    try:
        internal_ref = boundary.resolve(current_session(), ticket_ref)
    except KeyError:
        return refused                    # raw ref, other session, or expired

    ticket = internal_api.get_ticket(internal_ref)
    if not ticket or ticket["customer_id"] != current_subject():
        return refused

    customer = internal_api.get_customer(current_subject())
    body = body.replace("{first_name}", customer["first_name"])
    sent = internal_api.post_reply(internal_ref, body)
    return {"delivered": sent["delivered"], "ticket_ref": ticket_ref}
```

Add this explanation after the listing:

> The model never sees the internal ticket reference. `get_open_ticket` returns
> a session-scoped handle, and `send_reply` resolves it on the server; a handle
> from another session, or one used after the session has closed, does not
> resolve. A resolved handle still does not authorize access, so before
> personalizing or sending a reply, the server checks that the ticket
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
- `tests/test_canary.py` also refuses a raw internal ref, a handle from another
  session, a handle after the session closes, and a handle issued for another
  customer's ticket.
- `tests/test_mcp_protocol.py::test_mcp_results_for_every_registered_tool`
  checks the handle flow (get_open_ticket, then send_reply) and refuses raw,
  foreign and missing references through MCP.

These tests bind synthetic sessions; they do not test upstream authentication.
