#!/usr/bin/env python3
"""What days a mailbox is already committed to, read from the sibling queues.

    PAGES=200 py -3 scripts/bison_forward_book.py

READ-ONLY GETs. This is the measurement that explained why campaign 487's ten
openers landed on 2026-09-23: `/campaigns/{id}/scheduled-emails` carries a
full `sender_email` object per row, so the client's own campaigns say what
each mailbox is already booked for, day by day. No other route on this
provider reports a sender's forward schedule or remaining capacity - asked of
the vendor's documentation and answered NOT DOCUMENTED.

**SAMPLE SIZE IS LOAD-BEARING AND THIS SCRIPT WILL LIE IF YOU RUSH IT.** At
PAGES=80 (3,600 rows) sender 2911 read ZERO on 2026-09-18 and a swap onto it
looked like the way to send a day early. At PAGES=200 (9,000 rows) the same
mailbox read 15. The zero was rows not yet reached, and the recommendation
built on it was wrong. Run it large, and treat a zero as "not seen yet" until
a bigger sample agrees.

Two things the large sample showed that the small one hid: two inboxes read
SIXTEEN against a configured limit of 15, so the limit is not provably a hard
per-day ceiling; and every mailbox reads zero beyond a certain date, so
"booked until X" and "the scheduler has not planned past X" are both
consistent with the same table.
"""
import collections, os, sys
sys.path.insert(0, os.path.abspath("."))
from src.providers import bison, load_env, request, ok
load_env()
TARGETS = {2736, 2903, 2904, 2906, 2911, 3437}
PAGES = int(os.environ.get("PAGES", "80"))
book = collections.defaultdict(collections.Counter)
rows_read = 0
for cid in (327, 328, 352):
    for page in range(1, PAGES + 1):
        url = bison.query(f"{bison.base()}/campaigns/{cid}/scheduled-emails",
                          {"page": page})
        status, data = request("GET", url, bison.headers())
        if not ok(status):
            break
        rows = (data or {}).get("data") or []
        if not rows:
            break
        for r in rows:
            rows_read += 1
            sid = (r.get("sender_email") or {}).get("id")
            if sid in TARGETS:
                book[sid][str(r.get("scheduled_date") or "")[:10]] += 1
print("rows sampled:", rows_read)
days = ["2026-09-18", "2026-09-19", "2026-09-21", "2026-09-22", "2026-09-23",
        "2026-09-24", "2026-09-25"]
print(f"{'sender':>8} " + " ".join(f"{d[5:]:>6}" for d in days) + "   limit")
for sid in sorted(TARGETS):
    line = f"{sid:>8} " + " ".join(f"{book[sid].get(d, 0):>6}" for d in days)
    print(line + "      15")
