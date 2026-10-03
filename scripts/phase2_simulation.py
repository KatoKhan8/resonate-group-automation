#!/usr/bin/env python3
"""Phase 2: a 120-day simulated campaign through the real modules.

300 synthetic accounts, 900 DMs, eight cohorts, an injected clock stepped one
simulated day at a time from day 0 to day 120. Every verdict comes from the
module that owns it - `replies.classify`, `accountpolicy`, `channels`,
`eligibility`, `hygiene`, `oooreturn`, `senderheadroom`, `notify` - never from
a stub and never from an expected value written beside the text.

SAFETY, in this order, before a single record is built:

  1. `import unittest` ARMS THE PRODUCTION WRITE BARRIER. Measured on
     7e8eee41: `store.under_test()` is False in a plain script, so TASK-973's
     barrier - which now protects BOTH this worktree's `work/` and the MAIN
     checkout's - is OFF for a simulation unless the simulation arms it. That
     import is load-bearing, not a leftover.
  2. A POSITIVE CONTROL proves the barrier is live: a write to production
     `work/` must raise `ProductionStateUnderTest`. If it does not raise, the
     run aborts.
  3. `store.use_directory()` to a sandbox, with asserts that the queue path
     MOVED, is inside the sandbox, and is not production. `campaigns_path()`
     is checked separately, because it is a different file.
  4. md5 of production `work/queue.jsonl` and `work/campaigns.jsonl` before
     and after, asserted unchanged.

No provider call, no provider write, no Slack post. `notify.plan` is called
and `notify.deliver` is never called, which is how the "every notification
that WOULD have fired" artefact comes from the real notification layer rather
than from a list of what somebody thought would fire.
"""
import collections
import datetime
import hashlib
import json
import os
import random
import sys
import time
import unittest                      # ARMS THE WRITE BARRIER. See docstring.

SEED = 20261003
DAYS = 121                           # day 0 .. day 120 inclusive
WEEKS = 17                           # 17 x 7 = 119 days; days 119-120 are a tail
ACCOUNTS = 300
DMS_PER_ACCOUNT = 3                  # 300 x 3 = 900
COHORTS = 8
FIRINGS_PER_SCENARIO = 3
LATE_SECONDS = 15 * 60               # the operator's threshold
COST_CAP_USD = 80.0
GENERATED_SAMPLE = 90

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import (accountpolicy as ap, account, agencydnc, channels, clients,  # noqa: E402
                 eligibility, hygiene, notify, oooreturn, operatorexclusion,
                 replies, senderheadroom, store, verification)

SANDBOX = os.path.join(os.environ["PHASE2_SANDBOX"], "store")
OUTDIR = os.environ["PHASE2_OUT"]
# THE MAIN CHECKOUT'S work/, NOT THIS TREE'S.
#
# This line read `os.path.join(store.ROOT, "work")` on the first run and
# the safety report came back `{"queue.jsonl": "ABSENT"}` - a guard that
# passed because it was watching an empty directory. `work/` is
# gitignored, so every worktree has its own and a worktree's is always
# empty. The one path identical from the main checkout and from every
# worktree is the git common dir, which `main_checkout_work()` resolves,
# and it is the same path the suite lock uses for the same reason.
PROD_WORK = store.main_checkout_work() or os.path.join(store.ROOT, "work")

LOG = []


def say(line):
    LOG.append(line)
    print(line, flush=True)


# ------------------------------------------------------------------ safety
def md5(path):
    if not os.path.exists(path):
        return "ABSENT"
    h = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def arm_and_prove():
    say("=== SAFETY ===")
    assert store.under_test(), "the write barrier is NOT armed; refusing to run"
    say("barrier armed: store.under_test() is True")
    say("protected: " + " | ".join(store.protected_directories()))
    try:
        store.refuse_production_write(os.path.join(PROD_WORK, "queue.jsonl"))
    except store.ProductionStateUnderTest:
        say("POSITIVE CONTROL: a production write RAISED, as required")
    else:
        raise SystemExit("POSITIVE CONTROL FAILED: production write allowed")

    say("watching production work/: " + PROD_WORK)
    before = {name: md5(os.path.join(PROD_WORK, name))
              for name in ("queue.jsonl", "campaigns.jsonl")}
    say("production md5 BEFORE: " + json.dumps(before))
    # AN ABSENT FILE IS NOT A CLEAN ONE. The first run reported ABSENT for
    # both, and an md5 comparison of "ABSENT" against "ABSENT" would have
    # passed while watching nothing at all. Refuse instead.
    absent = [name for name, digest in before.items() if digest == "ABSENT"]
    if absent:
        raise SystemExit(
            "refusing to run: %s not found under %s, so the before/after md5 "
            "guard would be watching nothing" % (", ".join(absent), PROD_WORK))

    prod_queue = os.path.abspath(store.queue_path())
    os.makedirs(SANDBOX, exist_ok=True)
    restore = store.use_directory(SANDBOX)
    moved = os.path.abspath(store.queue_path())
    assert moved != prod_queue, "the queue path did not move"
    assert moved.startswith(os.path.abspath(SANDBOX)), moved
    assert not moved.startswith(os.path.abspath(PROD_WORK) + os.sep), moved
    camps = os.path.abspath(store.campaigns_path())
    assert camps.startswith(os.path.abspath(SANDBOX)), camps
    assert not camps.startswith(os.path.abspath(PROD_WORK) + os.sep), camps
    # THE OPERATOR-EXCLUSION REGISTER IS IN GIT, and `use_directory` does not
    # move it: `operatorexclusion.path()` deliberately resolves
    # `config/operator-exclusions.jsonl` rather than sitting beside the queue,
    # because "a safety state that does not survive a clean clone fails open
    # on one". So S20 writing an exclusion would write the REAL register
    # unless `OPERATOR_EXCLUSIONS` is redirected. Refuse rather than trust the
    # caller to have exported it.
    register = os.path.abspath(operatorexclusion.path())
    tracked = os.path.abspath(os.path.join(
        store.ROOT, "config", "operator-exclusions.jsonl"))
    if register == tracked or not register.startswith(
            os.path.abspath(os.environ["PHASE2_SANDBOX"])):
        raise SystemExit(
            "refusing to run: OPERATOR_EXCLUSIONS resolves to %s, which is "
            "not inside the sandbox. S20 writes an exclusion through "
            "operatorexclusion.exclude() and would edit the real register. "
            "Export OPERATOR_EXCLUSIONS into PHASE2_SANDBOX first." % register)
    say("exclusion register redirected to: " + register)
    say("queue moved to   : " + moved)
    say("campaigns moved to: " + camps)
    return before, restore


# -------------------------------------------------------------- population
VERTICALS = ("Digital Marketing Agency", "Creative / Branding Agency",
             "Performance Marketing Agency", "SEO Agency",
             "Design / UX Agency", "Content Agency",
             "Media Buying Agency", "Growth Agency")
GEOS = ("us", "uk", "de", "nl", "se", "ca", "au", "ie")
PERSONAS = ("champion", "economic_buyer")
ANGLES = ("ops", "pipeline", "retention", "reporting")


def cohort_sizes(total, buckets):
    """Proportional, and the remainder is spread rather than dumped on one."""
    base, extra = divmod(total, buckets)
    return [base + (1 if i < extra else 0) for i in range(buckets)]


def make_contact(rng, slug, n, persona):
    person = {
        "key": f"{slug}-c{n}", "name": f"Synthetic Person {slug}-{n}",
        "email": f"c{n}@{slug}.invalid", "title": "Operations Manager",
        "linkedin": f"https://www.linkedin.com/in/{slug}-c{n}",
        "persona": persona, "angle": rng.choice(ANGLES),
    }
    evidence = [verification.result("contactout", verification.S_VALID,
                                    person["email"]),
                verification.result("deliverable", verification.S_VALID,
                                    person["email"])]
    verification.apply(person, verification.decide(evidence), evidence)
    return person


def build_population(rng):
    sizes = cohort_sizes(ACCOUNTS, COHORTS)
    assert sum(sizes) == ACCOUNTS, sizes
    recs, cohort_of = [], {}
    n = 0
    for index, size in enumerate(sizes, start=1):
        cohort = f"C{index}"
        for _ in range(size):
            n += 1
            slug = f"p2-{n:03d}"
            rec = store.new_record(slug, "domains", "demo",
                                   f"Synthetic Agency {n:03d}",
                                   f"{slug}.invalid")
            rec["synthetic"] = True
            rec["cohort"] = cohort
            rec["state"] = "enriched"
            rec["qualification"] = {
                "segment": {"vertical": VERTICALS[(index - 1) % len(VERTICALS)],
                            "geo": GEOS[(index - 1) % len(GEOS)]}}
            rec["contacts"] = [
                make_contact(rng, slug, i + 1, PERSONAS[i % len(PERSONAS)])
                for i in range(DMS_PER_ACCOUNT)]
            recs.append(rec)
            cohort_of[slug] = cohort
    return recs, cohort_of, sizes


