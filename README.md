# havenware-support-mcp

Working code for the InfoQ article **Building Privacy-Aware MCP Servers: An
Engineering Runbook**.

A customer-facing support agent over a fictional home-goods retailer, built
twice. `before/` is a competent thin wrapper over an existing internal REST API.
`after/` is the same server with the article's six-stage runbook applied. The
internal API does not change between them, because in practice it can't.

Every number quoted in the article is produced by `harness/measure.py` against
these two servers, not estimated.

```
Rows returned                   25  ->  2
Distinct fields in context      49  ->  9
Third-party subjects exposed     2  ->  0
Payload into model context  22,214  ->  453 bytes
Bytes written to logs       22,305  ->  445
Log contains response payloads yes  ->  no
Health disclosure in context   yes  ->  yes
```

That last row is deliberate. The customer typed the disclosure herself, so no
server-side control prevents it crossing. What changes is that it stops
accumulating in logs and tickets.

## Quick start

```bash
pip install -r requirements.txt

make seed      # build the deterministic fixture database
make classify  # Stage 1: every reachable column is classified (62 of 62)
make demo      # the before/after measurement above
make canary    # Stage 6: the canary PII suite (11 tests)
```

Python 3.12. No accounts, no API keys, no network access required.

To point an MCP client at either server:

```bash
python -m before.server    # the baseline
python -m after.server     # after the runbook
```

Both bind one fixture customer as the session subject so the tools can be
exercised by hand. A real deployment resolves that from the chat widget's
verified session.

## Where each runbook stage lives

| Stage | Article section | Code |
|---|---|---|
| 1. Classify what your server can touch | 5 | `after/classification.py` |
| 2. Scope tools to purposes | 6 | `after/server.py`, `session.py` |
| 3. Minimize every response | 7 | `after/shaping.py` |
| 4. Guard the model boundary | 8 | `after/boundary.py` |
| 5. Sanitize logs, set retention | 9 | `after/audit.py` |
| 6. Verify with canary tests | 10 | `tests/test_canary.py` |

Other files:

- `internal_api.py` — the REST API that predates MCP. Identical for both
  servers. It was a correct answer to the question it was built for.
- `before/server.py` — three entity-shaped tools and one line of payload
  logging. Session identity is already correct here; the leak is not an
  authorization bug.
- `harness/measure.py` — runs the same customer task against both and prints
  the comparison.
- `figures/` — the article's diagrams as SVG.

## The task everything measures

One ticket, one sentence:

> Where's my order? It was supposed to arrive Friday and I need it before my
> mother's surgery on the 14th.

Answering it needs three things: the shipment status on one order, the promised
date, and the customer's first name. The model needs only the first two. The
name is needed only in the outgoing reply, so the model writes `{first_name}`
and `send_reply` fills it in on the server. The name never enters context.

## CI

`.github/workflows/ci.yml` runs the article's own argument as build gates. The
build fails if a reachable column has no classification entry, if a canary
marker reaches tool output, a log, or an exception message, or if a tool ships
without a declared output schema.

## A note on the data

Every customer, order, ticket and address in `fixtures/` is synthetic and
generated from a fixed seed. Canary records use addresses at `1 Canary Row`,
phone numbers in the reserved `555-01xx` range, and `example.invalid` email
addresses, so they cannot route anywhere. No real personal data appears in this
repository.

Havenware does not exist. The failure patterns do.

## Licence

MIT. See `LICENSE`.
