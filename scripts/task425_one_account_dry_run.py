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
the account, its copy and its campaign row live in a temporary directory and the
production queue is never WRITTEN. `store.refuse_production_write` is the second
fence and would raise if this pointed at `work/` by accident.

**CORRECTED 2026-09-28, and the correction matters.** This paragraph used to say
"the production queue is never opened". That stopped being true when the matrix
moved onto the real account: `load_the_real_account()` opens it ONCE, READ ONLY,
BEFORE `store.use_directory()` - deliberately before, because after isolation
`store.get` reads the temp directory and the load would find nothing. So the
claim is now about writes, which is what the fences actually enforce, rather
than about opens, which they never did. A docstring that describes the previous
version of its own file is how a reader comes to trust the wrong fence.

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
import copy
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
        # A PROVIDER HOST MAY NEVER BE THE ALLOWED ONE.
        #
        # `allow` is read from `LLM_BASE_URL` and is the model endpoint, and
        # `fire_the_trap` POSTs to a real EmailBison campaigns route to prove the
        # trap is armed. If `allow` ever equalled an EmailBison host - a
        # misconfigured environment variable is enough - that trap firing would
        # be a real campaign creation, and `providers.refuse_unauthorized_write`
        # would not stop it because that route is not prospect-facing. Found by an
        # adversarial review as not-reachable-as-written, which is the kind of
        # thing that becomes reachable later.
        host = (allow or "").lower() or None
        if host and any(name in host for name in PROVIDER_HOSTS):
            raise AssertionError(
                "refusing to allow provider host %r through the transport: the "
                "trap is fired at a real EmailBison route on purpose, and an "
                "allowed provider host would make that a real write" % host)
        self.allow = host
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

    def __init__(self, inner):
        self.inner = inner
        self.name = getattr(inner, "name", "unknown")
        self.calls = []
        self.stages = self.stage_prompts()

    @staticmethod
    def stage_prompts():
        """Each stage's SYSTEM PROMPT, so a call is attributed exactly.

        NOT BY KEYWORD, and the first attempt shows why. `_call_model` builds
        `system + "\\n\\n" + user`, so the system prompt is a PREFIX of every
        call and matching it is exact. Matching a keyword instead - "hypothesis",
        "capability" - labelled the ICP stage `unlabelled` and the match and
        writer stages both `hypothesis`, because those words appear in more than
        one prompt. A stage attribution that is wrong makes the matrix's prompt
        diff meaningless while looking complete.

        NOT BY POSITION EITHER: the number of writer calls per contact varies
        with the retry budget, so a call index identifies nothing.

        The prompts are read from the same places the pipeline reads them - the
        skills for ICP, research and the writer, `copystages` for the two stages
        that have no skill - so a prompt edited next week is still attributed.
        """
        from src import copystages, skills

        out = []
        for stage, loader in (
                ("strategy", lambda: skills.load("campaign_strategy").procedure),
                ("icp", lambda: skills.load("signal_verification").procedure),
                ("extract", lambda: skills.load("account_research").procedure),
                ("hypothesis", lambda: copystages.HYPOTHESIS_SYSTEM),
                ("match", lambda: copystages.MATCH_SYSTEM),
                ("writer", lambda: skills.load("cold_email_writing").procedure),
        ):
            try:
                text = str(loader() or "")
            except Exception:                                   # noqa: BLE001
                text = ""
            if text:
                out.append((stage, text))
        # LONGEST PREFIX FIRST. Two system prompts could share an opening, and
        # the more specific one has to win.
        out.sort(key=lambda pair: -len(pair[1]))
        return out

    @staticmethod
    def digest(text):
        return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]

    def label(self, prompt):
        text = str(prompt or "")
        for stage, system in self.stages:
            if text.startswith(system):
                return stage
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


#: THE REAL ACCOUNT, LOADED ONCE FROM THE PRODUCTION STORE BEFORE THE STORE IS
#: ISOLATED. Every run deep-copies it; nothing writes back to it.
#:
#: `None` is never a usable value here. `the_account()` raises rather than
#: returning one, and `load_the_real_account` raises rather than substituting.
ACCOUNT = None

#: THE REAL CONTACT KEY, resolved from that record by
#: `fixture.contact_under_test`, which asks `verification.is_sendable` rather
#: than reading the contact's own `sendable` string.
CONTACT_KEY = None

#: Where the account was read from, recorded in the artifact so a reader can
#: tell which store a run actually used.
ACCOUNT_SOURCE = None


class TheRealAccountIsNotAvailable(SystemExit):
    """The store has no record for the selected account, so nothing may run.

    **THIS IS THE POINT OF THE WHOLE CHANGE, NOT A DEFENSIVE EXTRA.**

    The harness used to build every run from `fixture.record()` - an offline
    reconstruction of the account with a PLACEHOLDER contact on a reserved
    domain. Swapping that for `fixture.record_from_store()` is two lines. What
    those two lines cannot do is stop the next person being fooled when the
    store is empty, the `--queue` path is wrong, or a `git worktree` has its own
    stale `work/`: a silent fall back to the reconstruction produces a full set
    of plausible diffs, a complete artifact, and a matrix that answers a
    question nobody asked. It would look EXACTLY like a successful run.

    So the failure is loud, it is fatal, and its message names the record it
    looked for and every path it looked in. A sentence beats a quiet default.
    """