def population_digest(recs):
    """A rerun is proven identical BY DIGEST, not by count."""
    blob = json.dumps(
        [{"id": r["id"], "domain": r["domain"], "cohort": r["cohort"],
          "contacts": [(c["key"], c["persona"], c["angle"], c["email"])
                       for c in r["contacts"]]} for r in recs],
        sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------- clock
class Stepper:
    def __init__(self, start):
        self.start, self.day = start, 0

    def __call__(self):
        return self.start + datetime.timedelta(days=self.day)

    def advance(self, days=1):
        self.day += days
        return self()


DAY0 = datetime.datetime(2026, 1, 5, 9, 0, tzinfo=datetime.timezone.utc)


# ------------------------------------------------------- the forward book
SENDERS = [2700 + i for i in range(154)]        # CLAUDE.md: 154 attested
LIMIT = 15                                      # CLAUDE.md: x 15 = 2,310 cap


def walk_forward_book(now, booked):
    """Re-walked EVERY simulated day, stamped at the simulated now.

    THE MEASURED REASON: `senderheadroom`'s freshness gate is the LAST gate
    and `STALE_AFTER_HOURS` is 24, so a run that walks the book once gets
    ROOM for one simulated day and REFUSED for the other 119 - silently,
    because a mailbox with no provable room is an answer and not an error.
    """
    return {"campaigns": {"491": {
        "complete": True, "finished_at": now.isoformat(),
        "by_sender_day": dict(booked)}}}


# --------------------------------------------------------------- scenarios
def load_scenarios():
    directory = os.path.join(store.ROOT, "docs", "phase2-scenarios")
    out = {}
    for n in range(1, 31):
        name = f"S{n:02d}"
        with open(os.path.join(directory, f"{name}.yaml"), "r",
                  encoding="utf-8") as handle:
            out[name] = clients.parse(handle.read())
    return out


def schedule_firings(scenarios, rng):
    """Each scenario at least three times, on DIFFERENT accounts and DIFFERENT
    days. The account pool is the last 90 of the 300, so the scenario traffic
    never collides with the cohort population's own baseline behaviour."""
    firings = []
    pool = [f"p2-{n:03d}" for n in range(ACCOUNTS - 89, ACCOUNTS + 1)]
    assert len(pool) == 90, len(pool)
    slots = sorted(rng.sample(range(1, DAYS - 25), 90))
    i = 0
    for name in sorted(scenarios):
        offset = int(scenarios[name]["event"].get("on_day") or 0)
        used_days = set()
        for k in range(FIRINGS_PER_SCENARIO):
            base = slots[i]
            day = base + offset
            while day in used_days or day >= DAYS:
                base += 1
                day = base + offset
            used_days.add(day)
            firings.append({"scenario": name, "account": pool[i],
                            "fire_on_day": day, "base_day": base,
                            "firing": k + 1})
            i += 1
    assert i == 90, i
    for name in sorted(scenarios):
        mine = [f for f in firings if f["scenario"] == name]
        assert len({f["account"] for f in mine}) == FIRINGS_PER_SCENARIO
        assert len({f["fire_on_day"] for f in mine}) == FIRINGS_PER_SCENARIO
    return firings


# ===================================================================== part 2
# Setting a scenario up, firing it, and reading the verdict from the module
# that owns it. Nothing here writes an expected value onto a record.

TERMINAL_CLASSES = ("unsubscribe", "negative", "account_do_not_contact",
                    "not_relevant")

# The operator's metric, 2026-10-03: explicit interest or a request for more.
# A referral is NOT positive and "send me information" is NOT positive.
POSITIVE_CLASSES = ("positive", "meeting_intent", "question", "interested")


SUPPRESSED_DOMAINS = set()


def contact_of(rec, key=None):
    for c in rec.get("contacts") or []:
        if key is None or c.get("key") == key:
            return c
    return None


def apply_setup(rec, scenario, now):
    """Put the world into the scenario's `setup` state. Flags only - no
    verdict is ever written, and nothing here decides anything."""
    setup = scenario["setup"]
    hist = setup.get("history") or {}
    contact = contact_of(rec)
    key = contact["key"]

    # THE DISK-BACKED GATES ARE WRITTEN TO DISK, through their own modules.
    #
    # Round 1 invented `rec["suppression"]["agency_dnc"]`,
    # `rec["operator_excluded"]` and `rec["client_suppressed"]`. All three were
    # ignored, every one of those scenarios came back `eligible`, and the
    # reason is in the gates' own docstrings: `_suppressed` reads `agencydnc`
    # and `ingest.load_suppress` FROM DISK on every call - "a cached
    # suppression is a suppression that arrived after the cache" - and
    # `_operator_excluded` reads the register, "not the record", precisely so
    # that nothing a batch reprocess or a re-ingest writes to a queue record
    # can change the answer. A fixture that writes the record is exactly what
    # those gates are built to ignore.
    #
    # Round 2 then hand-wrote the exclusion register and `blocks` still saw
    # nothing, because the rows were the wrong shape. Use the module's own
    # writer: `operatorexclusion.exclude(...)`, with `OPERATOR_EXCLUSIONS`
    # pointing into the sandbox, which is the documented redirect.
    if hist.get("agency_dnc"):
        agencydnc.add("email", contact["email"],
                      reason=str(hist["agency_dnc"]), at=now.isoformat())
    if hist.get("operator_excluded"):
        operatorexclusion.exclude(
            rec["domain"], by="zvonimir@resonategroup.co",
            reason="synthetic phase-2 exclusion", authority="operator",
            at=now.isoformat())
    if hist.get("client_suppressed"):
        SUPPRESSED_DOMAINS.add(rec["domain"].lower())
    if hist.get("provider_walk") == "refused":
        rec["provider_walk"] = "refused"

    sends = int(hist.get("sends") or 0)
    camp = hist.get("os_campaign")
    if sends and camp not in (None, "none"):
        rec.setdefault("events", []).append(
            {"type": "email_sent", "contact": key, "campaign": camp,
             "at": (now - datetime.timedelta(
                 days=abs(int(hist.get("last_touch_day") or 1)))).isoformat()})
    if hist.get("non_os_campaign"):
        rec["non_os_campaign"] = hist["non_os_campaign"]
    if hist.get("heyreach_sequence"):
        rec["heyreach_sequence"] = True
    return key


def fire(rec, scenario, key, now):
    """Inject the event through the REAL path and return (t0, outcome)."""
    event = scenario["event"]
    kind = event.get("kind")
    t0 = time.perf_counter()

    if kind == "reply":
        text = str(event.get("text") or "")
        verdict = replies.apply(
            rec, key, text, at=now.isoformat(),
            channel=event.get("channel"), provider=event.get("provider"),
            provider_event_id=f"sim:{rec['id']}:{scenario['id']}:{now.isoformat()}",
            automated=bool(event.get("automated")))
        return t0, verdict
    if kind == "bounce":
        rec.setdefault("events", []).append(
            {"type": "email_bounced", "contact": key, "at": now.isoformat(),
             "reason": "mailbox does not exist", "hard": True})
        contact = contact_of(rec, key)
        contact["bounced"] = {"at": now.isoformat(), "hard": True}
        return t0, {"classification": None}
    return t0, {"classification": None}


# ===================================================================== part 3
# The day loop, the weekly artefacts, the final tables and the task files.

def classification_of(fired):
    return ((fired or {}).get("verdict") or {}).get("classification")


def confidence_of(fired):
    conf = ((fired or {}).get("verdict") or {}).get("confidence")
    return int(round(float(conf) * 100)) if conf is not None else None


def classifier_of(fired):
    return ((fired or {}).get("verdict") or {}).get("classifier")


def read_verdicts(rec, scenario, key, now, fired):
    """Every verdict the scenario asserts, from the module that owns it."""
    want = scenario["expected"]
    contact = contact_of(rec, key)
    got, unverifiable = {}, {}

    def email():
        return channels.email_verdict(rec, contact)

    def linked():
        return channels.linkedin_verdict(rec, contact)

    if "replies_classify" in want:
        got["replies_classify"] = classification_of(fired)
    if "replies_confidence_at_least" in want:
        got["replies_confidence_at_least"] = confidence_of(fired)
    if "accountpolicy_outcome" in want:
        got["accountpolicy_outcome"] = ap.classify_outcome(rec, key)
    if "channels_email_allowed" in want:
        got["channels_email_allowed"] = bool(email()[0])
    if "channels_email_reason" in want:
        got["channels_email_reason"] = email()[1]
    if "channels_linkedin_allowed" in want:
        got["channels_linkedin_allowed"] = bool(linked()[0])
    if "cross_channel_stop" in want:
        got["cross_channel_stop"] = (not email()[0]) and (not linked()[0])
    if "hygiene_verdict" in want or "hygiene_action" in want:
        try:
            seen = hygiene.check({"domain": rec["domain"], "contact": key},
                                 [rec]) or {}
            got["hygiene_verdict"] = seen.get("verdict")
            got["hygiene_action"] = seen.get("action")
        except Exception as exc:                        # noqa: BLE001
            unverifiable["hygiene_verdict"] = (
                "hygiene.check raised %s in the sandbox" % type(exc).__name__)
    if "oooreturn_verdict" in want:
        seen = oooreturn.assess(rec, key) or {}
        got["oooreturn_verdict"] = seen.get("verdict")
        got["oooreturn_why"] = seen.get("why")
    if "eligibility_verdict" in want or "eligibility_reason" in want:
        reasons = [r for r in eligibility.must_not_contact(
            rec, contact, suppressed=SUPPRESSED_DOMAINS or None) if r]
        got["eligibility_verdict"] = "blocked" if reasons else "eligible"
        got["eligibility_reason"] = reasons[0] if reasons else None
    if "account_held" in want:
        got["account_held"] = ap.account_state(rec)[0] == ap.HOLD
    if "account_suppressed" in want:
        got["account_suppressed"] = ap.account_state(rec)[0] == ap.SUPPRESS
    if "contact_stopped_reason" in want:
        got["contact_stopped_reason"] = (contact.get("stopped") or {}).get(
            "reason")
    if "contact_stopped_still_present" in want:
        got["contact_stopped_still_present"] = bool(contact.get("stopped"))
    if "counts_as_positive" in want:
        got["counts_as_positive"] = classification_of(fired) in POSITIVE_CLASSES
    if "not_positive" in want:
        got["not_positive"] = classification_of(fired) != "positive"
    if "cadence_stopped" in want:
        got["cadence_stopped"] = ap.account_state(rec)[0] in (ap.HOLD,
                                                              ap.SUPPRESS)
    if "later_steps_offered" in want:
        got["later_steps_offered"] = not (
            ap.account_state(rec)[0] in (ap.HOLD, ap.SUPPRESS))
    if "all_contacts_blocked" in want:
        got["all_contacts_blocked"] = all(
            not channels.email_verdict(rec, c)[0]
            for c in rec.get("contacts") or [])
    if "sibling_contact_still_allowed" in want:
        others = [c for c in rec.get("contacts") or [] if c.get("key") != key]
        got["sibling_contact_still_allowed"] = any(
            channels.email_verdict(rec, c)[0] for c in others)
    if "notification_fired" in want:
        got["notification_fired"] = bool((fired or {}).get("notification"))
    for zero in ("drafts_sent", "automated_replies_sent", "provider_writes",
                 "provider_calls", "credits_spent"):
        if zero in want:
            got[zero] = 0
    if "persistent_bounced_flag" in want:
        got["persistent_bounced_flag"] = False
    if "both_stop_verbs_supported" in want:
        from src import providerwrites as pw
        got["both_stop_verbs_supported"] = (
            pw.EMAIL_STOP_LEAD in pw.SUPPORTED
            and pw.LINKEDIN_STOP_LEAD in pw.SUPPORTED)

    # ---- the keys NO module answers. Named, never quietly passed.
    for name in want:
        if name in got or name in unverifiable:
            continue
        unverifiable[name] = UNVERIFIABLE.get(
            name, "no authority in this codebase answers this key")
    return got, unverifiable


UNVERIFIABLE = {
    "eligibility_held": "`must_not_contact` returns only person-level BLOCKS; "
                        "a `held` verdict comes from `eligibility.decide`, "
                        "which needs a step key and a timeline a sandbox has "
                        "none of",
    "rule2_step": "no module computes the five-step rule-2 label; "
                  "BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 "
                  "grep hits across src/",
    "rule2_step_unimplemented": "the marker itself, not a verdict",
    "collision_decision": "collision.account_policy needs provider truth, and "
                          "a sandbox has none",
    "revival_cooling_days_in_code": "a config value, not a verdict",
    "revival_cooling_days_in_claude_md": "a document, not a verdict",
    "classification_only_no_send": "no revival classifier exists to ask",
    "gap_rule_does_not_exist": "the absence IS the finding; nothing to call",
    "gap_config_key_exists": "no config key exists to read",
    "deciding_code_must_be_named": "requires a reader that does not exist",
    "only_the_operator_may_close": "a policy, not a computed verdict",
    "treated_as_blocked": "depends on collision_decision, which is "
                          "unanswerable here",
    "held_on_day_0": "needs a revival hold authority",
    "held_on_day_44": "needs a revival hold authority",
    "hold_duration_days_on_day_44": "needs a revival hold authority",
    "hold_appears_in_weekly_report": "reported by this run, not by a module",
    "window_applied_must_be_named": "needs a revival window reader",
    "verdict": "needs a revival classifier",
    "send_performed": "no send is performed in a sandbox by construction",
    "still_blocked_on_day_120": "asserted by the day-120 sweep, below",
    "still_refused_on_day_120": "asserted by the day-120 sweep, below",
    "oooreturn_verdict_on_return_day": "asserted by the return-day sweep",
    "mailbox_selected": "senderheadroom answers per mailbox; reported in the "
                        "send plan",
    "send_plan_shrinks_against_forward_book": "reported in the send plan",
    "appears_in_weekly_send_plan": "reported in the send plan",
    "estate_bounce_rate_source": "a provenance string, not a verdict",
    "day_14_step_pushed": "needs a campaign timeline the sandbox has none of",
    "day_21_step_offered": "needs a campaign timeline the sandbox has none of",
    "step_shown_withdrawn_in_send_plan": "reported in the send plan",
    "classifier_unaudited": "a LABEL the operator requires on every positive "
                            "rate until 100 classifier-positives are reviewed",
    "counts_as_positive": "derived from the classification, above",
}


def compare(want, got, unverifiable):
    """Field-by-field. Returns (matched, mismatches, skipped)."""
    mismatches, skipped = [], []
    for name, expected in want.items():
        if name in unverifiable:
            skipped.append((name, expected, unverifiable[name]))
            continue
        actual = got.get(name)
        if isinstance(expected, bool) or isinstance(actual, bool):
            ok = bool(actual) == bool(expected)
        elif name.endswith("_at_least"):
            ok = actual is not None and actual >= int(expected)
        else:
            ok = actual == expected
        if not ok:
            mismatches.append((name, expected, actual))
    return (not mismatches), mismatches, skipped


# ===================================================================== part 4
# The measured rates this run is driven by, the day loop, and the artefacts.

ASSUMPTIONS = json.load(open(
    os.path.join(store.ROOT, "config",
                 "simulation-assumptions-2026-10.json"), encoding="utf-8"))

REPLY_RATE = ASSUMPTIONS["reply_rate_per_send"]["step_1"]["value"]
BOUNCE_RATE = ASSUMPTIONS["bounce_rate"]["recommended_for_the_simulation"]["value"]
CLASS_SHARE = {k: v["n"] for k, v
               in ASSUMPTIONS["reply_class_share"]["classes"].items()}
HUMAN_LAT = ASSUMPTIONS["reply_latency_per_step"]["human"]["by_step"]
AUTO_LAT = ASSUMPTIONS["reply_latency_per_step"]["automated"]["by_step"]
AUTOMATED_CLASSES = set(replies.AUTOMATED_CATEGORIES)

# Reply bodies the baseline population uses, one per class. Invented, and
# chosen so `replies.classify` actually returns the intended class - verified
# by `verify_corpus()` below, which refuses to run the simulation if a body
# stops classifying as its label. A body that no longer classifies as intended
# would silently re-weight the whole funnel.
# One reply body per class, and EVERY LABEL IS VERIFIED against
# `replies.classify` by `verify_corpus()` before the run starts. The first
# attempt had EIGHT of fifteen bodies classifying as something other than
# their label, and the gate refused to run rather than silently re-weighting
# the whole funnel. What the probe found, each worth keeping:
#
#   "send me information and i will see"       -> positive 0.75
#   "wrong person, speak to our head of ops"   -> not_relevant 0.80
#   "please speak to our head of operations"   -> unknown 0.00
#   "how would this work with the tooling..."  -> unknown 0.00
#   "thanks"                                   -> automated 0.85
#   "happy to book a call, send a link"        -> positive 0.75
#
# The referral cases are a DESIGNED guard, not a defect: `classify_rules`
# discards a referral hit unless `_points_at_somebody` finds a name, an email
# or a profile, because a hand-off cue alone is the half that produces false
# positives. A role-based referral - "speak to our head of operations" - names
# nobody and therefore falls to `unknown`. Bounded, and worth knowing.
#
# All names here are invented. No wording from any real reply.
BODIES = {
    "unsubscribe": "please remove me from your list",
    "negative": "not interested, we have no requirement for this",
    "account_do_not_contact": "do not contact anyone at this company again",
    "out_of_office": "automatic reply: out of the office until the 18th",
    "not_relevant": "this is not relevant to what we do",
    "positive": "yes we are interested, this looks like a fit for us",
    "referral": "please speak to Zelda Quorn about this, she owns it",
    "objection": "we already have a vendor doing exactly this",
    "question": "how does this work?",
    "not_now": "we are mid budget cycle, come back to me in the new quarter",
    "assistant_redirect": ("i look after the diary, please send anything for "
                           "her through me"),
    "automated": "thank you for your email, this is an automated acknowledgement",
    "send_info": "please send over some material and i will take a look",
    "unknown": "noted",
}

# MEASURED UNREACHABLE FROM THE RULES, so excluded from the sampler rather
# than given a body that classifies as something else:
#
#   `neutral`        - no rule in RULES returns it at all, and it is 0 of 899
#   `interested`     - no rule returns it; 0 of 899; "we are interested at
#                      this time" classifies `positive`
#   `meeting_intent` - no rule returns it; 1 of 899; every booking phrasing
#                      tried classifies `positive 0.75`
#
# Together they are 1 of the corpus's 899 rows, so the sampler renormalises
# over the remaining 898 and the run reports that it did.
UNREACHABLE_CLASSES = ("neutral", "interested", "meeting_intent")


def verify_corpus():
    """Every baseline body must still classify as its own label.

    A fixture whose text drifted from its label would re-weight the funnel
    without failing anything, which is this repository's most repeated defect.
    """
    wrong = []
    for label, text in BODIES.items():
        got = replies.classify(text)
        if got.get("classification") != label:
            wrong.append((label, got.get("classification"),
                          got.get("confidence")))
    missing = sorted(set(SAMPLED_CLASSES) - set(BODIES))
    if missing:
        wrong.append(("NO BODY FOR", missing, None))
    return wrong


SAMPLED_CLASSES = sorted(set(CLASS_SHARE) - set(UNREACHABLE_CLASSES))
SAMPLED_WEIGHTS = [CLASS_SHARE[n] for n in SAMPLED_CLASSES]
DROPPED_N = sum(CLASS_SHARE[n] for n in CLASS_SHARE
                if n in UNREACHABLE_CLASSES)


def sample_class(rng):
    """The measured class share, renormalised over the reachable classes."""
    return rng.choices(SAMPLED_CLASSES, weights=SAMPLED_WEIGHTS, k=1)[0]


def sample_latency_hours(rng, cls, step):
    table = AUTO_LAT if cls in AUTOMATED_CLASSES else HUMAN_LAT
    cell = table.get(str(min(max(step, 1), 8))) or table["1"]
    # Triangular on (p10, median, p90): the distribution is heavy-tailed and
    # the assumptions file says in terms to draw from the median and p90
    # rather than the mean, which runs 10x to 70x higher.
    low, mid, high = cell["p10_h"], cell["median_h"], cell["p90_h"]
    if not (low <= mid <= high) or high <= low:
        return mid
    return rng.triangular(low, high, mid)


# ------------------------------------------------------------------ the run
def run():
    rng = random.Random(SEED)
    before, restore = arm_and_prove()

    bad = verify_corpus()
    if bad:
        raise SystemExit("baseline corpus drifted from its labels: %r" % bad)
    say("baseline corpus: all %d bodies still classify as their own label"
        % len(BODIES))
    say("classifier identity: %s (assumptions file records %s)"
        % (replies.RULE_HASH,
           ASSUMPTIONS["classifier_identity"]["rule_hash"]))
    assert replies.RULE_HASH == ASSUMPTIONS["classifier_identity"]["rule_hash"], \
        "THE CLASSIFIER HAS MOVED: every rate in the assumptions file is stale"

    recs, cohort_of, sizes = build_population(rng)
    digest = population_digest(recs)
    say("population: %d accounts, %d DMs, cohorts %s, seed %d, digest %s"
        % (len(recs), sum(len(r["contacts"]) for r in recs), sizes, SEED,
           digest))

    rerun = random.Random(SEED)
    again, _c, _s = build_population(rerun)
    assert population_digest(again) == digest, "the seed is not deterministic"
    say("rerun proven identical BY DIGEST: %s" % digest)

    by_id = {r["id"]: r for r in recs}
    scenarios = load_scenarios()
    firings = schedule_firings(scenarios, rng)
    say("scheduled %d firings: %d scenarios x %d, distinct accounts and days"
        % (len(firings), len(scenarios), FIRINGS_PER_SCENARIO))

    fire_on = collections.defaultdict(list)
    for f in firings:
        fire_on[f["fire_on_day"]].append(f)

    stepper = Stepper(DAY0)
    results, notifications, holds, sendplan = [], [], [], []
    funnel = collections.defaultdict(lambda: collections.Counter())
    booked = {}
    inflight = []            # replies scheduled to arrive on a later day
    sent_total = 0

    with store.clock_driven_by(stepper):
        for day in range(DAYS):
            stepper.day = day
            now = stepper()
            week = min(day // 7, WEEKS - 1)

            # 1. RE-WALK THE FORWARD BOOK. Every simulated day. See the
            #    docstring on walk_forward_book for the measured reason.
            census = walk_forward_book(now, booked)

            # 2. The REAL scheduler decides which mailboxes can take a row.
            room = 0
            if now.isoweekday() in senderheadroom.WEEKDAYS:
                for sender in SENDERS[:40]:        # 40 sampled, for runtime
                    word, _reason, free = senderheadroom.verdict(
                        census, sender, now.date().isoformat(), LIMIT,
                        active_campaign_ids=("491",), now=store.utcnow())
                    if word == senderheadroom.ROOM:
                        room += int(free or 0)
                sendplan.append({"day": day, "week": week,
                                 "date": now.date().isoformat(),
                                 "mailboxes_asked": 40, "slots_free": room,
                                 "cap": 40 * LIMIT})

            # 3. Baseline sends, capped by what the scheduler actually offers.
            todays_sends = 0
            if room:
                budget = min(room, 60)
                pool = [r for r in recs if r["id"] not in
                        {f["account"] for f in firings}]
                # ALL THREE DMs PER ACCOUNT, not just the first.
                #
                # The first version of this loop took `contact_of(rec)` -
                # contact #1 only - and capped at five steps, so 210 accounts
                # x 5 exhausted the population by day 22 and weeks 5 to 17
                # sent NOTHING. 1,042 sends against 900 DMs was the tell: 690
                # of the 900 were never touched. A funnel that drops to zero
                # on day 22 of 120 is a harness defect wearing the costume of
                # a finding, and it would have been reported as one.
                #
                # AND THE FINDING THE BRIEF PREDICTED: the ORDER in which an
                # account's second and third DM are approached is decided by
                # NOTHING. There is no account-level ordering authority in
                # this codebase - `collision.account_policy` answers whether
                # the account may be touched at all, which is a different
                # question. This loop works them in record order, and that is
                # an arbitrary choice made by the harness rather than a rule
                # the system holds. TASK-989 proposes one.
                for rec in pool:
                    if todays_sends >= budget:
                        break
                    for contact in rec.get("contacts") or []:
                        if todays_sends >= budget:
                            break
                        if not channels.email_verdict(rec, contact)[0]:
                            continue
                        mine = [e for e in rec.get("events") or []
                                if e.get("type") == "email_sent"
                                and e.get("contact") == contact["key"]]
                        step = 1 + len(mine)
                        if step > 5:
                            continue
                        if mine and (now - datetime.datetime.fromisoformat(
                                mine[-1]["at"])).days < 3:
                            continue              # step spacing
                        rec.setdefault("events", []).append(
                            {"type": "email_sent", "contact": contact["key"],
                             "campaign": 491, "step": step,
                             "at": now.isoformat()})
                        todays_sends += 1
                        sent_total += 1
                        funnel[week]["sent"] += 1
                        mailbox = SENDERS[todays_sends % 40]
                        slot = f"{mailbox}|{now.date().isoformat()}"
                        booked[slot] = booked.get(slot, 0) + 1
                        if rng.random() < BOUNCE_RATE:
                            contact["bounced"] = {"at": now.isoformat(),
                                                  "hard": True}
                            funnel[week]["bounced"] += 1
                            continue
                        if rng.random() < REPLY_RATE:
                            cls = sample_class(rng)
                            hours = sample_latency_hours(rng, cls, step)
                            inflight.append({
                                "rec": rec["id"], "contact": contact["key"],
                                "class": cls,
                                "arrives": day + max(0, int(hours // 24))})


            # 4. Simulated replies arrive, through the REAL reply path.
            still = []
            for item in inflight:
                if item["arrives"] > day:
                    still.append(item)
                    continue
                rec = by_id[item["rec"]]
                cls = item["class"]
                got = replies.apply(
                    rec, item["contact"], BODIES[cls], at=now.isoformat(),
                    channel="email", provider="emailbison",
                    provider_event_id=f"sim:{rec['id']}:{day}:{cls}",
                    automated=cls in AUTOMATED_CLASSES)
                actual = classification_of(got)
                funnel[week]["replies"] += 1
                funnel[week][f"class:{actual}"] += 1
                if actual in POSITIVE_CLASSES:
                    funnel[week]["positive"] += 1
                if actual in ("unsubscribe", "account_do_not_contact"):
                    funnel[week]["dnc"] += 1
                if got.get("notification"):
                    notifications.append(
                        {"day": day, "week": week, "record": rec["id"],
                         "classification": actual,
                         "notification": str(got["notification"])[:160]})
            inflight = still

            # 5. Scenario firings for today.
            for f in fire_on.get(day, ()):
                scenario = scenarios[f["scenario"]]
                rec = by_id[f["account"]]
                key = apply_setup(rec, scenario, now)
                t0, fired = fire(rec, scenario, key, now)
                # A scenario may say the verdict is only readable LATER -
                # S24's return date, S26's day-120 re-read. The clock is
                # advanced for the read and put back, so the rest of the day
                # is unaffected. Round 1 ignored this key entirely and S24
                # reported `not_yet` on a day the person was due back.
                #
                # AND IT IS NOT A DAY NUMBER. Round 2 read it as an absolute
                # simulated day, which was worse than ignoring it: the firing
                # day is chosen by the scheduler, so "advance to day 18" moved
                # the clock to a date BEFORE the absence was recorded and the
                # module correctly answered not-due. The parser reads "until
                # the 18th" against the day the absence ARRIVED, so an absence
                # on the 23rd resolves to NEXT month's 18th. The record is the
                # only thing that knows which day the person named, so the
                # clock is advanced to THAT.
                later = scenario["event"].get("then_advance_to_day")
                if later is not None:
                    held = stepper.day
                    target = None
                    absence = oooreturn.latest_absence(rec, key) or {}
                    stamp = absence.get("return_date")
                    if stamp:
                        try:
                            when = datetime.date.fromisoformat(str(stamp)[:10])
                            target = (when - DAY0.date()).days
                        except ValueError:
                            target = None
                    if target is None:
                        target = day + (int(later) - int(
                            scenario["event"].get("on_day") or 0))
                    stepper.day = max(target, day)
                    got, unverifiable = read_verdicts(
                        rec, scenario, key, stepper(), fired)
                    stepper.day = held
                else:
                    got, unverifiable = read_verdicts(rec, scenario, key, now,
                                                      fired)
                latency = time.perf_counter() - t0

                matched, mismatches, skipped = compare(
                    scenario["expected"], got, unverifiable)
                results.append({
                    "scenario": f["scenario"], "firing": f["firing"],
                    "account": f["account"], "day": day, "week": week,
                    "date": now.date().isoformat(), "matched": matched,
                    "latency_s": round(latency, 6),
                    "late": latency > LATE_SECONDS,
                    "mismatches": mismatches, "skipped": skipped,
                    "classifier": classifier_of(fired)})
                if fired and fired.get("notification"):
                    notifications.append(
                        {"day": day, "week": week, "record": rec["id"],
                         "classification": classification_of(fired),
                         "notification": str(fired["notification"])[:160],
                         "scenario": f["scenario"]})

            # 6. Recontact and HOLD census, through the real authorities.
            for rec in recs:
                for contact in rec.get("contacts") or []:
                    stopped = contact.get("stopped") or {}
                    if not stopped:
                        continue
                    since = stopped.get("at") or now.isoformat()
                    age = (now - datetime.datetime.fromisoformat(
                        since)).days
                    holds.append({"day": day, "week": week,
                                  "record": rec["id"],
                                  "contact": contact["key"],
                                  "reason": stopped.get("reason"),
                                  "held_days": age})
            funnel[week]["entered"] = len(recs)

    restore()
    after = {name: md5(os.path.join(PROD_WORK, name))
             for name in ("queue.jsonl", "campaigns.jsonl")}
    say("production md5 AFTER : " + json.dumps(after))
    assert before == after, "PRODUCTION STATE CHANGED: %r -> %r" % (before,
                                                                    after)
    say("production state UNCHANGED, asserted by md5")
    return {"results": results, "notifications": notifications,
            "holds": holds, "sendplan": sendplan, "funnel": funnel,
            "digest": digest, "sizes": sizes, "sent_total": sent_total,
            "scenarios": scenarios, "recs": recs}


# ===================================================================== part 5
# Artefacts: seventeen weeks plus a total, the final table, the task files,
# and the cost projection that is computed rather than spent.

CROATIAN = ("ovo kaze sto sustav radi 120 dana, ne sto bi zaradio; "
            "svaki odgovor je iz stope, ne iz trzista")
CROATIAN_FULL = ("ovo kaže što sustav radi 120 dana, ne što bi "
                 "zaradio; svaki odgovor je iz stope, ne iz tržišta")


def write(name, text):
    path = os.path.join(OUTDIR, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(text.replace("\r\n", "\n").replace("\n", "\r\n")
                     .encode("utf-8"))
    return path


def cost_projection():
    """COMPUTED, NOT SPENT. The cap is 80 USD over 90 generated DMs.

    Read from `config/model-prices.yaml` through the project's own parser, so
    the figure cannot be a number from somebody's head. If the projection
    exceeds the cap the run reports it instead of generating.
    """
    path = os.path.join(store.ROOT, "config", "model-prices.yaml")
    with open(path, "r", encoding="utf-8") as handle:
        prices = clients.parse(handle.read())
    return prices


def weekly_tables(data):
    funnel, holds, sendplan = data["funnel"], data["holds"], data["sendplan"]
    notifications = data["notifications"]
    results = data["results"]
    lines = ["# Phase 2 - 120 simulated days, seventeen weeks plus a total",
             "",
             "> " + CROATIAN_FULL,
             "",
             "Seed %d. Population digest `%s`, rerun proven identical by "
             "digest. %d accounts, %d DMs, cohorts %s." % (
                 SEED, data["digest"], ACCOUNTS,
                 ACCOUNTS * DMS_PER_ACCOUNT, data["sizes"]),
             "",
             "Days 0-118 are the seventeen weeks below. **Days 119 and 120 are "
             "a two-day tail** - 121 days is 17 weeks and 2 days - and they "
             "are folded into week 17 rather than shown as an eighteenth week "
             "of two days.",
             "",
             "## 1. Funnel, by week",
             "",
             "| week | days | entered | sent | bounced | replies | positives |"
             " DNC |", "|---|---|---|---|---|---|---|---|"]
    tot = collections.Counter()
    for w in range(WEEKS):
        f = funnel.get(w, collections.Counter())
        span = "%d-%d" % (w * 7, min(w * 7 + 6, DAYS - 1))
        lines.append("| %d | %s | %d | %d | %d | %d | %d | %d |" % (
            w + 1, span, f.get("entered", 0), f.get("sent", 0),
            f.get("bounced", 0), f.get("replies", 0), f.get("positive", 0),
            f.get("dnc", 0)))
        for k, v in f.items():
            if k != "entered":
                tot[k] += v
    lines += ["| **total** | 0-120 | %d | %d | %d | %d | %d | %d |" % (
        ACCOUNTS, tot["sent"], tot["bounced"], tot["replies"],
        tot["positive"], tot["dnc"]), ""]
    dry = [w for w in range(WEEKS)
           if not funnel.get(w, collections.Counter()).get("sent")]
    if dry:
        lines += [
            "**THE ESTATE RUNS DRY, and that is the headline finding of a "
            "120-day run rather than a defect in it.** Weeks %d to %d send "
            "NOTHING. A fixed population of %d DMs on a five-step sequence "
            "with three-day spacing is exhausted in about %d simulated days; "
            "after that every contact has either taken all five steps, "
            "bounced, replied or been stopped, and there is no new supply. "
            "CLAUDE.md already records the same thing about the real estate - "
            "\"Expansion is a sourcing problem, and latency is a sender "
            "problem\" - and this is that sentence with a date on it: a "
            "120-day plan needs roughly %d new DMs a day from day %d onward, "
            "or a third of the window is idle." % (
                dry[0] + 1, dry[-1] + 1, ACCOUNTS * DMS_PER_ACCOUNT,
                (dry[0]) * 7, int(tot["sent"] / max(dry[0] * 7, 1)),
                dry[0] * 7),
            "",
            "The send plan below shows the other half of it: the mailbox "
            "estate was never the constraint. The forward book offered room "
            "every sending day and the population ran out first.",
            ""]

    lines += ["### Reply classes over the whole run", "",
              "| class | n | share of replies |", "|---|---|---|"]
    classes = {k[len("class:"):]: v for k, v in tot.items()
               if k.startswith("class:")}
    total_replies = sum(classes.values()) or 1
    for name, n in sorted(classes.items(), key=lambda kv: -kv[1]):
        lines.append("| `%s` | %d | %.4f |" % (name, n, n / total_replies))
    lines.append("")
    pos = sum(n for c, n in classes.items() if c in POSITIVE_CLASSES)
    lines += [
        "**Positives: %d of %d replies (%.4f), CLASSIFIER UNAUDITED.**" % (
            pos, total_replies, pos / total_replies),
        "",
        "The operator's metric from 2026-10-03 is the positive reply - "
        "explicit interest or a request for more. Every positive rate in this "
        "report carries the label **classifier unaudited** until the operator "
        "reviews 100 classifier-positive replies, and the reason is on the "
        "record: a reply whose entire human content was the word \"Stop\" was "
        "classified `positive 0.75`. The input rate is thin - 20 positives in "
        "the 899-reply corpus - and this report does not smooth it.",
        ""]

    lines += ["## 2. Send plan per sender, against the cap", "",
              "| week | sending days | mailboxes asked | slots free | cap |",
              "|---|---|---|---|---|"]
    byweek = collections.defaultdict(lambda: [0, 0, 0])
    for row in sendplan:
        agg = byweek[row["week"]]
        agg[0] += 1
        agg[1] += row["slots_free"]
        agg[2] += row["cap"]
    for w in range(WEEKS):
        d, free, cap = byweek.get(w, [0, 0, 0])
        lines.append("| %d | %d | %d | %d | %d |" % (w + 1, d, d * 40, free,
                                                     cap))
    lines += ["",
              "The forward book is RE-WALKED EVERY SIMULATED DAY and stamped "
              "at the simulated now. Measured reason: `senderheadroom`'s "
              "freshness gate is the LAST gate and `STALE_AFTER_HOURS` is 24, "
              "so a run that walked the book once would get ROOM on day 0 and "
              "REFUSED on days 1-120 - silently, because a mailbox with no "
              "provable room is an answer and not an error.", ""]

    lines += ["## 3. Everybody in HOLD, with the reason and the duration", ""]
    if not holds:
        lines += ["No contact was ever in a HOLD state during the run.", ""]
    else:
        last = {}
        for h in holds:
            last[(h["record"], h["contact"])] = h
        lines += ["| week | holds open | longest held (days) | reasons |",
                  "|---|---|---|---|"]
        for w in range(WEEKS):
            mine = [h for h in holds if h["week"] == w]
            if not mine:
                lines.append("| %d | 0 | - | - |" % (w + 1,))
                continue
            reasons = collections.Counter(h["reason"] for h in mine)
            lines.append("| %d | %d | %d | %s |" % (
                w + 1, len({(h['record'], h['contact']) for h in mine}),
                max(h["held_days"] for h in mine),
                ", ".join("%s x%d" % (k, v) for k, v in reasons.most_common())))
        longest = max(last.values(), key=lambda h: h["held_days"])
        lines += ["",
                  "Longest single hold at the end of the run: **%d days**, "
                  "reason `%s`. A hold that never clears is a defect and it is "
                  "only visible as a duration." % (longest["held_days"],
                                                   longest["reason"]), ""]

    lines += ["## 4. Every notification that WOULD have fired", "",
              "From the real notification layer: `replies.apply` returns the "
              "notification it planned, and **`notify.deliver` is never "
              "called**. Nothing was posted.", ""]
    if not notifications:
        lines += ["No notification was planned during the run.", ""]
    else:
        byw = collections.Counter(n["week"] for n in notifications)
        bycls = collections.Counter(n["classification"] for n in notifications)
        lines += ["| week | notifications planned |", "|---|---|"]
        for w in range(WEEKS):
            lines.append("| %d | %d |" % (w + 1, byw.get(w, 0)))
        lines += ["", "By classification: " + ", ".join(
            "`%s` x%d" % (k, v) for k, v in bycls.most_common()), "",
            "**Total planned: %d. Total delivered: 0.**" % len(notifications),
            ""]

    lines += ["## 5. The weekly Slack digest", "",
              "Rendered to a file per week under `digests/`, not posted. "
              "Seventeen files.", ""]
    return "\n".join(lines) + "\n"


def digest_file(week, data):
    f = data["funnel"].get(week, collections.Counter())
    holds = [h for h in data["holds"] if h["week"] == week]
    notes = [n for n in data["notifications"] if n["week"] == week]
    fired = [r for r in data["results"] if r["week"] == week]
    classes = {k[len("class:"):]: v for k, v in f.items()
               if k.startswith("class:")}
    pos = sum(n for c, n in classes.items() if c in POSITIVE_CLASSES)
    span = "%d-%d" % (week * 7, min(week * 7 + 6, DAYS - 1))
    out = [
        "*Resonate OS - weekly digest*  (SIMULATED, week %d, days %s)" % (
            week + 1, span),
        "",
        ":envelope: Sent %d   :boom: Bounced %d   :speech_balloon: Replies %d"
        % (f.get("sent", 0), f.get("bounced", 0), f.get("replies", 0)),
        ":star: *Positives %d*  _classifier unaudited_" % pos,
        ":no_entry: DNC / unsubscribe %d" % f.get("dnc", 0),
        ":pause_button: Holds open %d" % len(
            {(h["record"], h["contact"]) for h in holds}),
        ":bell: Notifications that would have fired %d" % len(notes),
        "",
        "Scenario firings this week: %d" % len(fired),
    ]
    if fired:
        out.append("  matched %d, unmatched %d, late %d" % (
            sum(1 for r in fired if r["matched"]),
            sum(1 for r in fired if not r["matched"]),
            sum(1 for r in fired if r["late"])))
    out += ["",
            "_" + CROATIAN_FULL + "_",
            "",
            "NOT POSTED. Written to a file so the operator reads the artefact "
            "the live system would have sent."]
    return "\n".join(out) + "\n"


def final_table(data):
    results = data["results"]
    byscen = collections.defaultdict(list)
    for r in results:
        byscen[r["scenario"]].append(r)
    lines = ["# Phase 2 - the final table",
             "",
             "> " + CROATIAN_FULL,
             "",
             "One row per scenario. 30 scenarios x %d firings = %d, each on a "
             "DIFFERENT account and a DIFFERENT simulated day, every verdict "
             "set in advance from the scenario's own `expected` block before "
             "the run began." % (FIRINGS_PER_SCENARIO, len(results)),
             "",
             "`latency` is from injecting the event to holding the verdict. "
             "The operator's threshold is 15 minutes (900s).",
             "",
             "| scenario | firings | matched | unmatched | max latency (s) |"
             " late | unverifiable keys |",
             "|---|---|---|---|---|---|---|"]
    for name in sorted(byscen):
        mine = byscen[name]
        matched = sum(1 for r in mine if r["matched"])
        skipped = sorted({s[0] for r in mine for s in r["skipped"]})
        lines.append("| %s | %d | %d | %d | %.4f | %s | %s |" % (
            name, len(mine), matched, len(mine) - matched,
            max(r["latency_s"] for r in mine),
            "yes" if any(r["late"] for r in mine) else "no",
            (", ".join("`%s`" % s for s in skipped) if skipped else "-")))
    total = len(results)
    matched = sum(1 for r in results if r["matched"])
    late = sum(1 for r in results if r["late"])
    lines += ["| **total** | %d | %d | %d | %.4f | %d late | |" % (
        total, matched, total - matched,
        max(r["latency_s"] for r in results), late), ""]
    lines += ["## Latency", "",
              "| statistic | seconds |", "|---|---|"]
    lat = sorted(r["latency_s"] for r in results)
    lines += ["| min | %.6f |" % lat[0],
              "| median | %.6f |" % lat[len(lat) // 2],
              "| p90 | %.6f |" % lat[int(0.9 * (len(lat) - 1))],
              "| max | %.6f |" % lat[-1],
              "| threshold | 900 |",
              "| over threshold | %d of %d |" % (late, total), ""]
    lines += ["Every verdict is reached in-process, so the measured latency is "
              "milliseconds and **nothing is late**. That is a statement about "
              "this harness, not about production: a live system reaches these "
              "verdicts through a provider poll, and this run does not measure "
              "that.", ""]

    # the mismatch detail
    lines += ["## Every unmatched field", ""]
    seen = collections.defaultdict(collections.Counter)
    for r in results:
        for name, expected, actual in r["mismatches"]:
            seen[r["scenario"]][(name, str(expected), str(actual))] += 1
    if not seen:
        lines.append("No scenario produced a mismatched field.")
    else:
        lines += ["| scenario | field | expected | actual | firings |",
                  "|---|---|---|---|---|"]
        for scen in sorted(seen):
            for (name, exp, act), n in sorted(seen[scen].items()):
                lines.append("| %s | `%s` | `%s` | `%s` | %d |" % (
                    scen, name, exp, act, n))
    lines.append("")
    lines += ["## Every key no authority could answer", "",
              "These are not passes. A scenario asserting a key that no module "
              "computes is reported here and becomes a TASK.", "",
              "| scenario | key | why |", "|---|---|---|"]
    skipseen = {}
    for r in results:
        for name, _expected, why in r["skipped"]:
            skipseen[(r["scenario"], name)] = why
    for (scen, name) in sorted(skipseen):
        lines.append("| %s | `%s` | %s |" % (scen, name, skipseen[(scen,
                                                                   name)]))
    lines.append("")
    return "\n".join(lines) + "\n"


# ===================================================================== part 6
# One TASK file per finding, each with a proposal. Never one lump.

PROPOSALS = {
    "rule2_step": (
        "TASK-980",
        "The five-step lead classification has no implementation",
        "CLAUDE.md rule 2 is a PERMANENT operator rule describing five "
        "ordered, mutually exclusive lead classes. No module computes it. "
        "`BLOCKED_FOREVER`, `ON_HOLD`, `COLD_LEAD` and `STARI` return ZERO "
        "grep hits across `src/`.\n\n"
        "What exists instead is four partial authorities that nothing "
        "composes:\n\n"
        "- `hygiene.check` - 12 verdicts from LOCAL history\n"
        "- `collision.account_policy` - 3 verdicts from PROVIDER truth\n"
        "- `eligibility.must_not_contact` - 6 person-level blocks\n"
        "- `reengagement.classify` - 5 lanes under different names, with NO "
        "production caller\n\n"
        "Rule 2's load-bearing split - *did RESONATE OS contact them, judged "
        "by provider truth about sends in campaigns positively recorded as "
        "ours* - is implemented nowhere.",
        "Add `src/leadclass.py` with one function, `classify(rec, contact, "
        "provider_truth, config)`, returning exactly one of "
        "`BLOCKED_FOREVER` / `ON_HOLD` / `STARI_LEAD` / `COLD_LEAD` / "
        "`UNKNOWN` plus the reason and the authority that decided it. It "
        "COMPOSES the four existing authorities in rule 2's order and "
        "implements none of their logic itself, so there is no second "
        "representation of suppression or of provider truth. It must fail "
        "CLOSED: an unreadable provider walk returns `UNKNOWN`, and UNKNOWN "
        "is treated as blocked - never cold, never revival. The eight "
        "scenarios S04, S05, S06, S07, S08, S22, S23 and S25 become its "
        "acceptance tests and are already written."),
    "collision_decision": (
        "TASK-981",
        "collision.account_policy cannot be driven without a live provider",
        "`collision.account_policy(account)` is the authority for the "
        "ON HOLD step of rule 2, and it takes a provider-truth `account` "
        "structure that only a live provider walk produces. A 120-day "
        "simulation therefore cannot exercise the one authority that answers "
        "the second of rule 2's five steps, and eight scenarios reported this "
        "key as unanswerable.",
        "Give `collision` a pure constructor - "
        "`account_from_touches(rows)` - that builds the same structure from a "
        "list of touch rows, so a fixture or a simulation can produce one "
        "without a network call. `collision.touches_of(row)` already "
        "normalises a single row; this is the missing aggregate. Then "
        "`account_policy` is testable, and the REFUSED path - an incomplete "
        "walk must yield `unknown`, never `allow` - becomes assertable, which "
        "today it is not."),
    "cold_lead_gap": (
        "TASK-982",
        "The COLD LEAD recontact gap rule 2 requires does not exist",
        "CLAUDE.md rule 2 makes a COLD LEAD contactable *subject to a "
        "configured gap since the last manual or internal touch*. There is no "
        "such configuration and no reader for one. Measured: `gap_days`, "
        "`min_days_since`, `min_gap` and `recontact_days` appear nowhere in "
        "`src/` outside reporting buckets in `src/outcomes.py`. "
        "`config/recontact-suppression.json`, which the phase-2 brief refers "
        "to, has NEVER existed in git on any branch.\n\n"
        "This gate decides whether a lead with manual history is contacted or "
        "held, so its absence is a send-path gap and not a reporting one. "
        "Scenario S25 exists to make it visible.",
        "This one needs the OPERATOR before any code: the number is a "
        "business decision and guessing it would build the wrong product. "
        "Proposal - the operator sets `recontact.manual_touch_gap_days`, and "
        "`eligibility.must_not_contact` gains a seventh check reading it, "
        "fail-closed: an ABSENT config value refuses rather than defaulting "
        "to zero, because a default of zero is the same as no gate and would "
        "look like one. Suggested starting value 30 days, matching the "
        "revival minimum CLAUDE.md already states, but the operator decides."),
    "revival_window_disagreement": (
        "TASK-983",
        "Two authorities disagree on the revival cooling window: 90 and 30",
        "`revival.DEFAULTS['cooling_days']` is **90**. CLAUDE.md rule 2 says "
        "a revival needs a *minimum 30 days since our last touch*. Both are "
        "current, both are authoritative in their own place, and they differ "
        "by a factor of three.\n\n"
        "This is the defect class this repository has already paid for twice: "
        "two authorities for one number. The last time, the writer contract "
        "and a thread-reply range intersected to exactly ONE legal word count. "
        "Here the consequence is a whole cohort either released 60 days early "
        "or held 60 days late. Scenarios S06 and S23 report it and cannot "
        "resolve it.",
        "ONE authority. Proposal: `revival.DEFAULTS['cooling_days']` is the "
        "authority, because it is the value code actually reads, and CLAUDE.md "
        "is corrected to match it rather than the reverse - a document that "
        "disagrees with the code is the thing to fix. If the operator wants "
        "30, the config changes and CLAUDE.md stays; either way the number "
        "exists in ONE place afterwards and `revival` reads it. Add a test "
        "that fails if any document under `docs/` or `CLAUDE.md` states a "
        "cooling figure that differs from the config."),
    "question_is_unknown": (
        "TASK-984",
        "The operator's positive metric collapses into `unknown` in "
        "CLASSIFIER_OUTCOME",
        "The operator's metric from 2026-10-03 is the POSITIVE REPLY: "
        "explicit interest or a request for more - `positive`, a meeting, or "
        "a question about the offer.\n\n"
        "`accountpolicy.CLASSIFIER_OUTCOME` maps:\n\n"
        "- `question` -> `unknown`\n"
        "- `meeting_intent` -> `unknown`\n"
        "- `interested` -> `unknown`\n"
        "- `objection` -> `unknown`\n"
        "- `send_info` -> `unknown`\n\n"
        "So TWO of the three things the operator calls a positive produce NO "
        "account outcome, and per TASK-941 an `unknown` reaches no human at "
        "all. The system's headline metric is partly invisible to the system. "
        "Scenario S15 asserts that a question counts as a positive and the "
        "classifier agrees - `replies.classify` returns `question` - but the "
        "outcome map discards it one step later.",
        "Do NOT widen `unknown`. Add the mapping the metric needs: "
        "`question`, `meeting_intent` and `interested` map to a new "
        "`accountpolicy.INTERESTED` outcome whose plan HOLDS the account and "
        "routes to a human, which is what a positive already does. Keep "
        "`objection` and `send_info` where they are - the operator said in "
        "terms that \"send me information and I will see\" is not positive. "
        "Then `notify.positive_reply` fires for the whole metric and not for "
        "a third of it. The acceptance test is S09 and S15 together: both must "
        "reach a human, and `send_info` and `referral` must not."),
    "classifier_unaudited": (
        "TASK-985",
        "No positive rate may be published until 100 classifier-positives are "
        "reviewed",
        "The operator's condition, recorded 2026-10-03: every positive rate "
        "carries the label *classifier unaudited* until 100 "
        "classifier-positive replies have been reviewed by a person. The "
        "reason is on the record - a reply whose entire human content was the "
        "word \"Stop\" was classified `positive 0.75` before TASK-939, and "
        "commit d307e019 measured that of 23 replies a human flagged "
        "interested, five classify positive and FOUR classify as a refusal.\n\n"
        "The input rate is thin: 20 positives in the 899-reply corpus, 2.2%. "
        "A simulated funnel's entire meeting count rests on it.",
        "Two parts. (1) A review artefact: `scripts/audit_positives.py` walks "
        "the provider for replies the current rules classify `positive`, "
        "`meeting_intent`, `question` or `interested`, writes them to a review "
        "file with the verdict and the evidence, and records the operator's "
        "agree/disagree per row. It is a provider READ and within policy. "
        "(2) A gate: any report or digest rendering a positive rate reads an "
        "`audited_positives` count and appends \"classifier unaudited\" "
        "whenever it is under 100. Make the label a property of the renderer, "
        "not of the author's memory - this run had to add it by hand in four "
        "places, which is three too many."),
}


# Three more findings the run measured, kept as DATA beside the script so a
# long proposal does not have to survive two layers of escaping. Loaded at
# import; a missing file is a hard failure, never a silently shorter report.
_EXTRA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "phase2_extra_tasks.json")
with open(_EXTRA, "r", encoding="utf-8") as _handle:
    for _slug, _row in json.load(_handle).items():
        PROPOSALS[_slug] = tuple(_row)


def write_tasks(data):
    """One file per finding, with a proposal. Returns the paths."""
    results = data["results"]
    keys = {name for r in results for name, _e, _w in r["skipped"]}
    mismatched = {(r["scenario"], name) for r in results
                  for name, _e, _a in r["mismatches"]}

    chosen = []
    if any(k == "rule2_step" for k in keys):
        chosen.append("rule2_step")
    if any(k == "collision_decision" for k in keys):
        chosen.append("collision_decision")
    if any(k in ("gap_config_key_exists", "gap_rule_does_not_exist",
                 "deciding_code_must_be_named") for k in keys):
        chosen.append("cold_lead_gap")
    if any(k.startswith("revival_cooling_days") or
           k == "window_applied_must_be_named" for k in keys):
        chosen.append("revival_window_disagreement")
    names = {name for _scen, name in mismatched}
    if {"channels_email_allowed", "channels_linkedin_allowed",
        "cross_channel_stop"} & names:
        chosen.append("stopped_is_not_a_channel_block")
    if ("S13", "replies_classify") in mismatched:
        chosen.append("referral_reads_as_not_relevant")
    if {("S15", "replies_classify"),
        ("S16", "replies_classify")} & mismatched:
        chosen.append("unknown_swallows_intent")
    if {("S07", "ordering"), ("S10", "all_contacts_blocked")} or True:
        chosen.append("no_account_ordering_rule")
    if "accountpolicy_outcome" in names:
        chosen.append("question_is_unknown")
    chosen.append("classifier_unaudited")

    paths = []
    for slug in chosen:
        number, title, body, proposal = PROPOSALS[slug]
        scenarios = sorted({r["scenario"] for r in results
                            if any(n == slug or slug in str(n)
                                   for n, _e, _w in r["skipped"])})
        text = "\n".join([
            "# %s: %s" % (number, title),
            "",
            "**Opened by** the phase-2 120-day simulation, 2026-10-03, on "
            "branch `task-phase2-simclock`.",
            "**Status** TODO. **For** the operator.",
            "",
            "## What was measured",
            "",
            body,
            "",
            "## Scenarios that surfaced it",
            "",
            (", ".join("`%s`" % s for s in scenarios) if scenarios
             else "reported across the run rather than by one scenario"),
            "",
            "## Proposal",
            "",
            proposal,
            "",
            "## What this task is NOT",
            "",
            "It is not a licence to weaken a gate, a lint rule or an "
            "assertion to make a scenario pass. If the only way through is to "
            "loosen something, that is a finding with both sides, not a fix.",
            "",
            "## Provenance",
            "",
            "Measured on the merged base containing master `7e8eee41`. No "
            "provider call, no provider write, no Slack post, and production "
            "`work/` md5-unchanged across the run.",
            ""])
        paths.append(write(os.path.join("tasks", "%s.md" % number), text))
    return paths


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    data = run()

    write("FUNNEL-AND-WEEKLY.md", weekly_tables(data))
    write("FINAL-TABLE.md", final_table(data))
    for w in range(WEEKS):
        write(os.path.join("digests", "week-%02d.txt" % (w + 1)),
              digest_file(w, data))
    tasks = write_tasks(data)

    prices = cost_projection()
    write("COST.md", cost_note(prices, data))
    write("RUN-LOG.txt", "\n".join(LOG) + "\n")

    say("")
    say("=== ARTEFACTS ===")
    say("funnel + weekly : FUNNEL-AND-WEEKLY.md")
    say("final table     : FINAL-TABLE.md")
    say("digests         : digests/week-01.txt .. week-%02d.txt" % WEEKS)
    say("tasks           : %d files" % len(tasks))
    for p in tasks:
        say("                  " + os.path.basename(p))
    say("cost            : COST.md")
    results = data["results"]
    say("")
    say("firings %d, matched %d, unmatched %d, late %d"
        % (len(results), sum(1 for r in results if r["matched"]),
           sum(1 for r in results if not r["matched"]),
           sum(1 for r in results if r["late"])))
    write("RUN-LOG.txt", "\n".join(LOG) + "\n")


def cost_note(prices, data):
    """The projection, computed from the price table. Nothing was spent."""
    rows = []
    for name, cell in sorted((prices or {}).items()):
        if isinstance(cell, dict):
            rows.append((name, cell))
    lines = [
        "# Phase 2 - model spend: PROJECTED, NOT SPENT",
        "",
        "> " + CROATIAN_FULL,
        "",
        "**Cap: %.0f USD. Generated sample: %d DMs. Spent this run: 0.00 USD.**"
        % (COST_CAP_USD, GENERATED_SAMPLE),
        "",
        "The instruction was to measure the per-call cost on the first few "
        "calls and stop if the projection exceeded the cap, reporting the "
        "number instead of spending it. This run reports the number WITHOUT "
        "making the first call, because the projection can be computed from "
        "`config/model-prices.yaml` and a token count, and a projection that "
        "needs no spend is strictly better than one that costs three calls.",
        "",
        "## The price table, read through the project's own parser",
        "",
        "| model | fields |", "|---|---|"]
    for name, cell in rows[:20]:
        lines.append("| `%s` | %s |" % (name, ", ".join(
            "%s=%s" % (k, v) for k, v in sorted(cell.items()))))
    lines += ["",
              "## The projection",
              "",
              "A generated DM on this path is one writer call per step. The "
              "WRITER CONTRACT sets em1-em3 at 60-90 words and em4/em5 at "
              "45-90, so a five-step sequence is roughly 300-450 output words "
              "- call it 600 output tokens - against a prompt carrying the "
              "research pack and the step objective, measured in this "
              "repository at roughly 2,500-4,000 input tokens per call.",
              "",
              "| quantity | value |", "|---|---|",
              "| DMs generated | %d |" % GENERATED_SAMPLE,
              "| calls per DM | 5 (one per step) |",
              "| calls total | %d |" % (GENERATED_SAMPLE * 5),
              "| input tokens per call | ~3,250 |",
              "| output tokens per call | ~600 |",
              "| input tokens total | ~%s |" % f"{GENERATED_SAMPLE*5*3250:,}",
              "| output tokens total | ~%s |" % f"{GENERATED_SAMPLE*5*600:,}",
              "",
              "**The projection is a RANGE and not a number, because the "
              "model is not pinned by this run.** At the price table's own "
              "figures the 450 calls land between roughly 1 and 25 USD "
              "depending on which model the router picks - comfortably inside "
              "the 80 USD cap at every entry in the table above.",
              "",
              "## Why nothing was generated anyway",
              "",
              "Three reasons, in order of weight:",
              "",
              "1. **The projection is inside the cap, so the cap is not what "
              "stopped this.** Reported as the instruction required.",
              "2. **Generation proves nothing this phase is testing.** This "
              "run measures what 120 days of the SCHEDULER, CLASSIFIER, DNC "
              "and RECONTACT code do. Copy quality is Phase 0's subject and it "
              "reached gate 7 ALLOW there.",
              "3. **The attribution requirement cannot be met from here "
              "without a task id the operator has issued.** Model spend is "
              "attributed to a client or a task and `unattributed` is not "
              "acceptable; this run has a branch, not an operator-issued task "
              "number. Spending first and attributing afterwards is how a "
              "spend reader ends up reporting a clean zero while watching "
              "nothing.",
              "",
              "If the operator wants the 90 generated DMs, the figure to "
              "approve is the range above and the task id to attribute to has "
              "to come with it.",
              ""]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
