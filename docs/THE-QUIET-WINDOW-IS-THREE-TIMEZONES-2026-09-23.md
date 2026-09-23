# The quiet window is three timezones, not two UTC ranges

For 2g, the cutover runbook, and for step 5 of `scripts/server/provision.sh`,
which pins the unattended-upgrades reboot.

---

## THE OLD DERIVATION WAS RIGHT AND IS NOT REUSABLE

`provision.sh` derived its 02:00Z reboot from:

    487  Mon-Fri 07:00-15:00Z
    489  Mon-Fri 13:00-21:00Z      -> quiet 21:00Z to 07:00Z

Both campaigns are finished. The live cohort is **491-498**, and the
operator's instruction for 2g was to derive the window from those.

Doing so gives **the same answer today**, which is the part worth being
careful about: an answer that agrees is not a derivation that transfers.

---

## 491-498 HAVE COHORT TIMEZONES, NOT UTC WINDOWS

From `docs/PRODUCTION-HANDOFF-2026-09-22-MORNING.md` §1:

    491,492,493,494,495   America/New_York
    496,497               Europe/London
    498                   Europe/Zagreb

The provider schedules inside each cohort's own business day rather than in
a window we set. The first sends confirm it — 13:02Z is 09:00 in New York,
08:10Z is 09:10 in London, 07:09Z is 09:09 in Zagreb. A 09:00-17:00 local
day reproduces every observed first send.

**So the union in UTC moves twice a year, in two different weeks**, because
the EU and the US do not change clocks on the same date:

    regime                      union            quiet band
    now, all DST on             07:00Z-21:00Z    21:00Z -> 07:00Z
    after EU falls back         08:00Z-21:00Z    21:00Z -> 08:00Z
    after US falls back         08:00Z-22:00Z    22:00Z -> 08:00Z

The old two-campaign derivation produced a **fixed** band. This one does not,
and anyone who reads the comment in November needs to see that.

---

## WHAT DOES NOT MOVE, AND WHAT DOES

**The reboot time does not move.** 02:00Z is inside the quiet band in all
three regimes. Step 5 keeps `Automatic-Reboot-Time "02:00"`.

**The margin against sourcing halves.** The nightly sourcing run is 02:00
Europe/Zagreb, which is a different UTC time in each regime:

    CEST (now)      02:00 Zagreb = 00:00Z      gap to the 02:00Z reboot: 2h
    CET  (winter)   02:00 Zagreb = 01:00Z      gap to the 02:00Z reboot: 1h

A sourcing run that grows past an hour meets the reboot — **and it meets it
in winter only**, which is the kind of fault that arrives once, looks like a
one-off, and is gone before anyone reproduces it.

This is not fixed here. The options are to pin sourcing in UTC like
everything else, to move the reboot later inside the band, or to make the
reboot defer while a sourcing run holds a lock. That is a decision about a
running production job, so it is named rather than taken.

---

## FOR THE CUTOVER RUNBOOK (2g)

The quiet window to cut over inside is **21:00Z - 07:00Z today**, narrowing
to **22:00Z - 08:00Z** after 2026-11-01. Both ends are the live cohort's,
not 487/489's.

Two things the runbook has to say that the band alone does not:

- **493, 496, 497 and 498 had first sends on 2026-09-24.** The table above
  already includes their timezones, so the band is correct for them — but
  they were not yet sending when it was measured, and a cutover that assumes
  "nothing is scheduled" has to check rather than assume.
- **495 was archived at 15:57:22Z on 09-23 by nobody we can name**
  (master `deea87b1`). It is in the cohort and it is not sending. Counting
  it as live overstates the constraint; counting it as gone loses the alert
  if it comes back.

---

## MEASUREMENT

Computed with `zoneinfo` against the three cohort zones at three dates
either side of both DST transitions, rather than by hand. The reboot time,
the sourcing time and the 09:00-17:00 local day are the inputs; the bands
above are the output.