def load_the_real_account(queue_path=None):
    """Read the selected account from the PRODUCTION store, or refuse.

    CALLED BEFORE `store.use_directory(tmp)`, deliberately. After isolation
    `store.get` reads the temp directory, so a load placed one line later would
    find nothing and this refusal would fire on every run - correctly, and
    uselessly.

    Every candidate path is tried in order and every one is REPORTED in the
    refusal, because "the record is missing" and "I looked in the wrong
    checkout" are different problems and only the second is fixed by an
    argument. A `git worktree` is the usual reason: it has its own empty
    `work/`, which is exactly the shape that makes a fallback look like a pass.
    """
    global ACCOUNT, CONTACT_KEY, ACCOUNT_SOURCE

    tried, saved = [], os.environ.get("QUEUE")
    for candidate in queue_candidates(queue_path):
        tried.append(candidate)
        if not os.path.isfile(candidate):
            continue
        os.environ["QUEUE"] = candidate
        try:
            rec = fixture.record_from_store()
        finally:
            if saved is None:
                os.environ.pop("QUEUE", None)
            else:
                os.environ["QUEUE"] = saved
        if rec:
            ACCOUNT, ACCOUNT_SOURCE = rec, candidate
            CONTACT_KEY = fixture.contact_under_test(rec)
            if not CONTACT_KEY:
                raise TheRealAccountIsNotAvailable(
                    "TASK-425 REFUSES TO RUN: record %r was found in %s and "
                    "has no contact that `verification.is_sendable` accepts. "
                    "The matrix needs one eligible identity and the account "
                    "has none, so there is nothing to generate for. This is a "
                    "finding about the account, not a bug in the harness."
                    % (fixture.RECORD_ID, candidate))
            return ACCOUNT

    raise TheRealAccountIsNotAvailable(
        "TASK-425 REFUSES TO RUN: the real account could not be read, and the "
        "harness will NOT fall back to `fixture.record()`.\n"
        "  looked for record id : %s\n"
        "  account              : %s (%s)\n"
        "  queues tried         : %s\n"
        "The offline reconstruction in `tests/task425fixture.py` carries a "
        "PLACEHOLDER contact on a reserved domain. A matrix built on it would "
        "produce a complete artifact full of plausible diffs about a person "
        "who does not exist, and would be indistinguishable from a real run. "
        "Point --queue at the checkout that holds the estate."
        % (fixture.RECORD_ID, fixture.COMPANY, fixture.DOMAIN,
           "\n                         ".join(tried) or "(none)"))


def queue_candidates(path):
    """`work/queue.jsonl`, here or in the checkout this worktree belongs to.

    The same reasoning as `env_candidates`, for the same reason: `work/` is
    gitignored, so a `git worktree` created for one task has an EMPTY one, and
    the estate lives in the checkout that owns it. `--git-common-dir` is the
    shared `.git` of every worktree and its parent is that checkout.

    ## AN EXPLICIT `--queue` IS THE ONLY CANDIDATE, AND THAT IS NOT A DETAIL

    Found by this change's own refusal proof, which could not make the refusal
    fire: pointed at an EMPTY queue it searched on, found the real estate two
    candidates later, and returned the account. The search is right when nobody
    said where to look and wrong the moment somebody did - a mistyped `--queue`
    would silently read a different store, and the run would report an account
    the operator never asked for while its own artifact named the path they
    typed. So an explicit path is used alone, and if the record is not there the
    run stops.
    """
    if path:
        return [os.path.abspath(path)]

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = []
    if os.environ.get("QUEUE"):
        out.append(os.environ["QUEUE"])
    out.append(os.path.join(root, "work", "queue.jsonl"))
    common = os.environ.get("GIT_COMMON_DIR")
    if not common:
        import subprocess
        try:
            common = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                capture_output=True, text=True, timeout=15, cwd=root
            ).stdout.strip()
        except Exception:                                       # noqa: BLE001
            common = ""
    if common:
        owner = os.path.dirname(os.path.abspath(common))
        out.append(os.path.join(owner, "work", "queue.jsonl"))
    seen, unique = set(), []
    for candidate in out:
        resolved = os.path.abspath(candidate)
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def contact_under_test():
    """The REAL contact key, or a refusal. Never the placeholder.

    `fixture.CONTACT_UNDER_TEST` is a declared placeholder on a reserved
    domain, and matching stored cadence keys against it would match NOTHING -
    so every run would report `contact_under_test_stored: 0`, every comparison
    would read NOT COMPARABLE, and the matrix would look like a copy-engine
    failure rather than a wiring one.
    """
    if not CONTACT_KEY:
        raise TheRealAccountIsNotAvailable(
            "TASK-425 REFUSES TO RUN: no real contact key is resolved. "
            "`load_the_real_account()` must run before anything asks which "
            "identity the matrix is driven on, and it must never be answered "
            "with `fixture.CONTACT_UNDER_TEST`, which is a placeholder.")
    return CONTACT_KEY


def the_account():
    """The loaded account, or a refusal. Never `None`, never a substitute."""
    if ACCOUNT is None:
        raise TheRealAccountIsNotAvailable(
            "TASK-425 REFUSES TO RUN: `load_the_real_account()` was never "
            "called, so no account is loaded. This is a programming error in "
            "the harness rather than a state of the estate - it must be called "
            "BEFORE `store.use_directory()`, because after isolation "
            "`store.get` reads the temp directory.")
    return copy.deepcopy(ACCOUNT)


