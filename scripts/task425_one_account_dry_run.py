#!/usr/bin/env python3
"""TASK-425. One Productive account, four causal runs, zero provider writes.

    py -3 scripts/task425_one_account_dry_run.py --out docs/ARTIFACT.md

WHAT THIS IS. The operator's four frozen acceptance criteria
(`docs/OPERATING-MODE.md`, "TASK-425 ACCEPTANCE"), executed through the real
production entrypoints and written out as one audit artifact. It is a harness,
not a product path: everything it drives is production code, and everything it
adds is measurement.

## HOW ZERO PROVIDER WRITES IS PROVED, NOT ASSERTED

Two transports, installed over `providers.request` - the single HTTP seam every
provider module in this repository goes through - and the REAL `bison` and
`heyreach` modules left in place underneath. A fake provider cannot prove that
nothing was told to a provider, only that nothing was told to the fake.

  GENERATION PHASE   the writer needs a model, and a model is an HTTP call. The
                     transport allows exactly ONE host, the endpoint named by
                     `LLM_BASE_URL`, and RAISES on every other URL. So a
                     provider call during generation fails the run rather than
                     passing quietly.
  STAGING PHASE      no model is needed, so the transport raises on ANY call,
                     which is `tests/test_a_dry_run_runs_the_sequence_gate.py`'s
                     pattern exactly.

BOTH TRAPS ARE FIRED ON PURPOSE, each against a real EmailBison URL, before the
phase they guard. `assertEqual([], requests)` is satisfied just as well by a
trap that was never installed, and a test that cannot fail is worse than no
test. Every request either phase sees is recorded with its host, and the
artifact prints the whole list.

## WHY IT RUNS IN A THROWAWAY STORE

`store.use_directory()` repoints `QUEUE` and clears all 34 state overrides, so
the fixture account, its copy and its campaign row live in a temporary directory
and the production queue is never opened. `store.refuse_production_write` is the
second fence and would raise if this pointed at `work/` by accident.

## WHAT THE FIXTURE APPROVAL IS, AND IS NOT

`bisonfactory._certified_copy` stages only words an ACCOUNTABLE approver signed,
which is the gate that closes the "thirty steps of unapproved words" defect of
2026-09-16. To exercise the staging path at all, the generated copy in the
throwaway store is stamped by `task425-fixture@example.test`.

THAT IS NOT AN APPROVAL AND THIS SCRIPT NEVER CLAIMS ONE. It is not the
operator, it is not `operator-control-arm`, it is a reserved-domain address that
exists so the refusal-shaped gate downstream of it can be observed. Approval is
the operator's, the artifact carries no approved copy, and nothing this script
writes leaves the temporary directory.
"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (approval, bisonfactory, cadence, campaigns, clients,   # noqa: E402
                 copylint, eligibility, generate, generate_campaign,
                 heyreachfactory, killswitch, llm, offers, packfacts,
                 providers, sequencegate, sequenceplan, spendledger, store,
                 workspaces)
from tests import task425fixture as fixture                     # noqa: E402

CLIENT = "productive"

#: The approver stamped onto generated copy inside the throwaway store. A
#: reserved-domain address on purpose: `approval.is_accountable_approver` accepts
#: an email, so the gate can be exercised, and nobody reading an audit trail can
#: mistake this for the operator.
FIXTURE_APPROVER = "task425-fixture@example.test"

#: The URL each booby trap is fired at on purpose. A real EmailBison route, so
#: the thing proved is that the seam the provider modules use is armed.
TRAP_URL = "https://api.emailbison.com/api/campaigns"

#: THE MODEL THIS RUN ASKS FOR, and why it is named here.
#:
#: `docs/OPERATING-MODE.md` MODEL POLICY: "Sonnet - prospect-facing copy - until
#: §34's tournament says otherwise". That is the recorded policy and this is
#: prospect-facing copy, so the run follows it rather than whatever
#: `LLM_MODEL` happens to hold.
#:
#: IT IS ALSO A MEASUREMENT, NOT A PREFERENCE. The endpoint's configured default
#: (`openai/gpt-4.1-mini`) returns CURLY APOSTROPHES in every LinkedIn note, and
#: `lint` refuses `em`, `en`, the non-breaking hyphen and both curly single
#: quotes. Measured 2026-09-28: all three contacts refused, three attempts each,
#: every rejection naming the curly apostrophe, and nothing stored - even with
#: the rule added to the writer's own HARD RULES and fed back in the retry
#: block. Under Sonnet the same fixture produced zero non-ASCII characters and
#: passed `copylint` and `lint` on the first attempt.
#:
#: `--model` and `LLM_MODEL` both override it, so the policy is a default rather
#: than a slug buried in code.
POLICY_MODEL = "anthropic/claude-sonnet-4"

#: Hosts that must never be contacted. Matched as substrings of the host,
#: because a provider's base URL is configuration and may carry a subdomain.
PROVIDER_HOSTS = ("emailbison", "heyreach", "contactout", "blitz", "apify",
                  "slack.com", "reoon", "aiark", "deliverable",
                  "cheapvalidator", "cheapverifier")


class AProviderRequestWasMade(AssertionError):
    """The transport was reached by something that is not the model.

    On a zero-write run that is always a failure, and it is an AssertionError
    rather than a provider error so it cannot be mistaken for the provider
    refusing us.
    """


class Wire:
    """Every HTTP request this run makes, and what was allowed to happen.

    `allow` is the single host the model is reachable on, or None for "nothing
    at all". The real transport is called ONLY for an allowed host; everything
    else raises before a socket is opened, and is recorded either way.
    """

    def __init__(self):
        self.requests = []
        self.allow = None
        self._firing = False
        self._real = providers._urllib_transport

    def host_of(self, url):
        text = str(url or "")
        return (text.split("/")[2] if "//" in text else text).lower()

    def install(self, allow=None):
        self.allow = (allow or "").lower() or None
        providers.set_transport(self._transport)

    def _transport(self, method, url, headers, body, timeout):
        host = self.host_of(url)
        # `trap` MARKS A REQUEST THIS RUN MADE ON PURPOSE. Without it the two
        # deliberate trap firings would count as two provider calls and the
        # artifact would report "provider writes = 2", which is the opposite of
        # the truth and would discredit the very measurement the trap exists to
        # support.
        self.requests.append({"method": method, "host": host,
                              "trap": self._firing,
                              "allowed": bool(self.allow and host == self.allow)})
        if self.allow and host == self.allow:
            return self._real(method, url, headers, body, timeout)
        raise AProviderRequestWasMade(
            "%s %s reached the transport. This run performs zero provider "
            "writes and zero provider reads" % (method, providers.redact(url)))

    def fire_the_trap(self):
        """Prove the trap is armed by tripping it, through the real chokepoint.

        Returns the recorded request. The claim "no provider was contacted"
        rests on this: an uninstalled transport records nothing and refuses
        nothing, and looks identical to a clean run.
        """
        before = len(self.requests)
        self._firing = True
        try:
            providers.request("POST", TRAP_URL, headers={}, body=None,
                              timeout=1)
        except AProviderRequestWasMade as caught:
            fired = self.requests[before:]
            return {"fired": True, "why": str(caught), "recorded": fired}
        finally:
            self._firing = False
        raise AssertionError(
            "the booby trap did NOT fire on %s. Every zero-write claim in this "
            "run rests on it, so an inert trap ends the run here" % TRAP_URL)

    def provider_requests(self):
        """Every request to a provider host that this run did not make on
        purpose. This is the number criterion "provider writes = 0" reads."""
        return [r for r in self.requests
                if not r.get("trap")
                and any(name in r["host"] for name in PROVIDER_HOSTS)]

    def deliberate_trap_requests(self):
        return [r for r in self.requests if r.get("trap")]

    def hosts(self):
        return sorted({r["host"] for r in self.requests})


# ------------------------------------------------------------------ the model


def env_candidates(path):
    """`config/.env`, here or in the checkout this worktree belongs to.

    `config/.env` is gitignored, so a `git worktree` created for one task has
    no copy of it and `llm.from_env()` silently falls back to whichever model is
    configured by something else. That is exactly the failure this function
    exists to stop: the first run of this harness reported `model: qwen-cli` and
    an unauthenticated CLI, because the worktree had no credentials and nothing
    said so.

    So the main checkout is tried as well, found through git's own answer rather
    than a hardcoded path: `--git-common-dir` is the shared `.git` of every
    worktree, and its parent is the checkout that owns it.
    """
    out = [path]
    common = os.environ.get("GIT_COMMON_DIR")
    if not common:
        import subprocess
        try:
            common = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                capture_output=True, text=True, timeout=15,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ).stdout.strip()
        except Exception:                                       # noqa: BLE001
            common = ""
    if common:
        root = os.path.dirname(os.path.abspath(common))
        out.append(os.path.join(root, "config", ".env"))
    return [p for p in out if p]


def load_env(path):
    """Read `config/.env` into the environment. Values are never printed.

    The file is gitignored and holds the operator's credentials. Only the NAMES
    of the variables set are reported, and `providers.redact` covers anything
    that reaches an error message.
    """
    names = []
    if not os.path.isfile(path):
        return names
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            found = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.strip())
            if found:
                os.environ[found.group(1)] = (
                    found.group(2).strip().strip('"').strip("'"))
                names.append(found.group(1))
    return names


class RecordingModel:
    """The real model, with every prompt and answer kept.

    THE PROMPT IS THE CAUSAL CARRIER, which is why this exists. Criterion 1
    asks whether changing an input changes the output; a copy diff alone cannot
    say whether the change travelled through the decision layer or came out of
    the model's own variance. The rendered prompt is deterministic given the
    inputs, so a prompt that MOVES when a fact moves proves the intelligence
    layer reaches the writer, and a prompt that does not proves it does not -
    whatever the copy then does.

    Each prompt is recorded with a sha256 prefix and a stage label read off the
    prompt itself, so two runs can be diffed stage by stage.
    """

    name = "recording"

    #: How a prompt is attributed to a stage. Read off the system prompt's own
    #: distinctive wording rather than a call counter: the number of calls per
    #: contact varies with the retry budget, so position identifies nothing.
    STAGES = (
        ("strategy", "You plan a nine message outreach sequence"),
        ("icp", "is this an agency"),
        ("extract", "extract"),
        ("hypothesis", "hypothesis"),
        ("match", "capability"),
        ("writer", "previous draft failed lint"),
    )

    def __init__(self, inner):
        self.inner = inner
        self.name = getattr(inner, "name", "unknown")
        self.calls = []

    @staticmethod
    def digest(text):
        return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]

    def label(self, prompt):
        low = str(prompt or "").lower()
        for name, marker in self.STAGES:
            if marker.lower() in low:
                return name
        return "unlabelled"

    def complete(self, prompt, temperature=0, client=None, config=None):
        answer = self.inner.complete(prompt, temperature=temperature,
                                     client=client, config=config)
        self.calls.append({"stage": self.label(prompt),
                           "prompt_sha": self.digest(prompt),
                           "prompt": prompt,
                           "answer_sha": self.digest(answer),
                           "chars": len(str(prompt))})
        return answer


# --------------------------------------------------------------- the matrix

#: The four runs, and the ONE thing each changes. Written as data so the
#: artifact reports the variable it actually applied rather than the one the
#: prose says it applied.
RUNS = {
    "A": {"label": "original",
          "variable": "nothing: this is the baseline",
          "expected": "the baseline artifact. No expectation to satisfy; "
                      "every other run is measured against it"},
    "A2": {"label": "original, repeated",
           "variable": "nothing, again",
           "expected": "THE CONTROL FOR THE WHOLE MATRIX. Identical inputs, so "
                       "every prompt must be byte-identical to run A's. If a "
                       "prompt moves here, no copy diff in B, C or D is "
                       "attributable to its variable"},
    "B": {"label": "one fact changed",
          "variable": "one research row's text: retained monthly engagements "
                      "becomes fixed price project work. Same account, same "
                      "domain, same contacts, same persona, same offer library",
          "expected": "the ANGLE and the COPY must both change. The changed row "
                      "is admitted research, so it reaches the extract and "
                      "hypothesis prompts and the writer's fact block"},
    "C": {"label": "persona switched",
          "variable": "the account persona: economic_buyer becomes the "
                      "operations persona. Nothing else",
          "expected": "the SELECTED OFFER must change from "
                      "OFFER-A-ECONOMIC-BUYER to OFFER-B-OPERATIONS, the "
                      "CAPABILITIES must change with it, and the step "
                      "objectives the gate enforces must change to Offer B's "
                      "ladder"},
    "D": {"label": "key evidence removed",
          "variable": "the research row the licensed claim traces to is "
                      "removed. Nothing else",
          "expected": "the CLAIM must disappear from the copy, or the lead must "
                      "HOLD. If the claim survives the removal of the evidence "
                      "that licensed it, the grounding is decorative"},
}


#: How many contacts each run generates for. 0 means every one the fixture
#: declares. It is a module global rather than a parameter threaded through four
#: functions because it must be IDENTICAL for every run in the matrix: a
#: baseline with three contacts compared against a variant with one would differ
#: for a reason that is not the variable.
CONTACT_CAP = 0


def record_for(run):
    """The fixture record as this run's variable leaves it."""
    rec = fixture.record()
    rec["persona"] = fixture.PERSONA_ECONOMIC_BUYER
    if CONTACT_CAP:
        rec["contacts"] = rec["contacts"][:CONTACT_CAP]
    if run == "C":
        rec["persona"] = fixture.PERSONA_OPERATIONS
        for contact in rec["contacts"]:
            contact["persona"] = fixture.PERSONA_OPERATIONS
    if run == "B":
        rows = [dict(fixture.FACT_CHANGED_B)
                if row["source_url"] == fixture.EVIDENCE_UNDER_TEST
                else dict(row)
                for row in fixture.RESEARCH]
        rec["research"] = fixture.research_rows(rec["id"], rows)
    if run == "D":
        rec["research"] = fixture.research_rows(
            rec["id"], [row for row in fixture.RESEARCH
                        if row["source_url"] != fixture.EVIDENCE_UNDER_TEST])
    return rec


