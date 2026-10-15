"""How close each campaign's queue is to the cap its readers will walk.

TASK-0150. Pure arithmetic and classification. No provider call, no I/O, no
state. `scripts/queue_wall_check.py` is the entry point that feeds it counts
and prints the answer.

## THE WALL IS NOT ONE NUMBER, IT IS FIVE

`bison.scheduled_emails` refuses a queue past `cap` pages rather than
returning a prefix, and TASK-0130 measured **five distinct effective caps
across eighteen production call sites** for that one endpoint: 40 (the
`bison.PAGE_CAP` default, taken by every site that passes nothing), 80, 200,
400 (`bison.CAMPAIGN_QUEUE_PAGE_CAP`) and caller-supplied.

So "can this campaign's queue be read" has no single answer - it depends on
which code path asked, and the answer can be yes for the watcher and no for
the gate beside it. That is the defect this module makes visible: it assesses
every campaign against every reader's cap, so a campaign readable by one and
invisible to another is a row you can see rather than an inference somebody
has to make twice.

## THE MARGIN IS MEASURED, NOT CHOSEN

A percentage would be arbitrary. The margin here is **one more sequence
step at today's lead count**, because that is the largest discrete jump a
queue can actually take: a sequence change adds a step to every lead at once,
with no lead added.

TASK-0130 measured the five largest campaigns sitting at exactly **two
scheduled rows per lead** - 665/333, 500/250, 446/223, 434/217, 409/206 - so
the step count is derivable from the counts themselves, and a third step puts
503, 504, 505 and 492 all over 600 rows with no lead added. AT-RISK is
therefore not a forecast; it is the arithmetic of an event the operator can
schedule this afternoon.

## WHAT IS NEVER REPORTED

A campaign whose leads or rows are missing is `UNKNOWN`, never OK. Pages
are always DERIVED from rows so there is one authority for the arithmetic,
and a counts file older than the caller's `max_age_days` is REFUSED rather
than reported off - a stale cached provider file reading as current is this
project's own recorded defect, not a hypothetical one.
"""
import datetime
import math

#: Rows the provider puts on one page of this route. Measured, not configured.
PAGE_SIZE = 15

#: The caps TASK-0130 measured in production, named by the reader that takes
#: them, smallest first. `producer` is the one that takes the bare default.
#: These are DESCRIPTIVE of the code as measured on 2026-10-15; a reader whose
#: cap changes has to change here too, which is the point - a wall check that
#: invented its own numbers would answer about a system nobody runs.
READER_CAPS = (
    ("producer-default", 40),
    ("batch1_build", 80),
    ("qa/check_readback", 200),
    ("watcher", 400),
)

OVER = "OVER"
AT_RISK = "AT-RISK"
OK = "OK"
UNKNOWN = "UNKNOWN"

#: OVER and AT-RISK and UNKNOWN all refuse. Only OK passes.
PASSING = (OK,)


def pages(rows):
    """Pages a queue of `rows` takes. One page, even for nothing.

    An empty queue still costs one request to discover that it is empty,
    which is why a pass over twenty campaigns is 205 requests across 202
    pages of rows.
    """
    return max(1, math.ceil(int(rows) / PAGE_SIZE))


def wall_rows(cap):
    """The most rows a reader at `cap` pages can walk."""
    return int(cap) * PAGE_SIZE


def steps_of(leads, rows):
    """Sequence steps implied by the counts, or None when undeterminable.

    Rows per lead, rounded. Not read from the sequence, because the counts
    are what a reader of the queue actually faces and a sequence with a step
    nobody has been enrolled into does not put a row in the queue.
    """
    if not leads or rows is None:
        return None
    ratio = float(rows) / float(leads)
    if ratio <= 0:
        return None
    return max(1, int(round(ratio)))


def leads_of_headroom(leads, rows, cap):
    """Leads this campaign could add before a reader at `cap` refuses it.

    Negative when it is already over. None when the step count cannot be
    derived, because then there is no rows-per-lead to divide by and a number
    here would be invented.
    """
    steps = steps_of(leads, rows)
    if steps is None:
        return None
    return int(wall_rows(cap) / steps) - int(leads)


def survives_one_more_step(leads, rows, cap):
    """Would this queue still be readable with one more sequence step?

    `(steps + 1) / steps` of today's rows, at today's lead count. None when
    the step count cannot be derived.
    """
    steps = steps_of(leads, rows)
    if steps is None:
        return None
    projected = int(math.ceil(int(rows) * (steps + 1) / steps))
    return pages(projected) <= int(cap), projected


def assess_one(campaign_id, leads, rows, cap):
    """One campaign against one cap.

    UNKNOWN when rows is missing: a campaign whose queue size nobody knows is
    not a campaign that fits. A campaign with 0 rows and no leads is OK and
    says so - there is nothing to walk and nothing to grow.
    """
    out = {"campaign_id": campaign_id, "leads": leads, "rows": rows,
           "cap": int(cap), "wall_rows": wall_rows(cap)}
    if rows is None:
        out.update({"verdict": UNKNOWN, "pages": None, "steps": None,
                    "leads_of_headroom": None, "projected_rows": None,
                    "why": "no row count; the queue size is not known"})
        return out
    out["pages"] = pages(rows)
    out["steps"] = steps_of(leads, rows)
    out["leads_of_headroom"] = leads_of_headroom(leads, rows, cap)
    survives = survives_one_more_step(leads, rows, cap)
    out["projected_rows"] = None if survives is None else survives[1]
    if out["pages"] > int(cap):
        out["verdict"] = OVER
        out["why"] = (f"{rows} rows is {out['pages']} pages and this reader "
                      f"stops at {cap}; it cannot read this queue at all")
    elif not rows:
        out["verdict"] = OK
        out["why"] = "empty queue; one request to discover that"
    elif survives is None:
        out["verdict"] = UNKNOWN
        out["why"] = (f"{rows} rows fit today, but with {leads!r} leads the "
                      f"rows-per-lead cannot be derived, so the next "
                      f"sequence step cannot be projected")
    elif not survives[0]:
        out["verdict"] = AT_RISK
        out["why"] = (f"{rows} rows fit today, but one more sequence step at "
                      f"{leads} leads is {survives[1]} rows - "
                      f"{pages(survives[1])} pages - and this reader stops "
                      f"at {cap}")
    else:
        out["verdict"] = OK
        out["why"] = (f"{out['pages']} of {cap} pages, {out['steps']} step(s) "
                      f"at {leads} leads; survives one more step "
                      f"({survives[1]} rows) and {out['leads_of_headroom']} "
                      f"more leads")
    return out