#: WHICH RESEARCH ROW RUN D REMOVES, discovered from run A rather than chosen.
#:
#: The criterion is "a key piece of evidence removed - the claim disappears, or
#: the lead HOLDs". A row chosen in advance is only KEY if the copy happens to
#: lean on it, and the first version of this run chose one that the copy did not:
#: the phrase under test appeared in NEITHER run A's copy nor run D's, so its
#: absence in D proved nothing and the criterion read BLOCKED for a reason that
#: was about the fixture rather than about the system.
#:
#: So run A is measured first, `licensing_fact_of` asks `copylint`'s own
#: machinery which admitted fact licensed a specific in the copy it actually
#: produced, and run D removes THAT row. The evidence is key by measurement.
EVIDENCE_TO_REMOVE = {"source_url": None, "specifics": [], "why": None}


def record_for(run):
    """THE REAL ACCOUNT as this run's variable leaves it.

    A deep copy of the record the estate holds, never the offline
    reconstruction - see `TheRealAccountIsNotAvailable`.

    ## B AND D MUTATE THE ACCOUNT'S OWN ROWS, NOT THE FIXTURE'S

    This function used to rebuild `rec["research"]` for runs B and D out of
    `fixture.RESEARCH`, which was correct while every run started from
    `fixture.record()` and is now the most dangerous line in the file: run A
    would carry the estate's research and runs B and D a committed
    reconstruction of it, so two thirds of the matrix would differ from its own
    baseline for a reason that is not the variable. Every row below therefore
    comes from THIS RECORD, filtered or replaced in place.

    Run B's replacement fact is the one thing that cannot come from the store -
    it is the alternative real fact the fixture nominates - so it is built
    through `fixture.research_rows`, which stamps it for this record and scores
    it exactly as `evidence.make` scores every other row.
    """
    rec = the_account()
    rec["persona"] = fixture.PERSONA_ECONOMIC_BUYER
    if CONTACT_CAP:
        rec["contacts"] = rec["contacts"][:CONTACT_CAP]
    if run == "C":
        rec["persona"] = fixture.PERSONA_OPERATIONS
        for contact in rec["contacts"]:
            contact["persona"] = fixture.PERSONA_OPERATIONS
    if run == "B":
        # ONE FACT REPLACED, IN PLACE. Order is preserved because
        # `copyprompts._numbered` prints the sources in list order and a
        # reordered source block is a prompt diff that is not the variable.
        made = fixture.research_rows(rec["id"], [fixture.FACT_CHANGED_B])
        rows, swapped = [], False
        for row in rec.get("research") or ():
            if (row or {}).get("source_url") == fixture.EVIDENCE_UNDER_TEST:
                rows.extend(made)
                swapped = True
            else:
                rows.append(row)
        if not swapped:
            raise TheRealAccountIsNotAvailable(
                "TASK-425 REFUSES TO RUN run B: the record holds no research "
                "row for %s, so there is nothing to replace and B would be a "
                "no-op reported as a changed fact."
                % fixture.EVIDENCE_UNDER_TEST)
        rec["research"] = rows
    if run == "D":
        # The row run A's own copy leaned on, or the fixture's nominated one if
        # run A produced no licensed claim at all. Either way it is RECORDED.
        remove = (EVIDENCE_TO_REMOVE.get("source_url")
                  or fixture.EVIDENCE_UNDER_TEST)
        kept = [row for row in rec.get("research") or ()
                if (row or {}).get("source_url") != remove]
        if len(kept) == len(rec.get("research") or ()):
            raise TheRealAccountIsNotAvailable(
                "TASK-425 REFUSES TO RUN run D: the record holds no research "
                "row for %s, so D would remove nothing and its result would "
                "be a copy of run A reported as an evidence removal." % remove)
        rec["research"] = kept
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


#: HOW MANY TIMES THE ENTRYPOINT IS INVOKED BEFORE A RUN IS CALLED HELD.
#:
#: `generate_campaign` already regenerates up to `MAX_WRITER_ATTEMPTS` (3) times
#: inside ONE invocation, feeding the failure back each time. This is the outer
#: loop an operator performs by hand: run it again.
#:
#: IT EXISTS BECAUSE THE COPY PATH IS GENUINELY MARGINAL ON THIS ACCOUNT, and
#: that is a finding rather than a nuisance. Measured 2026-09-28 across repeated
#: invocations of the identical input: some produced a full ten-step sequence
#: that passed every gate, and others held on one sentence - a dash, a
#: second-person operational assertion, an AI capability at the wrong rung. The
#: number of invocations each run needed is REPORTED, so the artifact says how
#: often the system converges rather than implying it always does.
DEFAULT_INVOCATIONS = 4