def campaign_row(config):
    """One campaign, declaring the canonical five-plus-five itself.

    DECLARED, NOT INHERITED. `bisonfactory._plan` refuses a campaign carrying no
    `cadence_steps`, because the fallback through the client config is what once
    let a live campaign be staged against a cadence it never chose. And because
    this campaign is built by this run it gets the canonical ten steps rather
    than one of the sixty stale stored declarations launch blocker 9 counts.
    """
    row = campaigns.new_campaign(fixture.CAMPAIGN_ID, CLIENT,
                                 "TASK-425 one account dry run")
    row["cadence_steps"] = [dict(step) for step in
                            cadence.steps_for(None, config=config)]
    row["record_ids"] = [fixture.RECORD_ID]
    row["daily_volume"] = {"email": 5, "linkedin": 5}
    return row


def sequence_gate_validator(offer, rules):
    """The sequence gate's failures, as `generate()`'s `validate` callback.

    WHY THE LADDER IS ENFORCED FROM HERE AND NOT INSIDE THE LIBRARY.
    `generate_campaign` computes `result["sequence_gate"]` and its retry loop
    reads only `copylint`, so a sequence the gate refused is returned exactly
    like one it passed. Folding the gate into that loop would apply PRODUCTIVE's
    approved ladder to every client, because `offers.py` is single-tenant
    (`_offers_path()` resolves `productive-offers.yaml` whatever client is
    generating) - a worse fault than the one it fixes.

    `validate` is the seam built for exactly this: a caller that holds more
    context than the library returns extra failures and the whole set is
    REGENERATED, never patched. So the ladder is enforced for the one client
    whose ladder it is, by the caller who knows that.
    """

    def validate(result):
        gate = result.get("sequence_gate") or {}
        return ["sequencegate %s/%s: %s" % (f.get("check"), f.get("step"),
                                            f.get("why"))
                for f in gate.get("failures") or ()]

    return validate


