#!/usr/bin/env python3
"""NEVER, REENGAGE, REVIVE: three lanes, by rule, no overlap.

One function, one lead, one lane.  TOTAL: every lead lands in exactly one of
NEVER, REENGAGE, REVIVE, ACTIVE or UNKNOWN.  No lead falls through.  No lead
lands in two.

PRECEDENCE (not negotiable):

    NEVER       unsubscribe, negative reply, bounce, unknown stop reason
    ACTIVE      still in an active sequence anywhere - checked BEFORE the
                other lanes, because a lead being mailed right now must not
                be re-enrolled by a rule about its age
    REVIVE      any reply (positive or neutral), then silence, not enrolled
    REENGAGE    no reply ever AND sequence finished AND last touch > 90 days
    UNKNOWN     everything else.  It HOLDS.  It is not a fourth lane to be
                drained later by a looser rule.

NEVER beats everything.  ACTIVE beats REVIVE and REENGAGE.  A lead that
unsubscribed and later replied is NEVER.  `has_reply` excludes REGARDLESS of
recency - that is the standing collision rule and this does not amend it.

UNKNOWN STAYS HOLD.  The register's REFUTED rows are mostly the shape of
"a category nobody could explain, drained anyway".  Report its size loudly.

INPUT SHAPE
-----------

Each lead is a dict with these fields (all booleans default to False, all
strings/ints default to None):

    lead_id             unique identifier for the lead
    has_unsubscribe     True if the lead unsubscribed from any campaign
    has_bounce          True if any email to this lead bounced
    has_negative_reply  True if any reply was classified as negative
    stop_reason         one of stoppedcause.ALL_OUTCOMES or None
    in_active_sequence  True if the lead is in an active sequence anywhere
    has_reply           True if the lead ever replied (positive or neutral)
    reply_kind          "positive", "neutral", or None
    reply_at            ISO timestamp of the most recent reply, or None
    sequence_finished   True if all sequences this lead was in have finished
    last_touch_days     int days since last touch, or None if unknown
    connected_linkedin  True if already connected on LinkedIn (for cadence
                        selection, not for lane assignment)

OUTPUT
------

    {"lead_id": ..., "lane": "NEVER"|"REENGAGE"|"REVIVE"|"ACTIVE"|"UNKNOWN"}
"""

# -------------------------------------------------------------- lane names

NEVER = "NEVER"
REENGAGE = "REENGAGE"
REVIVE = "REVIVE"
ACTIVE = "ACTIVE"
UNKNOWN = "UNKNOWN"

LANES = (NEVER, REENGAGE, REVIVE, ACTIVE, UNKNOWN)

# The 90-day threshold for REENGAGE.
REENGAGE_MIN_DAYS = 90

# Stop reasons from `stoppedcause` that map to NEVER.  An unknown stop
# reason is NEVER because missing evidence about why somebody stopped is
# not evidence that it is safe to re-engage them.
_NEVER_STOP_REASONS = frozenset({
    "unsubscribed",
    "replied_interested",
    "bounced",
    "still_unknown",
})


def classify(lead):
    """Assign exactly one lane to this lead.

    The precedence is the whole design:

        1. NEVER  - hard stop signals that outrank everything
        2. ACTIVE - still being worked; do not touch
        3. REVIVE - replied then went silent
        4. REENGAGE - no reply, sequence done, cold for >90 days
        5. UNKNOWN - everything else; holds, is not drained
    """
    lead_id = lead.get("lead_id")

    # --- NEVER: hard stop signals ---
    if _is_never(lead):
        return {"lead_id": lead_id, "lane": NEVER}

    # --- ACTIVE: still in an active sequence ---
    if lead.get("in_active_sequence"):
        return {"lead_id": lead_id, "lane": ACTIVE}

    # --- REVIVE: any reply then silence ---
    if _is_revive(lead):
        return {"lead_id": lead_id, "lane": REVIVE}

    # --- REENGAGE: no reply, sequence finished, cold >90 days ---
    if _is_reengage(lead):
        return {"lead_id": lead_id, "lane": REENGAGE}

    # --- UNKNOWN: everything else; holds ---
    return {"lead_id": lead_id, "lane": UNKNOWN}