def generate_one_run(run, model, config, wire, invocations=1):
    """One matrix run, through `generate.run()`, the production entrypoint.

    Returns everything the artifact needs and nothing it does not: the plan, the
    record as generation left it, the prompts, and the refusal if there was one.
    """
    # EACH RUN DECIDES ITS OWN STRATEGY, and without this the matrix would lie.
    #
    # `campaignstrategy.for_segment` caches by `(segment_key, persona)` and calls
    # the model AT MOST ONCE per combination for the life of the process - which
    # is correct for production and fatal for a matrix in one process. Runs A, A2,
    # B and D share a persona, so only A would render a strategy prompt and every
    # other run's prompt list would be MISSING that stage. `prompt_shas` would
    # then report the strategy stage as "changed" between A and A2, the control
    # would read BLOCKED, and no diff in B, C or D would be attributable to
    # anything.
    #
    # Cleared rather than worked around, because the artifact has to be able to
    # say what strategy each run decided, and a cache hit decides none.
    from src import campaignstrategy as _campaignstrategy
    _campaignstrategy._strategy_cache.clear()

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
    attempts = []
    try:
        for invocation in range(1, max(1, invocations) + 1):
            # THE RECORD IS RESET BEFORE EACH INVOCATION, because
            # `_protected_reason` will not overwrite a stored step and a
            # half-written record from a refused invocation would make the next
            # one look like a partial success.
            #
            # THE HISTORY IS CARRIED FORWARD, and `store.save` is right to insist.
            # A fresh copy of the fixture record is a STALE SNAPSHOT of a record
            # that has since accumulated events, and writing it back drops them:
            # `store.refuse_history_loss` raised `HistoryLost: 9 event(s)
            # dropped` on the fourth invocation and ended the whole run.
            #
            # That guard exists because a concurrent run once checkpointed a
            # snapshot loaded before a "remove us from your list" reply, and the
            # events and the pause were gone. It has no opt-out and should not:
            # this harness is the caller in the wrong, not the guard. So the
            # reset clears the CADENCE and the stamp - the two things a fresh
            # invocation must not inherit - and carries `events` and `log`
            # forward from whatever is stored.
            fresh = record_for(run)
            held = store.get(fixture.RECORD_ID) or {}
            for key in ("events", "log"):
                if held.get(key):
                    fresh[key] = held[key]
            # WHERE THIS INVOCATION'S OWN LOG STARTS. The log is carried forward,
            # so reading the whole of it afterwards would attribute invocation
            # one's hold to invocation three and the artifact would report the
            # same refusal three times as though it had recurred.
            log_from = len(fresh.get("log") or ())
            store.save([fresh])
            try:
                generate.run(model=recorder, live=True,
                             ids=[fixture.RECORD_ID])
                outcome["error"] = None
            except Exception as exc:                            # noqa: BLE001
                outcome["error"] = "%s: %s" % (type(exc).__name__,
                                               str(exc)[:600])
                outcome["traceback"] = traceback.format_exc()[-1500:]
            after = store.get(fixture.RECORD_ID) or {}
            stored = sorted(
                "%s/%s" % (ck, key)
                for ck, steps in (after.get("cadence") or {}).items()
                if isinstance(steps, dict) for key in steps)
            # THE RUN IS DONE WHEN THE CONTACT UNDER TEST HAS COPY, not when ANY
            # contact does.
            #
            # "Everything else constant" includes WHO the copy is for. Breaking on
            # any contact let run A land on the Managing Director and run A2 land
            # on the Head of Delivery, so the control compared two different
            # people's messages and every step read as changed. Measured
            # 2026-09-28: A and B stored c1, A2, C and D stored c3, and the copy
            # diff between A and A2 was every step - for no reason that was about
            # the system.
            #
            # A run that never gets the contact under test through says so, and
            # its comparison is marked NOT COMPARABLE rather than being read as a
            # diff.
            wanted = [key for key in stored
                      if key.startswith(contact_under_test() + "/")]
            attempts.append({"invocation": invocation,
                             "steps_stored": len(stored),
                             "contacts_stored": sorted({key.split("/")[0]
                                                        for key in stored}),
                             "contact_under_test_stored": len(wanted),
                             "error": outcome.get("error"),
                             "held": [entry.get("note")
                                      for entry in (after.get("log")
                                                    or ())[log_from:]
                                      if "no draft passed lint"
                                      in str(entry.get("note") or "")]})
            if wanted:
                break
    finally:
        generate._campaign_validator = original_validator
        generate_campaign.generate = real_generate

    outcome["invocations"] = attempts
    outcome["invocations_used"] = len(attempts)
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