def generate_one_run(run, model, config, wire):
    """One matrix run, through `generate.run()`, the production entrypoint.

    Returns everything the artifact needs and nothing it does not: the plan, the
    record as generation left it, the prompts, and the refusal if there was one.
    """
    rec = record_for(run)
    store.save([rec])
    pack, unused = packfacts.pack_for(rec)
    recorder = RecordingModel(model)

    outcome = {"run": run, **RUNS[run],
               "persona": rec.get("persona"),
               "research": [dict(row) for row in rec.get("research") or ()],
               "admitted_facts": [dict(f) for f in pack.get("facts") or ()],
               "client_supplied": [dict(f) for f in
                                   unused.get(packfacts.CLIENT_SUPPLIED) or ()],
               "refused_facts": [dict(f) for f in
                                 unused.get(packfacts.REFUSED) or ()],
               "unverifiable_facts": [dict(f) for f in
                                      unused.get(packfacts.UNVERIFIABLE) or ()],
               "error": None}

    # THE OFFER THIS RUN SELECTS, resolved the same way the pipeline resolves
    # it, so the artifact's "selected offer" line and the gate's verdict cannot
    # disagree.
    selected = generate_campaign._select_offers(
        rec.get("segment", CLIENT), rec.get("persona"))
    outcome["selected_offers"] = sorted(selected)
    offer = next(iter(selected.values())) if len(selected) == 1 else None
    outcome["offer"] = offer
    outcome["step_objectives"] = dict((offer or {}).get("step_objectives") or {})
    outcome["ai_capabilities"] = sorted((offer or {}).get("ai_capabilities")
                                        or {})
    outcome["capabilities"] = capabilities_for(rec.get("persona"), config)

    # THE LADDER, ENFORCED WHERE THE COPY IS WRITTEN. See the validator's
    # docstring for why it is the caller's job today.
    original_validator = generate._campaign_validator
    extra = sequence_gate_validator(offer, offers.messaging_rules())

    def both(rec_arg, client_config=None, campaign=None):
        inner = original_validator(rec_arg, client_config, campaign)

        def validate(result):
            return list(inner(result) or ()) + list(extra(result) or ())

        return validate

    # THE PLAN THE ENTRYPOINT RETURNED, CAPTURED WITHOUT CHANGING THE PATH.
    #
    # `generate.run()` is the production entrypoint and it returns a report, not
    # the SequencePlan - the plan is built inside `_generate_via_campaign` and
    # consumed there. Criterion 4 needs what is on it per contact: the extracted
    # facts, the hypothesis, the capability match, the qualification, the
    # per-attempt gate rejections. So the plan is recorded as it passes, and
    # `generate_campaign.generate` is otherwise untouched: the harness observes,
    # it does not substitute.
    captured = []
    real_generate = generate_campaign.generate

    def observing_generate(*a, **kw):
        plan = real_generate(*a, **kw)
        captured.append(plan)
        return plan

    generate_campaign.generate = observing_generate
    generate._campaign_validator = both
    try:
        generate.run(model=recorder, live=True, ids=[fixture.RECORD_ID])
    except Exception as exc:                                    # noqa: BLE001
        outcome["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:600])
        outcome["traceback"] = traceback.format_exc()[-1500:]
    finally:
        generate._campaign_validator = original_validator
        generate_campaign.generate = real_generate

    plan = captured[-1] if captured else {}
    outcome["plan_strategy"] = plan.get("strategy")
    outcome["plan_stamp"] = plan.get("generation_stamp")
    outcome["plan_contacts"] = [
        {"contact_key": c.get("contact_key"),
         "title": c.get("title"),
         "qualification": c.get("qualification"),
         "held": c.get("held"),
         "hold_kind": c.get("hold_kind"),
         "gate_attempts": c.get("gate_attempts"),
         "gate_rejections": c.get("gate_rejections"),
         "offer_id": c.get("offer_id"),
         "facts": c.get("facts"),
         "hypothesis": c.get("hypothesis"),
         "match": c.get("match"),
         "subjects": c.get("subjects"),
         "sequences": c.get("sequences"),
         "copylint": c.get("copylint"),
         "sequence_gate": c.get("sequence_gate")}
        for c in (plan.get("contacts") or ())]

    outcome["prompts"] = [{k: v for k, v in call.items() if k != "prompt"}
                          for call in recorder.calls]
    outcome["prompt_text"] = {"%s:%d" % (call["stage"], i): call["prompt"]
                              for i, call in enumerate(recorder.calls)}
    outcome["model_calls"] = len(recorder.calls)

    after = store.get(fixture.RECORD_ID) or {}
    outcome["generation_stamp"] = after.get("generation_stamp")
    outcome["cadence"] = json.loads(json.dumps(after.get("cadence") or {}))
    outcome["log"] = [entry for entry in (after.get("log") or ())
                      if entry.get("stage") in ("draft", "linkedin_note")][-12:]
    outcome["record_after"] = after
    return outcome


def capabilities_for(persona, config):
    """The capability sentences this persona's copy may name, from the client's
    own file. `cadence.product_words` is the one place that path is spelled
    out."""
    words = cadence.product_words({"persona": persona}, config)
    return {"capability": words.get("capability"),
            "capability_order": words.get("capability_order") or []}


# --------------------------------------------------------------- the staging


def approve_generated_copy(rec):
    """Stamp every generated step in the throwaway store. NOT an approval.

    See the module docstring. `approval.fingerprint` covers channel, subject,
    body and note, so the stamp certifies exactly the words present now and any
    later edit invalidates it - which is the property the staging gate relies on
    and the reason a placeholder fingerprint is refused.
    """
    stamped = []
    for contact_key, steps in (rec.get("cadence") or {}).items():
        if not isinstance(steps, dict):
            continue
        for step_key, step in steps.items():
            if not isinstance(step, dict) or not step.get("generated"):
                continue
            step["approval"] = {
                "by": FIXTURE_APPROVER,
                "at": "2026-09-28T00:00:00Z",
                "fingerprint": approval.fingerprint(step),
            }
            stamped.append("%s/%s" % (contact_key, step_key))
    return sorted(stamped)


def stage_email(config):
    """`bisonfactory.stage(live=False)`, and whatever it says.

    THE `sequencegate` KEY IS ASSERTED PRESENT BEFORE IT IS READ, because it is
    ABSENT for a zero-lead campaign in both modes - so
    `report.get("sequencegate", {}).get("passed")` is `None`, and `None` is not
    `True`. An artifact that rendered absence as a pass would make criterion 3
    decorative while looking satisfied.
    """
    out = {"refused": False, "why": None, "report": None,
           "sequencegate_present": False, "sequencegate": None,
           "sequencegate_leads_checked": 0, "sequencegate_vacuous": None,
           "copylint": None}
    try:
        report = bisonfactory.stage(fixture.CAMPAIGN_ID, config=config,
                                   live=False)
    except bisonfactory.FactoryRefused as refusal:
        out["refused"] = True
        out["why"] = str(refusal)
        report = refusal.report
    except Exception as exc:                                    # noqa: BLE001
        out["refused"] = True
        out["why"] = "%s: %s" % (type(exc).__name__, exc)
        out["traceback"] = traceback.format_exc()[-1500:]
        return out
    out["report"] = report
    if isinstance(report, dict):
        out["sequencegate_present"] = "sequencegate" in report
        out["sequencegate"] = report.get("sequencegate")
        out["copylint"] = report.get("copylint")
        # A VACUOUS PASS IS NOT A PASS, and it is a SECOND way this key lies.
        #
        # The brief's trap 1 is that `report["sequencegate"]` is absent for a
        # zero-lead campaign, so `.get("sequencegate", {}).get("passed")` is
        # `None`. Measured here, there is a deeper form: the key can be PRESENT
        # with `passed: True` and `leads: []`, because
        # `_refuse_sequence_gate` sets `{"passed": not refused, "leads":
        # checked}` and `checked` is empty when every lead carries no approved
        # copy - `refused` is then empty too, so `not refused` is True. A gate
        # that was asked about nobody reports the same verdict as a gate that
        # passed everybody. Counting the leads is what tells them apart.
        leads = (report.get("sequencegate") or {}).get("leads") or []
        out["sequencegate_leads_checked"] = len(leads)
        out["sequencegate_vacuous"] = bool(
            out["sequencegate_present"]
            and (report.get("sequencegate") or {}).get("passed") is True
            and not leads)
    return out


def stage_linkedin(config):
    """`heyreachfactory.stage(live=False)`, plus the graph projection.

    The graph is derived SEPARATELY as well, because `stage` refuses when no
    contact has approved copy for every role the graph requires - and the
    projection of the sequence still exists and is still what a provider would
    be written. A refusal is reported; it does not hide the projection.
    """
    out = {"refused": False, "why": None, "report": None, "graph": None,
           "touch_report": None, "plan": None}
    try:
        report = heyreachfactory.stage(fixture.CAMPAIGN_ID, config=config,
                                       live=False)
        out["report"] = report
    except heyreachfactory.FactoryRefused as refusal:
        out["refused"] = True
        out["why"] = str(refusal)
    except Exception as exc:                                    # noqa: BLE001
        out["refused"] = True
        out["why"] = "%s: %s" % (type(exc).__name__, exc)
        out["traceback"] = traceback.format_exc()[-1500:]

    rows = campaigns.load()
    row = campaigns.get(fixture.CAMPAIGN_ID, rows)
    try:
        plan = sequenceplan.for_campaign(
            row, config, cadence_steps=cadence.steps_for(row, config=config))
        graph, touch = sequenceplan.derive_heyreach_sequence(plan)
        out["plan"] = plan
        out["graph"] = graph
        out["touch_report"] = touch
    except Exception as exc:                                    # noqa: BLE001
        out["graph_error"] = "%s: %s" % (type(exc).__name__, exc)
    return out


def negative_test(config, rec):
    """Criterion 3's negative test, through the production staging path.

    THE LADDER IS BROKEN BY SWAPPING TWO STEPS AND NOTHING ELSE. em1 and em3
    exchange bodies and are re-stamped so the approval still certifies the words
    present, so the only property that changed is which rung each step pursues.
    Every other gate sees the same batch it just passed.

    The refusal has to be ATTRIBUTABLE. "it raised" would be satisfied by the
    cadence guard, the qualification check, the tenancy check or the copy lint,
    none of which is evidence that sequencing is enforced - so what is asserted
    is the gate by name, the check by name, and the steps.

    AND THE GATE MUST BE WHAT REFUSES. With `sequencegate.check` replaced by a
    verdict that passes everything, the identical broken campaign must reach the
    projection. If it does not, something else is refusing it and this proves
    nothing about the ladder.
    """
    from unittest import mock

    out = {"swapped": [], "refused": False, "why": None,
           "names_the_gate": False, "names_the_check": False,
           "names_the_steps": [], "gate_is_what_refuses": None,
           "bypassed_reached_projection": None}

    swapped = []
    for contact_key, steps in (rec.get("cadence") or {}).items():
        if not isinstance(steps, dict):
            continue
        one, three = steps.get("em1"), steps.get("em3")
        if not (isinstance(one, dict) and isinstance(three, dict)):
            continue
        one["body"], three["body"] = three.get("body"), one.get("body")
        for step in (one, three):
            step["approval"] = {"by": FIXTURE_APPROVER,
                                "at": "2026-09-28T00:00:00Z",
                                "fingerprint": approval.fingerprint(step)}
        swapped.append(contact_key)
    out["swapped"] = sorted(swapped)
    store.save([rec])

    try:
        bisonfactory.stage(fixture.CAMPAIGN_ID, config=config, live=False)
    except bisonfactory.FactoryRefused as refusal:
        out["refused"] = True
        out["why"] = str(refusal)
        out["names_the_gate"] = "sequence-level gate" in out["why"]
        out["names_the_check"] = "step_objectives" in out["why"]
        out["names_the_steps"] = [key for key in ("em1", "em3")
                                  if key in out["why"]]

    def passes_everything(sequence, **kwargs):
        return {"passed": True, "checks": [], "failures": [], "warnings": []}

    with mock.patch.object(sequencegate, "check", passes_everything):
        try:
            report = bisonfactory.stage(fixture.CAMPAIGN_ID, config=config,
                                        live=False)
            reached = len(((report or {}).get("plan") or {})
                          .get("provider_sequence") or ())
            out["bypassed_reached_projection"] = reached
            out["gate_is_what_refuses"] = reached > 0
        except Exception as exc:                                # noqa: BLE001
            out["bypassed_reached_projection"] = 0
            out["gate_is_what_refuses"] = False
            out["bypass_error"] = "%s: %s" % (type(exc).__name__,
                                              str(exc)[:400])
    return out


# ------------------------------------------------------- criterion 2, measured


SIGNATURE_FIELDS = ("sender_signature", "email_signature", "signature")


def signature_chain(email, config):
    """Criterion 2, measured end to end rather than assumed.

        mailbox owner -> sender_signature -> the rendered final message in the
        provider projection

    Every link is probed for a signature field by NAME, and what is reported is
    where the chain stops. No signature is synthesised: what a sender's
    signature says is the operator's and the client's decision, and inventing
    one would put words nobody approved at the bottom of every email.
    """
    from src import senderidentity, senders

    out = {"fields_searched": list(SIGNATURE_FIELDS)}

    # 1. THE LOCAL MAILBOX MODEL. `senderidentity.new_email_account` is what
    #    creates an inbox row in this system.
    account = senderidentity.new_email_account(
        "task425", "acct-1", "sender-1", "ada.sender@example.test",
        provider="emailbison")
    out["mailbox_row_keys"] = sorted(account)
    out["mailbox_has_signature_field"] = [f for f in SIGNATURE_FIELDS
                                          if f in account]

    # 2. THE CLIENT CONFIG'S SENDER BLOCK, the other place a signature could be
    #    declared for a cohort.
    sender_block = (config or {}).get("sender") or {}
    out["client_sender_block"] = dict(sender_block)
    out["client_has_signature_field"] = [f for f in SIGNATURE_FIELDS
                                         if f in sender_block]

    # 3. THE SENDER INVENTORY, in case a signature travels with the estate.
    try:
        inventory = senders.load()
    except Exception:                                           # noqa: BLE001
        inventory = []
    keys = set()
    for row in inventory or ():
        if isinstance(row, dict):
            keys.update(row)
    out["sender_inventory_rows"] = len(inventory or ())
    out["sender_inventory_keys"] = sorted(keys)
    out["inventory_has_signature_field"] = [f for f in SIGNATURE_FIELDS
                                            if f in keys]

    # 4. THE RENDERED FINAL MESSAGE IN THE PROVIDER PROJECTION. This is the one
    #    the criterion actually asks about: a populated field somewhere upstream
    #    is not the proof required.
    steps = ((email.get("report") or {}).get("plan") or {}).get(
        "provider_sequence") or []
    leads = ((email.get("report") or {}).get("plan") or {}).get("leads") or []
    rendered = []
    for step in steps:
        rendered.append({
            "step_key": step.get("step_key"),
            "subject": step.get("email_subject") or step.get("subject"),
            "body": step.get("email_body") or step.get("body"),
        })
    out["projection_step_keys"] = [s.get("step_key") for s in rendered]
    out["projection_step_fields"] = sorted({k for s in steps
                                            if isinstance(s, dict)
                                            for k in s})
    out["projection_has_signature_field"] = sorted(
        {f for s in steps if isinstance(s, dict) for f in SIGNATURE_FIELDS
         if f in s})
    last = rendered[-1] if rendered else {}
    out["final_rendered_step"] = last
    # A signature is TEXT at the foot of the rendered body. Looked for as text
    # as well as by field name, so a signature appended into the body rather
    # than carried in a field of its own would still be found.
    last_body = str(last.get("body") or "")
    out["final_rendered_body"] = last_body
    out["final_rendered_body_tail"] = last_body[-240:]
    out["lead_variable_names"] = sorted(
        {name for lead in leads for name in (lead.get("copy") and [] or [])})
    return out


# ------------------------------------------------------------------ the diffs


def diff_lines(before, after, label_before, label_after):
    return list(difflib.unified_diff(
        str(before or "").splitlines(), str(after or "").splitlines(),
        fromfile=label_before, tofile=label_after, lineterm="", n=1))


def copy_of(outcome, contact_key):
    steps = (outcome.get("cadence") or {}).get(contact_key) or {}
    return {key: (step or {}).get("body") or (step or {}).get("note") or ""
            for key, step in sorted(steps.items())
            if isinstance(step, dict)}


def prompt_shas(outcome):
    """Stage -> list of prompt digests, in call order."""
    out = {}
    for call in outcome.get("prompts") or ():
        out.setdefault(call["stage"], []).append(call["prompt_sha"])
    return out


def compare(base, other, contact_key):
    """What actually moved between two runs, measured rather than asserted."""
    base_copy, other_copy = copy_of(base, contact_key), copy_of(other,
                                                                contact_key)
    changed = sorted(key for key in set(base_copy) | set(other_copy)
                     if base_copy.get(key) != other_copy.get(key))
    return {
        "prompt_shas_before": prompt_shas(base),
        "prompt_shas_after": prompt_shas(other),
        "prompt_stages_changed": sorted(
            stage for stage in set(prompt_shas(base)) | set(prompt_shas(other))
            if prompt_shas(base).get(stage) != prompt_shas(other).get(stage)),
        "selected_offers_before": base.get("selected_offers"),
        "selected_offers_after": other.get("selected_offers"),
        "capabilities_before": base.get("capabilities"),
        "capabilities_after": other.get("capabilities"),
        "step_objectives_before": base.get("step_objectives"),
        "step_objectives_after": other.get("step_objectives"),
        "admitted_before": [f.get("snippet") for f in
                            base.get("admitted_facts") or ()],
        "admitted_after": [f.get("snippet") for f in
                           other.get("admitted_facts") or ()],
        "steps_whose_copy_changed": changed,
        "copy_identical": not changed,
        "em1_diff": diff_lines(base_copy.get("em1"), other_copy.get("em1"),
                               "A/em1", "%s/em1" % other.get("run")),
        "held_before": holds_of(base),
        "held_after": holds_of(other),
        "claim_before": claim_presence(base, contact_key),
        "claim_after": claim_presence(other, contact_key),
    }


def holds_of(outcome):
    out = {}
    for entry in outcome.get("log") or ():
        if "no draft passed lint" in str(entry.get("note") or ""):
            out[entry.get("note")[:200]] = True
    if outcome.get("error"):
        out["run error"] = outcome["error"]
    if not (outcome.get("cadence") or {}):
        out["no copy stored at all"] = True
    return sorted(out)


def claim_presence(outcome, contact_key):
    """Is the claim under test in this run's copy, and does it still trace?

    Criterion 1D asks whether the claim DISAPPEARS when the evidence goes. The
    honest measurement is two-sided: whether the phrase is in the copy, and
    whether `copylint.untraceable` still licenses it against this run's pack.
    """
    bodies = " ".join(copy_of(outcome, contact_key).values())
    pack = {"facts": [{"snippet": f.get("snippet")}
                      for f in outcome.get("admitted_facts") or ()]}
    return {
        "phrase": fixture.CLAIM_UNDER_TEST,
        "present_in_copy": fixture.CLAIM_UNDER_TEST.lower() in bodies.lower(),
        "untraceable_specifics": copylint.untraceable(bodies, pack),
        "pack_facts": len(pack["facts"]),
    }


# ---------------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/TASK-425-ARTIFACT.md")
    parser.add_argument("--json", default=None,
                        help="where to write the machine-readable artifact")
    parser.add_argument("--runs", default="A,A2,B,C,D")
    parser.add_argument("--model", default=POLICY_MODEL,
                        help="the model id to ask the endpoint for. Defaults to "
                             "the recorded policy model for prospect-facing "
                             "copy; pass an empty string to use LLM_MODEL as "
                             "the environment sets it")
    parser.add_argument("--contacts", type=int, default=0,
                        help="cap the contacts per run. 0 means all of them")
    parser.add_argument("--env", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", ".env"))
    args = parser.parse_args(argv)

    env_names, env_file = [], None
    for candidate in env_candidates(args.env):
        env_names = load_env(candidate)
        if env_names:
            env_file = candidate
            break
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    global CONTACT_CAP
    CONTACT_CAP = args.contacts
    wire = Wire()
    model_host = ""
    base = os.environ.get("LLM_BASE_URL") or ""
    if "//" in base:
        model_host = base.split("/")[2].lower()

    tmp = tempfile.mkdtemp(prefix="task425-")
    restore = store.use_directory(tmp)
    os.environ["OUT"] = os.path.join(tmp, "out")
    result = {
        "task": "TASK-425",
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "store": tmp,
        "env_file": env_file,
        "env_names": sorted(env_names),
        "model_host": model_host,
        "runs": {},
    }
    try:
        config = clients.load(CLIENT)
        result["client_config_sender"] = dict(config.get("sender") or {})
        result["cadence_name"] = config.get("cadence")
        result["cadence_steps"] = [dict(s) for s in
                                  cadence.steps_for(None, config=config)]

        # THE TENANT, WITH THE KILLSWITCH AS PRODUCTION HAS IT: `sending.live`
        # OFF. A dry run never reads it - `stage` returns above the workspace
        # read - and that is itself worth recording rather than assuming.
        workspace = workspaces.new_workspace(CLIENT, "Productive",
                                            client=CLIENT)
        workspace["settings"] = {"policy": {"sending.live": "off"}}
        workspaces.save([workspace])
        result["killswitch"] = killspace_state()

        model = llm.from_env()
        result["model"] = getattr(model, "name", "unknown")
        if isinstance(model, llm.NoModel):
            result["model_error"] = model_why_not()

        # ---------------------------------------------- phase 1: generation
        result["trap_generation"] = None
        wire.install(allow=model_host)
        result["trap_generation"] = wire.fire_the_trap()

        wanted = [r.strip() for r in args.runs.split(",") if r.strip()]
        for run in wanted:
            if run not in RUNS:
                continue
            campaigns.save([])
            store.save([])
            result["runs"][run] = generate_one_run(run, model, config, wire)

        # ------------------------------------------------- phase 2: staging
        # Run A is the one that is staged: the matrix measures generation, and
        # the projections are of the baseline artifact.
        store.save([])
        campaigns.save([])
        baseline = result["runs"].get("A")
        if baseline is not None:
            rec = baseline["record_after"]
            store.save([rec])
            campaigns.save([campaign_row(config)])
            result["fixture_approvals"] = approve_generated_copy(rec)
            store.save([rec])

            wire.install(allow=None)
            result["trap_staging"] = wire.fire_the_trap()

            result["email"] = stage_email(config)
            result["linkedin"] = stage_linkedin(config)
            result["signature_chain"] = signature_chain(result["email"],
                                                        config)
            result["suppression"] = suppression_of(rec, config)
            result["negative_test"] = negative_test(config, rec)

        result["spend"] = spend_report(config)
        result["wire"] = {
            "requests": wire.requests,
            "hosts": wire.hosts(),
            "provider_requests": wire.provider_requests(),
            "provider_request_count": len(wire.provider_requests()),
            "deliberate_trap_requests": wire.deliberate_trap_requests(),
        }
    finally:
        providers.reset_transport()
        restore()

    result["comparisons"] = {}
    baseline = result["runs"].get("A")
    if baseline:
        contact_key = fixture.CONTACT_UNDER_TEST
        for run in ("A2", "B", "C", "D"):
            other = result["runs"].get(run)
            if other:
                result["comparisons"][run] = compare(baseline, other,
                                                     contact_key)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=1, default=str)
    write_artifact(result, args.out)
    print("artifact:", args.out)
    print("provider requests:", len(wire.provider_requests()))
    return 0


def killspace_state():
    try:
        return killswitch.workspace_state(CLIENT)
    except Exception as exc:                                    # noqa: BLE001
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def model_why_not():
    try:
        return llm.OpenAICompatibleModel().why_not()
    except Exception as exc:                                    # noqa: BLE001
        return "%s: %s" % (type(exc).__name__, exc)


def suppression_of(rec, config):
    """What the canonical suppression resolver says about each contact.

    `eligibility.must_not_contact` is the public one precisely so it is not
    reimplemented, and it returns the five reason codes most-final first.
    """
    out = []
    for contact in rec.get("contacts") or ():
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        out.append({"contact": contact.get("key"),
                    "email": contact.get("email"),
                    "reasons": [r for r in reasons if r],
                    "may_contact": not any(reasons)})
    return out


def spend_report(config):
    try:
        return spendledger.report(client=CLIENT, config=config)
    except Exception as exc:                                    # noqa: BLE001
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def write_artifact(result, path):
    # `scripts/` is not a package (no `__init__.py`), so the sibling renderer is
    # imported off this file's own directory rather than through a package name
    # that does not exist.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import task425_artifact

    task425_artifact.write(result, path)


if __name__ == "__main__":
    sys.exit(main())