def _age_days(measured_at, now):
    stamp = datetime.datetime.fromisoformat(
        str(measured_at).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    return (now - stamp).total_seconds() / 86400.0


def assess(counts, now=None, max_age_days=7, reader_caps=READER_CAPS):
    """Every campaign against every reader's cap, plus one refusal.

    `counts` is `{"measured_at": iso, "campaigns": [{campaign_id, leads,
    rows}, ...]}`. `refused` is True when ANY campaign is OVER, AT-RISK or
    UNKNOWN for ANY reader, or when the counts are older than
    `max_age_days` - in which case nothing is assessed at all, because a
    stale measurement must not be reported as a current one.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    age = _age_days(counts.get("measured_at"), now)
    out = {"measured_at": counts.get("measured_at"),
           "age_days": round(age, 2), "max_age_days": max_age_days,
           "readers": [name for name, _cap in reader_caps],
           "stale": age > max_age_days, "by_reader": {}, "campaigns": [],
           "total_rows": 0, "total_row_pages": 0, "requests_per_pass": 0}
    if out["stale"]:
        out["refused"] = True
        out["why"] = (f"the counts are {age:.2f} days old and the limit is "
                      f"{max_age_days}; refusing to assess a queue wall off a "
                      f"stale measurement")
        return out

    rows_total = row_pages = requests = 0
    for entry in counts.get("campaigns") or []:
        rows = entry.get("rows")
        leads = entry.get("leads")
        per_reader = {name: assess_one(entry.get("campaign_id"), leads, rows,
                                      cap)
                      for name, cap in reader_caps}
        worst = UNKNOWN
        for name, _cap in reader_caps:
            v = per_reader[name]["verdict"]
            if v == OVER:
                worst = OVER
                break
            if v == AT_RISK and worst != OVER:
                worst = AT_RISK
            elif v == UNKNOWN and worst not in (OVER, AT_RISK):
                worst = UNKNOWN
            elif v == OK and worst == UNKNOWN:
                worst = OK
        readable_by = [name for name, _cap in reader_caps
                       if per_reader[name]["verdict"] != OVER]
        out["campaigns"].append({
            "campaign_id": entry.get("campaign_id"),
            "status": entry.get("status"),
            "leads": leads, "rows": rows,
            "pages": None if rows is None else pages(rows),
            "steps": steps_of(leads, rows),
            "worst_verdict": worst,
            "readable_by": readable_by,
            "invisible_to": [name for name, _cap in reader_caps
                             if name not in readable_by],
            "by_reader": per_reader})
        if rows is not None:
            rows_total += int(rows)
            row_pages += 0 if not rows else pages(rows)
            requests += pages(rows)
    out["total_rows"] = rows_total
    out["total_row_pages"] = row_pages
    out["requests_per_pass"] = requests
    for name, cap in reader_caps:
        verdicts = [c["by_reader"][name]["verdict"] for c in out["campaigns"]]
        out["by_reader"][name] = {
            "cap": cap, "wall_rows": wall_rows(cap),
            "over": [c["campaign_id"] for c in out["campaigns"]
                     if c["by_reader"][name]["verdict"] == OVER],
            "at_risk": [c["campaign_id"] for c in out["campaigns"]
                        if c["by_reader"][name]["verdict"] == AT_RISK],
            "unknown": [c["campaign_id"] for c in out["campaigns"]
                        if c["by_reader"][name]["verdict"] == UNKNOWN],
            "ok": verdicts.count(OK)}

    bad = [c for c in out["campaigns"] if c["worst_verdict"] not in PASSING]
    out["refused"] = bool(bad)
    out["why"] = _why(out, bad)
    return out


def _why(result, bad):
    """One sentence. This is what a tired person reads at a glance."""
    if not bad:
        return (f"QUEUE WALL: all {len(result['campaigns'])} campaigns fit "
                f"every reader's cap and all survive one more sequence step "
                f"({result['total_rows']} rows, "
                f"{result['requests_per_pass']} requests a pass).")
    over = sorted({c["campaign_id"] for c in bad
                   if c["worst_verdict"] == OVER})
    risk = sorted({c["campaign_id"] for c in bad
                   if c["worst_verdict"] == AT_RISK})
    unk = sorted({c["campaign_id"] for c in bad
                  if c["worst_verdict"] == UNKNOWN})
    parts = []
    if over:
        parts.append(f"{len(over)} OVER ({', '.join(str(c) for c in over)})")
    if risk:
        parts.append(f"{len(risk)} AT-RISK on one more sequence step "
                     f"({', '.join(str(c) for c in risk)})")
    if unk:
        parts.append(f"{len(unk)} UNKNOWN ({', '.join(str(c) for c in unk)})")
    return (f"QUEUE WALL REFUSES: {'; '.join(parts)} of "
            f"{len(result['campaigns'])} campaigns - a queue past a reader's "
            f"cap is not read in part, it is not read at all.")