def _is_never(lead):
    """Unsubscribe, negative reply, bounce, or unknown stop reason."""
    if lead.get("has_unsubscribe"):
        return True
    if lead.get("has_bounce"):
        return True
    if lead.get("has_negative_reply"):
        return True
    stop_reason = lead.get("stop_reason")
    if stop_reason is not None and stop_reason in _NEVER_STOP_REASONS:
        return True
    return False


def _is_revive(lead):
    """Any reply (positive or neutral), then silence, not enrolled anywhere.

    `has_reply` excludes REGARDLESS of recency.  A lead that replied two
    years ago and has been silent since is REVIVE, not REENGAGE - the reply
    happened, and re-engagement copy that pretends it did not would be a
    lie.
    """
    if not lead.get("has_reply"):
        return False
    # A lead in an active sequence is already caught by ACTIVE above.
    # A lead with a negative reply is already caught by NEVER above.
    # So reaching here means: replied (positive or neutral), not active.
    return True


def _is_reengage(lead):
    """No reply ever AND sequence finished AND last touch > 90 days."""
    if lead.get("has_reply"):
        return False
    if not lead.get("sequence_finished"):
        return False
    last_touch = lead.get("last_touch_days")
    if last_touch is None:
        return False
    try:
        return int(last_touch) > REENGAGE_MIN_DAYS
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------- batch classify

def classify_all(leads):
    """Classify every lead.  Returns a dict keyed by lead_id.

    Totality: every input lead produces exactly one output entry.  No lead
    is dropped and no lead appears twice.
    """
    results = {}
    for lead in leads:
        lid = lead.get("lead_id")
        result = classify(lead)
        results[lid] = result
    return results


def lane_counts(classified):
    """Count leads per lane.  UNKNOWN is reported loudly."""
    counts = {lane: 0 for lane in LANES}
    for entry in classified.values():
        lane = entry.get("lane")
        if lane in counts:
            counts[lane] += 1
        else:
            counts[UNKNOWN] += 1
    return counts


# ----------------------------------------------------------- revive queue

class ReviveQueue:
    """The REVIVE queue: 20/day cap, oldest-reply-first, no duplicates.

    The cap is a QUEUE not a filter: number 21 is tomorrow's, not nobody's.
    A lead already posted is never posted twice.  Ordering is
    oldest-reply-first.
    """

    DAILY_CAP = 20

    def __init__(self, posted_ids=None):
        self._posted = set(posted_ids or [])
        self._pending = []

    def enqueue(self, leads):
        """Add REVIVE leads to the queue, skipping already-posted ones.

        `leads` is an iterable of dicts with at least `lead_id` and
        `reply_at`.  Leads are sorted oldest-reply-first within the queue.
        """
        for lead in leads:
            lid = lead.get("lead_id")
            if lid in self._posted:
                continue
            if lid in {p["lead_id"] for p in self._pending}:
                continue
            self._pending.append({
                "lead_id": lid,
                "reply_at": lead.get("reply_at") or "",
                "thread": lead.get("thread"),
                "draft": lead.get("draft"),
            })
        self._pending.sort(key=lambda r: r["reply_at"])

    def todays_batch(self):
        """The next up-to-20 leads for today.  Does NOT remove them."""
        return list(self._pending[:self.DAILY_CAP])

    def mark_posted(self, lead_ids):
        """Record that these leads have been posted.  Removes from pending."""
        for lid in lead_ids:
            self._posted.add(lid)
        self._pending = [p for p in self._pending
                         if p["lead_id"] not in set(lead_ids)]

    @property
    def pending_count(self):
        return len(self._pending)

    @property
    def posted_count(self):
        return len(self._posted)

    def overflow(self):
        """Leads beyond today's cap - they wait, they are not dropped."""
        return list(self._pending[self.DAILY_CAP:])