def projections_of(email, linkedin):
    """EVERY projection of the one canonical plan, from the plan.

    `docs/OPERATING-MODE.md`, ARCHITECTURAL INVARIANTS, ONE TRUTH: "Preview,
    XLSX, provider adapters, approval and QA are PROJECTIONS of one canonical
    plan, never second implementations." The task's own path names five - the
    EmailBison projection, the HeyReach projection, the APPROVAL projection, the
    preview and the plan itself - so all of them are derived here from the SAME
    plan object, and the artifact can show that they agree because there is
    nothing for them to disagree with.

    Each is attempted separately and a refusal is recorded rather than allowed to
    take the others down: a projection that refuses is a finding about that
    projection.
    """
    plan = ((email.get("report") or {}).get("plan") or {}).get("sequence_plan")
    out = {"from_plan": bool(plan)}
    if not plan:
        # The LinkedIn side built its own copy of the plan when the email side
        # refused before the projection, so fall back to that rather than
        # reporting nothing.
        plan = linkedin.get("plan")
        out["from_plan"] = False
        out["note"] = ("the EmailBison report carried no `sequence_plan`, so "
                       "these are derived from the plan the LinkedIn path built "
                       "for the same campaign")
    if not plan:
        out["error"] = "no canonical plan was built by either path"
        return out
    for name, call in (
            ("approval_hash", lambda: sequenceplan.approval_hash(plan)),
            ("preview", lambda: sequenceplan.derive_preview_data(plan)),
            ("bison_payload", lambda: sequenceplan.derive_bison_payload(plan)),
            ("heyreach_payload",
             lambda: sequenceplan.derive_heyreach_payload(plan)),
    ):
        try:
            out[name] = call()
        except Exception as exc:                                # noqa: BLE001
            out[name] = {"refused": "%s: %s" % (type(exc).__name__,
                                                str(exc)[:400])}
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
    import copy as _copy
    from unittest import mock

    ORDER = ("em1", "em2", "em3", "em4", "em5")

    def restamp(step):
        step["approval"] = {"by": FIXTURE_APPROVER,
                            "at": "2026-09-28T00:00:00Z",
                            "fingerprint": approval.fingerprint(step)}

    def mutate(kind):
        """The record with its email bodies moved, and nothing else changed."""
        moved = _copy.deepcopy(rec)
        touched = []
        for contact_key, steps in (moved.get("cadence") or {}).items():
            if not isinstance(steps, dict):
                continue
            bodies = {key: (steps.get(key) or {}).get("body")
                      for key in ORDER if isinstance(steps.get(key), dict)}
            if len(bodies) < len(ORDER):
                continue
            if kind == "rotation":
                # EVERY RUNG GETS THE NEXT RUNG'S WORDS. The canonical "ladder
                # out of order": no step keeps any of its own objective, so
                # every rung's vocabulary is at a step that is not its own.
                for position, key in enumerate(ORDER):
                    steps[key]["body"] = bodies[ORDER[(position + 1)
                                                     % len(ORDER)]]
            else:
                steps["em1"]["body"], steps["em3"]["body"] = (
                    bodies["em3"], bodies["em1"])
            for key in ORDER:
                restamp(steps[key])
            touched.append(contact_key)
        return moved, sorted(touched)

    def stage_and_read(kind, watched):
        moved, touched = mutate(kind)
        store.save([moved])
        found = {"mutation": kind, "contacts_mutated": touched,
                 "refused": False, "why": None, "names_the_gate": False,
                 "names_the_check": False, "names_the_steps": []}
        try:
            bisonfactory.stage(fixture.CAMPAIGN_ID, config=config, live=False)
        except bisonfactory.FactoryRefused as refusal:
            found["refused"] = True
            found["why"] = str(refusal)
            found["names_the_gate"] = "sequence-level gate" in found["why"]
            found["names_the_check"] = "step_objectives" in found["why"]
            found["names_the_steps"] = [key for key in watched
                                        if key in found["why"]]
        return found

    # THE PRIMARY NEGATIVE TEST IS THE ROTATION, and the swap is reported beside
    # it because the two measure different sensitivities. The order check refuses
    # when a rung's vocabulary sits at another step and is ABSENT from its own;
    # a rotation guarantees that for every rung, while a single swap of two steps
    # whose real copy happens to share vocabulary may not. Reporting both is the
    # honest way to state how sharp the check is, rather than picking the
    # mutation that refuses and calling the gate proved.
    out = {"primary": stage_and_read("rotation", ORDER),
           "secondary": stage_and_read("swap", ("em1", "em3")),
           "gate_is_what_refuses": None,
           "bypassed_reached_projection": None}

    # AND THE GATE MUST BE WHAT REFUSES. Asserting on the message is not enough:
    # the message is built from the gate's own report, so a gate refusing for the
    # wrong reason still names itself. What is measured is an EFFECT - with
    # `sequencegate.check` replaced by a verdict that passes everything, the
    # identical broken campaign must reach the dry-run projection.
    moved, _touched = mutate("rotation")
    store.save([moved])

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

    # THE RECORD IS PUT BACK. The negative test is the LAST thing the run does
    # to the store, but leaving a mutated record behind would make any later
    # reader of this directory believe the artifact's copy was the rotated copy.
    store.save([rec])
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
    plan = (email.get("report") or {}).get("plan") or {}
    steps = plan.get("provider_sequence") or []
    leads = plan.get("leads") or []
    out["projection_step_keys"] = [s.get("step_key") for s in steps
                                   if isinstance(s, dict)]
    out["projection_step_fields"] = sorted({k for s in steps
                                            if isinstance(s, dict)
                                            for k in s})
    out["projection_has_signature_field"] = sorted(
        {f for s in steps if isinstance(s, dict) for f in SIGNATURE_FIELDS
         if f in s})

    # THE MESSAGE AS THE PROSPECT WOULD READ IT, NOT THE TEMPLATE.
    #
    # The criterion asks for the signature "in the rendered final message in the
    # provider projection", and the projection's steps are a TEMPLATE of merge
    # fields - `{SUBJECT_1}`, `{BODY_5}`. The words travel per lead in custom
    # variables, so the rendered message is the template with this lead's
    # variables resolved. Rendering it here is the only way the criterion can be
    # answered at all: reporting `<p>{BODY_5}</p>` and calling the signature
    # absent would be true of every campaign ever staged and would prove
    # nothing.
    #
    # `_variables_for` is `bisonfactory`'s own function, so what is rendered is
    # exactly what the provider would be told.
    rows = campaigns.load()
    campaign = campaigns.get(fixture.CAMPAIGN_ID, rows)
    rendered = []
    for lead in leads:
        # `_variables_for` returns the PROVIDER's shape - a list of
        # `{"name", "value"}` rows, because that is what `create_lead` takes -
        # so it is folded back into a mapping to render with. Reading it as a
        # dict raised `TypeError: '<' not supported between instances of
        # 'dict' and 'dict'`, which is the honest way a wrong assumption about a
        # provider shape announces itself.
        values = {row.get("name"): row.get("value")
                  for row in bisonfactory._variables_for(lead, campaign, steps)
                  if isinstance(row, dict)}
        out["lead_variable_names"] = sorted(values)
        for step in steps:
            if not isinstance(step, dict):
                continue
            subject = str(step.get("email_subject") or "")
            body = str(step.get("email_body") or "")
            for name, value in values.items():
                subject = subject.replace("{%s}" % name.upper(), str(value))
                body = body.replace("{%s}" % name.upper(), str(value))
            rendered.append({"lead": "%s/%s" % (lead.get("record_id"),
                                                lead.get("contact_key")),
                             "step_key": step.get("step_key"),
                             "thread_reply": step.get("thread_reply"),
                             "subject": subject, "body": body})
    out["rendered_messages"] = rendered
    last = rendered[-1] if rendered else {}
    out["final_rendered_step"] = {k: v for k, v in last.items()
                                  if k != "body"}
    # A signature is TEXT at the foot of the rendered body, so it is looked for
    # as text as well as by field name: a signature appended into the body rather
    # than carried in a field of its own would still be found.
    last_body = str(last.get("body") or "")
    out["final_rendered_body"] = last_body
    out["final_rendered_body_tail"] = last_body[-300:]
    out["any_rendered_body_names_the_sender"] = sorted(
        {r["step_key"] for r in rendered
         if str((config.get("sender") or {}).get("name") or "\0")
         in str(r.get("body") or "")})
    out["still_unrendered_variables"] = sorted(
        {token for r in rendered
         for token in re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}",
                                 str(r.get("body") or "")
                                 + str(r.get("subject") or ""))})
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
    """Stage -> the digest of the FIRST prompt that stage was asked.

    THE FIRST ONE ONLY, and that is what makes the comparison valid. A stage's
    later prompts carry `RETRY_BLOCK` with whatever the previous draft failed,
    so two runs that needed a different number of attempts would differ in
    prompts for a reason that is not the variable under test. The first prompt of
    each stage is a pure function of the inputs, which is exactly the property
    the causal matrix needs of it.
    """
    out = {}
    for call in outcome.get("prompts") or ():
        out.setdefault(call["stage"], call["prompt_sha"])
    return out


