# The 7-day bounce stop, measured from our own sends — 2026-09-22

The standing hard stop is **bounce > 2% on any mailbox over 7 days**. Every
stop checked in this project until today has been LIFETIME. This is the first
measurement of the rule as it is actually written.

`scripts/bounce_stop_7day.py` is the measurement, re-runnable, read-only.

---

## 1. THE ACTION LEDGER CANNOT ANSWER IT, AND THAT IS THE FIRST FINDING

The instruction was to measure the stop "from our own action ledger".
`work/action-ledger.jsonl` cannot answer it, and the reason is structural
rather than a gap to be filled in later:

    136 rows, all of them
      bison.activate        106
      heyreach.activate      18
      heyreach.add_lead      12
    states  attempted 64 · abandoned 41 · unresolved 26 · failed 5
    range   2026-09-15T18:04:25Z -> 2026-09-18T05:35:58Z

**It records what was ATTEMPTED against a provider, not what the provider
then did.** There is no send event and no bounce event in it of any kind, and
its last row predates every send this system has ever caused. A script that
derived a bounce rate from it would be reading activations as sends.

So the measurement reads the only record of our own sends that exists: the
per-message queue rows of the campaigns this system owns. Each row is one
message with its own `status`, `sent_at` and sender, and goes
`scheduled -> sent | bounced | stopped`. That is the same witness
`production_status` uses.

The client's own 327/328/352 are deliberately excluded. Their sends are not
our actions, and folding them in rebuilds the lifetime number this replaces.

## 2. THE MEASUREMENT

Window 2026-09-15T11:27Z to 2026-09-22T11:27Z, across 487, 489 and 491-498:

    mailbox 3437   sent 3   bounced 0   7-day rate 0.00%   campaign 489

    TRIPPED: none

Those three are 489's sends of 2026-09-21 at 13:34:48Z, 16:48:18Z and
20:37:54Z. They are every email this system has ever sent.

## 3. UNDEFINED IS NOT ZERO, AND IT IS MOST OF THE ESTATE

**153 of the 154 attested mailboxes have no 7-day bounce rate at all.** They
have sent nothing for us in the window, so the rule as written has no input
for them. That is UNDEFINED, and the script prints it as such rather than as
0%: a zero meaning "we never asked" is indistinguishable from a zero meaning
"nothing bounced", and it is the first reading that would clear a hold nobody
had evidence to clear.

This is the same distinction the register already enforces on `dns_failure`
and on `REFUSED IS NOT ROOM`. It applies here unchanged.

## 4. WHAT THIS DOES AND DOES NOT CHANGE

**Does not change:** the five lifetime holds stand. 3437 (2.14% over 8,947),
3760 (2.29%), 3743 (2.08%), 3761 (3.53%) and 3947 (2.68%) are all held on
LIFETIME evidence, which is a different and older question, and a 7-day
window with no data in it is not grounds to release any of them. The
conservative reading holds until there is a measurement, not until there is
an absence of one.

**3437 STAYS EXCLUDED.** Its 7-day rate is 0.00% and that is not a case for
reinstating it. It is excluded from every new batch by operator decision, and
489 runs its five leads to completion on it — also by operator decision, and
not an oversight. The clean week does not reopen the question; only the
operator does.

**Does change:** the hard stop is now checkable rather than asserted. It
answers `TRIPPED: none` today on real evidence, and it will answer on real
evidence the moment 491-498 start sending — 243 scheduled rows across 154
mailboxes, from 13:02Z today. Until then the honest state of the rule is that
it has one mailbox of input.

## 5. WHAT WOULD MAKE IT STRONGER

A send/bounce event of our own, written when the watcher observes a queue row
change state. Today the measurement is a provider read; if the provider
trimmed or re-planned a row, the history would go with it. The watchers
already see these transitions — `bison_watch_loop` prints SEND on both the
counter and the queue row — and nothing persists them.

That is a gap, not a defect, and it is named here so it is not rediscovered.
