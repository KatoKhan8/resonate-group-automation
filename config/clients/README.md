# Client config

One file per client, `config/clients/<client>.yaml`, in the shape BUILD-SPEC
section 4 documents. `src/clients.py` reads a strict subset of YAML: nested
maps, scalars, and inline lists in square brackets. It raises rather than
guessing, because a misread cap is money and a misread geo is a live customer
being cold sequenced.

A client file is required before a batch for that client can be ingested or
have personas applied. A record whose client has no config is skipped with a
logged reason; it never aborts the batch.

## Present

- `productive.yaml` — the worked example from BUILD-SPEC section 4.

## Missing, deliberately not invented

- `contactout.yaml` — the prototype's revive batches used a client called
  `contactout`, and `prototype/bin/prep.py` records a sender identity for it,
  but nothing in BUILD-SPEC or the prototype states that client's personas,
  title lists, angles, geos, size floor or cadence. Those cannot be filled in
  without inventing commercial policy, so the file is absent by choice.

  To run a revive batch for that client, add the file with the section 4 fields
  filled in from the client's actual ICP. Until then, revive behaviour is
  covered by fixtures under `tests/fixtures/`.