#: WHICH PROMPT STAGES ARE PURE FUNCTIONS OF THE INPUTS, and this distinction is
#: the whole basis of the matrix's control.
#:
#: `strategy`, `icp` and `extract` are rendered from the account, the domain, the
#: persona and the admitted research and from nothing else, so the same inputs
#: render the same bytes every time. Everything after them is rendered from a
#: MODEL'S ANSWER: `hypothesis` reads the extract's facts, `match` reads the
#: hypothesis, and the writer reads the strategy, the hypothesis and the match.
#: Two runs with identical inputs therefore DO differ in those prompts, and that
#: is the model's variance rather than a causal signal.
#:
#: So the control asserts the deterministic stages are byte-identical, and the
#: model-dependent ones are reported as the measured noise floor. Asserting that
#: nothing at all moved would be asserting the model is deterministic, which it
#: is not, and the artifact would read BLOCKED for a reason that is not about the
#: system.
DETERMINISTIC_STAGES = ("strategy", "icp", "extract")


def compare(base, other, contact_key):
    """What actually moved between two runs, measured rather than asserted."""
    base_copy, other_copy = copy_of(base, contact_key), copy_of(other,
                                                                contact_key)
    changed = sorted(key for key in set(base_copy) | set(other_copy)
                     if base_copy.get(key) != other_copy.get(key))
    before, after = prompt_shas(base), prompt_shas(other)
    moved = sorted(stage for stage in set(before) | set(after)
                   if before.get(stage) != after.get(stage))
    return {
        "prompt_shas_before": before,
        "prompt_shas_after": after,
        "prompt_stages_changed": moved,
        "deterministic_stages_changed": [s for s in moved
                                         if s in DETERMINISTIC_STAGES],
        "model_dependent_stages_changed": [s for s in moved
                                           if s not in DETERMINISTIC_STAGES],
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
        "claim_before": claim_presence(base, contact_key, EVIDENCE_TO_REMOVE),
        "claim_after": claim_presence(other, contact_key, EVIDENCE_TO_REMOVE),
        "contact_compared": contact_key,
        "comparable": (contact_key in (base.get("cadence") or {})
                       and contact_key in (other.get("cadence") or {})),
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


def pack_of(outcome):
    return {"facts": [{"snippet": f.get("snippet")}
                      for f in outcome.get("admitted_facts") or ()]}


def licensing_fact_of(outcome, contact_key):
    """WHICH admitted fact licensed a specific in the copy this run produced.

    Through `copylint`'s own machinery, one fact at a time, so the answer is the
    gate's rather than a resemblance this script invented. Returns
    `{"source_url", "specifics", "why"}` for the fact that licensed the most
    specifics, or an empty answer when the copy asserts nothing checkable about
    the prospect - which is itself worth reporting, because then no evidence is
    load-bearing and criterion D has nothing to remove.
    """
    bodies = copy_of(outcome, contact_key)
    admitted = outcome.get("admitted_facts") or []
    tally = {}
    for body in bodies.values():
        for sentence in re.split(r"(?<=[.!?])\s+", str(body or "")):
            if not copylint.COMPANY_CLAIM.search(sentence):
                continue
            for value in copylint.specifics_in(sentence):
                for fact in admitted:
                    one = copylint._pack_sentences(
                        {"facts": [{"snippet": fact.get("snippet")}]})
                    if copylint._traces(value, one, sentence):
                        entry = tally.setdefault(fact.get("source_url"), [])
                        if value not in entry:
                            entry.append(value)
                        break
    if not tally:
        return {"source_url": None, "specifics": [],
                "why": "run A's copy asserts no checkable specific about the "
                       "prospect, so no admitted fact is load-bearing and there "
                       "is nothing for criterion D to remove"}
    best = max(sorted(tally), key=lambda url: len(tally[url]))
    return {"source_url": best, "specifics": tally[best],
            "why": "this fact licensed %d specific(s) in run A's copy: %s"
                   % (len(tally[best]), ", ".join(map(repr, tally[best])))}


def claim_presence(outcome, contact_key, removed=None):
    """What this run's copy claims, and whether the removed evidence mattered.

    Criterion 1D asks whether the claim DISAPPEARS when the evidence goes. Three
    measurements, all through `copylint.untraceable`:

      specifics_licensed   what this run's copy asserts and its own pack licenses
      untraceable_specifics  what its own pack does NOT license. Non-empty means
                             the copy would be REFUSED, which is the lead holding
      would_be_refused_without  this copy re-linted against the pack MINUS the
                             removed row. Non-empty proves the removed evidence
                             was LOAD-BEARING for this copy, which is the half
                             that makes D a real test rather than a diff
    """
    bodies = " ".join(copy_of(outcome, contact_key).values())
    pack = pack_of(outcome)
    found = {
        "removed_evidence": removed,
        "specifics_in_copy": copylint.specifics_in(bodies),
        "untraceable_specifics": copylint.untraceable(bodies, pack),
        "pack_facts": len(pack["facts"]),
    }
    if removed and removed.get("source_url"):
        reduced = {"facts": [
            {"snippet": fact.get("snippet")}
            for fact in outcome.get("admitted_facts") or ()
            if fact.get("source_url") != removed["source_url"]]}
        found["would_be_refused_without_it"] = copylint.untraceable(bodies,
                                                                   reduced)
        found["specifics_it_licensed"] = [
            value for value in (removed.get("specifics") or ())
            if value.lower() in bodies.lower()]
    return found


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
    parser.add_argument("--invocations", type=int,
                        default=DEFAULT_INVOCATIONS,
                        help="how many times the entrypoint is invoked before a "
                             "run is called held. Each invocation already "
                             "regenerates three times internally")
    parser.add_argument("--env", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", ".env"))
    parser.add_argument("--queue", default=None,
                        help="the production work/queue.jsonl holding the "
                             "selected account. Omit to try this checkout and "
                             "then the checkout that owns this worktree. The "
                             "run REFUSES rather than falling back to the "
                             "fixture's offline reconstruction")
    parser.add_argument("--usd-ceiling", type=float, default=10.00,
                        help="stop the run when model spend reaches this many "
                             "US dollars. Operator decision, Zvonimir "
                             "2026-09-28: USD 10 per matrix run. Enforced "
                             "through spendledger's own per_run reservation, "
                             "not by a second mechanism here")
    args = parser.parse_args(argv)

    env_names, env_file = [], None
    for candidate in env_candidates(args.env):
        env_names = load_env(candidate)
        if env_names:
            env_file = candidate
            break
    if args.model:
        os.environ["LLM_MODEL"] = args.model

    # THE RUN REFUSES TO START AGAINST A MODEL NOBODY HAS PRICED.
    #
    # Operator decision, Zvonimir 2026-09-28: "fix the model-name price
    # mismatch first so the cap is measurable; the run starts only after a
    # dollar total is verified non-zero on a test call."
    #
    # This is that condition made structural rather than remembered. An
    # unpriced model ledgers every completion at expected_cost=0, so a USD
    # ceiling over it is arithmetic on zero - the cap would read as never
    # reached no matter what was spent. That is exactly what happened to the
    # previous matrix: 287 ledger rows, expected_total 0, and the artifact
    # warning in its own text that zero did not mean nothing was spent.
    #
    # The cause was a NAME, not a missing price: the harness asks for
    # "anthropic/claude-sonnet-4" while `config/model-prices.yaml` keyed the
    # same model as "claude-sonnet-4-20250514", and `price_for` is an exact
    # lookup. Both keys now exist, each with its own source and as_of.
    from src import modelprices as _prices

    _asked = os.environ.get("LLM_MODEL") or ""
    _priced = _prices.price_for(_asked)
    if _priced is None:
        raise SystemExit(
            "REFUSING TO START: the model %r is not in "
            "config/model-prices.yaml, so every call would ledger at zero and "
            "the --usd-ceiling of %.2f could never be reached however much was "
            "spent. Price it - with its source and as_of - or pass --model "
            "with a priced id. A missing price is not a free call."
            % (_asked, args.usd_ceiling))
    # Proof the arithmetic is live, not just that a key exists: a
    # representative call must cost more than zero.
    _probe = _prices.cost_micro_usd(_asked, {"prompt_tokens": 5000,
                                             "completion_tokens": 1000})
    if _probe <= 0:
        raise SystemExit(
            "REFUSING TO START: %r resolves a price row but a representative "
            "call still costs 0 micro-USD, so the ceiling is unenforceable."
            % _asked)

    global CONTACT_CAP
    CONTACT_CAP = args.contacts
    wire = Wire()
    model_host = ""
    base = os.environ.get("LLM_BASE_URL") or ""
    if "//" in base:
        model_host = base.split("/")[2].lower()

    # THE REAL ACCOUNT, BEFORE THE STORE IS ISOLATED, AND BEFORE ANYTHING ELSE.
    #
    # Order is the whole of it. `store.use_directory(tmp)` on the next line
    # repoints `QUEUE` at an empty temp directory, so a load placed after it
    # reads nothing. Loading here means the run either has the account the
    # estate holds, or it stops with a sentence - and it can never quietly
    # continue on `fixture.record()`, whose contact is a placeholder on a
    # reserved domain.
    load_the_real_account(args.queue)

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
        # WHICH ACCOUNT, WHICH IDENTITY, AND WHICH STORE IT CAME OUT OF.
        # Recorded so a reader never has to infer from the prose which record a
        # run used, and so `scripts/task425_criterion4_completeness.py` has a
        # real contact key to read instead of the fixture's placeholder.
        "account": {"record_id": fixture.RECORD_ID,
                    "company": fixture.COMPANY,
                    "domain": fixture.DOMAIN,
                    "source_queue": ACCOUNT_SOURCE,
                    "contact_under_test": CONTACT_KEY,
                    "from_the_store": True},
        "runs": {},
    }
    try:
        config = clients.load(CLIENT)

        # THE CEILING, ENFORCED BY THE MECHANISM THAT ALREADY EXISTS.
        #
        # `spendledger` enforces `per_run` by reservation and reads it from the
        # client's declared ceilings. Production declares none (`per_run: null`
        # on the previous matrix), which is why nothing stopped a run that
        # looped - one earlier attempt was killed by hand at ~470 model calls.
        #
        # This sets it on the harness's OWN in-memory copy of the config, so
        # the ceiling binds THIS run and nothing else. Writing it into
        # `config/clients/productive.yaml` would cap every run the client ever
        # makes, including enrichment passes that legitimately spend more -
        # a side effect the operator did not ask for, from a decision that
        # named "per matrix run".
        #
        # Units are $-cents, the same unit the client block's `per_day` uses.
        from src import spendledger as _ledger

        _declared = dict(config.get(_ledger.CONFIG_KEY) or {})
        _declared["per_run"] = int(round(args.usd_ceiling * 100))
        config[_ledger.CONFIG_KEY] = _declared
        result["usd_ceiling"] = args.usd_ceiling
        result["per_run_cents"] = _declared["per_run"]
        result["model_priced"] = {"model": _asked,
                                  "input_per_1m": _priced[0],
                                  "output_per_1m": _priced[1],
                                  "source": _priced[2],
                                  "as_of": _priced[3],
                                  "probe_micro_usd_5k_in_1k_out": _probe}

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
            result["runs"][run] = generate_one_run(
                run, model, config, wire, invocations=args.invocations)
            if run == "A":
                # WHICH EVIDENCE IS KEY, decided from the copy run A actually
                # produced. Run D removes THAT row, so "a key piece of evidence"
                # is a measurement rather than a guess made before the run.
                found = licensing_fact_of(result["runs"]["A"],
                                          contact_under_test())
                EVIDENCE_TO_REMOVE.update(found)
                result["evidence_under_test"] = dict(found)

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
            result["projections"] = projections_of(result["email"],
                                                   result["linkedin"])
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
        contact_key = contact_under_test()
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
    """The ledger's own answer, plus the rows, plus why the total can read 0.

    `expected_total: 0` DOES NOT MEAN NO CALL WAS MADE. A model absent from
    `config/model-prices.yaml` still gets a ledger row, with `expected_cost: 0`
    and its call name - the file's own header says so: "a missing row and a free
    call are indistinguishable in the ledger, and that is the failure TASK-323
    fixes". The model this run asks for is not in that file, so every completion
    is ledgered VISIBLY and UNPRICED.
    """
    out = {}
    try:
        out["report"] = spendledger.report(client=CLIENT, config=config)
    except Exception as exc:                                    # noqa: BLE001
        out["report"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    try:
        rows = spendledger.load()
    except Exception as exc:                                    # noqa: BLE001
        rows = []
        out["rows_error"] = "%s: %s" % (type(exc).__name__, exc)
    out["rows"] = rows
    out["row_count"] = len(rows)
    out["ledger_path"] = spendledger.path()
    out["unpriced_calls"] = sorted({row.get("call") for row in rows
                                    if not row.get("expected_cost")})
    out["priced_calls"] = sorted({row.get("call") for row in rows
                                  if row.get("expected_cost")})
    out["model_in_price_file"] = os.environ.get("LLM_MODEL") in _priced_models()
    return out


def _priced_models():
    try:
        from src import clients as _clients
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "config", "model-prices.yaml")
        with open(path, "r", encoding="utf-8") as handle:
            return set(_clients.parse(handle.read()) or {})
    except Exception:                                           # noqa: BLE001
        return set()


def write_artifact(result, path):
    # `scripts/` is not a package (no `__init__.py`), so the sibling renderer is
    # imported off this file's own directory rather than through a package name
    # that does not exist.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import task425_artifact

    task425_artifact.write(result, path)


if __name__ == "__main__":
    sys.exit(main())
