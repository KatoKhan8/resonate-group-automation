#!/usr/bin/env python3
"""TASK-0170. Per contact, per rule, and UNKNOWN never becomes PASS.

## THE HAZARD THIS PINS, MEASURED BEFORE ANY OF IT WAS WRITTEN

In `wt-suppression-2026-10-14` on 2026-10-16:

    agencydnc.load()         ->  {}      work/agency-dnc.jsonl ABSENT
    agencydnc.lookup(anyone) ->  None    every contact passes
    store.load()             ->  0 rows, NO RAISE, work/queue.jsonl ABSENT
    ingest.load_suppress()   ->  2 domains, config/suppress.local.txt ABSENT

The agency do-not-contact list is the one somebody joins by telling Resonate
directly. With its file absent, every contact passes it and **nothing
anywhere says the list was never read.** `src/supervisor.py` faced the same
shape for the campaign registry and refuses — *"Reading it straight would
turn 'I cannot see the registry' into 'there are no campaigns'"* — and
nothing does that for the DNC.

`src/preflight.py` does not change those readers: they sit on send paths and
changing one is a gate change. It checks each rule's AUTHORITY, by path,
before the rule is asked. These tests pin both halves: the hazard, so nobody
assumes it was fixed, and the compensation, so nobody removes it.

## AND THE ASYMMETRY, WHICH IS NOT SYMMETRICAL ON PURPOSE

An exclusion found on a partial read is still an exclusion; a rule that did
not fire on a partial read has not been answered. `bounce_stop_7day` states
the same thing one layer down and it is `senderheadroom`'s: a PASS needs a
complete read and a STOP does not.

## NO REAL ADDRESS IS IN THIS FILE

Operator's condition in the brief, and `test_fixture_hygiene` enforces it on
the bytes. Everything here is `example.test`, `example.invalid` or
`other.invalid`. The real cohort lives in `resonate-ops/` and under
gitignored `work/`, and `src/preflight.py` takes its contacts as an argument
precisely so that a grep of this repository for a prospect finds nothing.
"""
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import agencydnc, ingest, operatorexclusion, preflight   # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "canary_preflight.py")

#: Reserved domains only. See this module's docstring.
CLEAN = {"key": "clean-1", "name": "A Clean Person", "company": "Clean Co",
         "email": "clean@example.invalid", "domain": "example.invalid"}
SUPPRESSED_ADDRESS = "asked-to-stop@example.test"


def _script():
    spec = importlib.util.spec_from_file_location("_canary_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Planted(unittest.TestCase):
    """A temporary directory holding one POPULATED file per authority.

    TASK-0190 CHANGED WHAT THIS HELPER HAS TO PLANT. It used to write an
    empty file per authority and call that "present" - which is the exact
    world a present-and-empty `queue.jsonl` produces, and the one that must
    now come out UNKNOWN. So the plant goes through
    `preflight.plant_authority_files`, which writes ONE REAL RECORD per
    authority through the real writers; `empty=` asks for the other world
    deliberately.

    One plant implementation, shared with the production controls, because
    two would drift and the drift would be invisible in both.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-0170-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(operatorexclusion.forget)
        operatorexclusion.forget()
        os.makedirs(os.path.join(self.tmp, "blank"), exist_ok=True)
        self.paths = preflight.plant_authority_files(self.tmp)

    def state(self, absent=(), raising=(), override=None, empty=()):
        """Authority states, some planted absent, raising, empty or re-pathed.

        `root=self.tmp` is not optional: the plant is in a temporary
        directory, and without it every authority here is an OUTSIDE_TREE
        hard refusal - which is the containment check doing its job, and is
        how it was first observed working.
        """
        override = override or {}
        resolvers = {}
        for name, path in self.paths.items():
            if name in raising:
                def _boom(_n=name):
                    raise OSError("planted: %s unreadable" % _n)
                resolvers[name] = _boom
            elif name in absent:
                resolvers[name] = (lambda _n=name:
                                   os.path.join(self.tmp, _n + ".missing"))
            else:
                resolvers[name] = (lambda _p=override.get(name, path): _p)
        if empty:
            blank = preflight.plant_authority_files(
                os.path.join(self.tmp, "blank"), empty=empty)
            for name in empty:
                resolvers[name] = (lambda _p=blank[name]: _p)
        return preflight.authorities(resolvers=resolvers, root=self.tmp)

    def pointed_at(self, **kw):
        """Context manager pointing the real readers at planted files."""
        return _Pointed(self, kw)


class _Pointed:
    def __init__(self, case, kw):
        self.case, self.kw = case, kw

    def __enter__(self):
        paths = dict(self.case.paths)
        paths.update(self.kw)
        self.saved = (agencydnc.path, operatorexclusion.path,
                      ingest.SUPPRESS, ingest.SUPPRESS_LOCAL)
        agencydnc.path = (lambda _p=paths["agency_dnc"]: _p)
        operatorexclusion.path = (
            lambda _p=paths["operator_exclusion_register"]: _p)
        ingest.SUPPRESS = paths["suppression_template"]
        ingest.SUPPRESS_LOCAL = paths["suppression_local_roster"]
        operatorexclusion.forget()
        return self

    def __exit__(self, *exc):
        (agencydnc.path, operatorexclusion.path,
         ingest.SUPPRESS, ingest.SUPPRESS_LOCAL) = self.saved
        operatorexclusion.forget()
        return False


# --------------------------------------------------- the hazard, pinned


class TheReadersAnswerCleanlyWhenTheirFileIsGone(_Planted):
    """Measured, not argued. If any of these ever starts raising instead,
    this file is the place that finds out — and the authority gate could then
    be simplified rather than silently kept for a reason that moved."""

    def test_the_agency_dnc_returns_none_for_a_suppressed_person_when_absent(
            self):
        """THE WHOLE REASON `preflight.authorities` EXISTS.

        A person on the agency do-not-contact list, with the file absent,
        comes back as not suppressed — indistinguishable from a person who
        was asked and is clean.
        """
        missing = os.path.join(self.tmp, "nowhere.jsonl")
        self.assertFalse(os.path.exists(missing))
        with mock.patch.object(agencydnc, "path", lambda: missing):
            self.assertEqual({}, agencydnc.load())
            self.assertIsNone(agencydnc.lookup({"email": SUPPRESSED_ADDRESS}))

    def test_the_same_person_is_found_when_the_file_is_there(self):
        """The control on the test above: the lookup DOES work, so the None
        above is about the missing file and not about a broken fingerprint."""
        dnc = os.path.join(self.tmp, "real-dnc.jsonl")
        agencydnc.add("email", SUPPRESSED_ADDRESS, file_path=dnc)
        with mock.patch.object(agencydnc, "path", lambda: dnc):
            self.assertIsNotNone(
                agencydnc.lookup({"email": SUPPRESSED_ADDRESS}))

    def test_the_suppression_list_merges_a_missing_roster_silently(self):
        from src import ingest as _ingest
        self.assertEqual(set(), _ingest._read_suppress(
            os.path.join(self.tmp, "no-roster.txt")))


# ------------------------------------------- the authority gate compensates


class AnAbsentAuthorityIsUnknownAndNeverPass(_Planted):

    def test_an_absent_dnc_makes_the_rule_unknown_not_pass(self):
        """The compensation, against the exact hazard above."""
        row = preflight.evaluate(
            CLEAN, state=self.state(absent=("agency_dnc",)))
        cell = row["cells"]["agency_dnc"]
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("ABSENT", cell["why"])
        self.assertIn("agency_dnc", cell["why"])
        self.assertFalse(row["cleared"])

    def test_a_present_dnc_lets_the_rule_be_asked(self):
        """PRESENT **AND POPULATED**. TASK-0190: an empty one does not, and
        `test_a_present_but_empty_authority_is_unknown_not_pass` in
        `test_a_present_authority_can_still_be_empty` is that half."""
        with self.pointed_at():
            state = self.state()
        self.assertEqual(preflight.PRESENT_POPULATED,
                         state["agency_dnc"]["state"])
        with self.pointed_at():
            row = preflight.evaluate(CLEAN, state=state)
        self.assertEqual(preflight.PASS, row["cells"]["agency_dnc"]["cell"])

    def test_unreadable_is_not_the_same_state_as_absent(self):
        """Two different incidents: a file nobody wrote, and a file that is
        there and cannot be opened. Merging them sends somebody looking in
        the wrong place."""
        absent = self.state(absent=("queue",))["queue"]
        broken = self.state(raising=("queue",))["queue"]
        self.assertEqual(preflight.ABSENT, absent["state"])
        self.assertEqual(preflight.PRESENT_UNREADABLE, broken["state"])
        self.assertIsNotNone(absent["path"])
        self.assertIsNone(broken["path"])

    def test_every_authority_a_rule_names_is_in_the_table(self):
        """A typo'd dependency would resolve to no state at all, and a rule
        whose authority is UNDECLARED must not come out PASS."""
        unknown = {}
        for rule in preflight.RULES:
            missing = [n for n in rule["needs"]
                       if n not in preflight.AUTHORITY_NAMES]
            if missing:
                unknown[rule["name"]] = missing
        self.assertEqual({}, unknown)

    def test_an_undeclared_authority_still_comes_out_unknown(self):
        """Belt and braces on the test above, by behaviour: a rule naming an
        authority nobody declared is UNKNOWN, not PASS."""
        rule = dict(preflight.RULES[0], name="invented",
                    needs=("no_such_authority",))
        with mock.patch.object(preflight, "RULES", (rule,)):
            row = preflight.evaluate(CLEAN, state=self.state())
        self.assertEqual(preflight.UNKNOWN, row["cells"]["invented"]["cell"])
        self.assertIn("UNDECLARED", row["cells"]["invented"]["why"])


class ARuleThatRaisedDidNotPass(_Planted):

    def test_a_raising_rule_is_unknown_and_the_others_still_run(self):
        def boom(ctx):
            raise KeyError("a bug in the rule itself")

        broken = dict(preflight.RULES[0], name="boom", ask=boom)
        good = dict(preflight.RULES[0], name="fine", ask=lambda ctx: None)
        with mock.patch.object(preflight, "RULES", (broken, good)), \
                mock.patch.object(preflight, "RULE_NAMES", ("boom", "fine")):
            row = preflight.evaluate(CLEAN, state=self.state())
        self.assertEqual(preflight.UNKNOWN, row["cells"]["boom"]["cell"])
        self.assertIn("KeyError", row["cells"]["boom"]["why"])
        self.assertEqual(preflight.PASS, row["cells"]["fine"]["cell"])


class AnExclusionOnAPartialReadIsStillAnExclusion(_Planted):
    """The asymmetry. `senderheadroom`'s rule, and `bounce_stop_7day`'s."""

    def test_a_domain_on_the_readable_half_is_excluded(self):
        template = os.path.join(self.tmp, "template.txt")
        with io.open(template, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("example.test\n")
        state = self.state(absent=("suppression_local_roster",),
                           override={"suppression_template": template})
        with self.pointed_at(suppression_template=template):
            row = preflight.evaluate(
                {"key": "k", "email": "somebody@example.test",
                 "domain": "example.test"}, state=state)
        cell = row["cells"]["suppression_domain_list"]
        self.assertEqual(preflight.EXCLUDED, cell["cell"])
        self.assertIn("never-sequence", cell["why"])
        self.assertIn("missing one cannot change it", cell["why"])

    def test_a_domain_absent_from_the_readable_half_is_unknown(self):
        template = os.path.join(self.tmp, "template.txt")
        with io.open(template, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("somewhere-else.invalid\n")
        state = self.state(absent=("suppression_local_roster",),
                           override={"suppression_template": template})
        with self.pointed_at(suppression_template=template):
            row = preflight.evaluate(CLEAN, state=state)
        cell = row["cells"]["suppression_domain_list"]
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("readable half WAS asked and did not fire", cell["why"])

    def test_a_rule_without_the_flag_is_not_asked_on_a_partial_read(self):
        """`fires_on_partial` is a DECLARATION per rule, not a default. A
        rule whose halves are not a union must not be asked half-blind."""
        rule = dict(preflight.RULES[3], name="strict",
                    needs=("agency_dnc",),
                    ask=lambda ctx: "this would have fired")
        rule.pop("fires_on_partial", None)
        with mock.patch.object(preflight, "RULES", (rule,)):
            row = preflight.evaluate(CLEAN,
                                      state=self.state(absent=("agency_dnc",)))
        self.assertEqual(preflight.UNKNOWN, row["cells"]["strict"]["cell"])
        self.assertNotIn("would have fired", row["cells"]["strict"]["why"])


class ARecordOrAProviderReadIsNamedRatherThanGuessed(_Planted):

    def test_a_rule_needing_the_queue_is_unknown_and_names_the_file(self):
        row = preflight.evaluate(CLEAN, state=self.state(absent=("queue",)))
        cell = row["cells"]["record_state"]
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("queue", cell["why"])

    def test_a_rule_needing_a_provider_read_is_unknown_even_with_everything(
            self):
        """Every authority present and it is still UNKNOWN, because the read
        is forbidden rather than missing. Two different reasons, both
        reported, neither a pass."""
        with self.pointed_at():
            row = preflight.evaluate(CLEAN, state=self.state())
        for name in ("hold_active_sequence", "hold_recent_touch",
                     "hold_total_sends", "cooling_90_days"):
            with self.subTest(rule=name):
                cell = row["cells"][name]
                self.assertEqual(preflight.UNKNOWN, cell["cell"])
                self.assertIn("provider read", cell["why"])

    def test_a_rule_not_on_this_channel_is_not_a_finding(self):
        row = preflight.evaluate(CLEAN, state=self.state(), channel="linkedin")
        cell = row["cells"]["client_own_domain"]
        self.assertEqual(preflight.PASS, cell["cell"])
        self.assertTrue(cell["not_applicable"])
        self.assertNotIn("client_own_domain", row["unknown_on"])


# ------------------------------------------------------------- the totals


class TheThreeTotalsPartitionTheCohort(_Planted):

    def rows_of(self, verdicts):
        """Planted rows with the given verdicts, through the real `assess`."""
        made = []
        for n, verdict in enumerate(verdicts):
            if verdict == preflight.PASS:
                rule = dict(preflight.RULES[0], name="r",
                            ask=lambda ctx: None)
            elif verdict == preflight.EXCLUDED:
                rule = dict(preflight.RULES[0], name="r",
                            ask=lambda ctx: "planted exclusion")
            else:
                rule = dict(preflight.RULES[0], name="r",
                            needs=("queue",))
            made.append((rule, dict(CLEAN, key="k%d" % n)))
        return made

    def assess_one(self, verdict):
        rule, contact = self.rows_of([verdict])[0]
        with mock.patch.object(preflight, "RULES", (rule,)), \
                mock.patch.object(preflight, "RULE_NAMES", ("r",)):
            with self.pointed_at():
                return preflight.assess([contact],
                                        state=self.state(absent=("queue",)),
                                        control_rows=[{"ok": True}])

    def test_a_clean_cohort_is_cleared_and_exits_zero(self):
        out = self.assess_one(preflight.PASS)
        self.assertEqual({"contacts": 1, "cleared": 1, "excluded": 0,
                          "not_cleared_because_unknown": 0}, out["totals"])
        self.assertEqual(0, out["exit_code"])
        self.assertIn("IS CLEARED TO SEND", out["sentence"])

    def test_an_excluded_contact_exits_one(self):
        out = self.assess_one(preflight.EXCLUDED)
        self.assertEqual(1, out["totals"]["excluded"])
        self.assertEqual(0, out["totals"]["cleared"])
        self.assertEqual(1, out["exit_code"])
        self.assertIn("NOT CLEARED", out["sentence"])

    def test_an_unknown_contact_exits_two_and_is_counted_in_the_third_total(
            self):
        """THE NUMBER THAT MATTERS. It is computed from the rows, not from an
        absence of problems, which is why a cohort nobody could check reads 1
        here rather than 0."""
        out = self.assess_one(preflight.UNKNOWN)
        self.assertEqual(1, out["totals"]["not_cleared_because_unknown"])
        self.assertEqual(0, out["totals"]["cleared"])
        self.assertEqual(2, out["exit_code"])

    def test_an_empty_cohort_is_unknown_and_never_cleared(self):
        """An instrument handed nothing has not cleared anybody. This is the
        shape of every defect this lane has been fixing."""
        out = preflight.assess([], state=self.state(),
                               control_rows=[{"ok": True}])
        self.assertEqual(preflight.UNKNOWN, out["verdict"])
        self.assertEqual(2, out["exit_code"])
        self.assertEqual(0, out["totals"]["cleared"])
        self.assertIn("not a clean cohort", out["sentence"])

    def test_the_totals_partition_the_rows(self):
        with self.pointed_at():
            out = preflight.assess(
                [dict(CLEAN, key="a"), dict(CLEAN, key="b")],
                state=self.state(absent=("queue",)),
                control_rows=[{"ok": True}])
        totals = out["totals"]
        self.assertEqual(totals["contacts"],
                         totals["cleared"] + totals["excluded"]
                         + totals["not_cleared_because_unknown"])

    def test_a_broken_control_outranks_a_finding(self):
        """A table whose instrument could not be shown to work does not
        support either answer, so it exits 2 rather than 1."""
        rule, contact = self.rows_of([preflight.EXCLUDED])[0]
        with mock.patch.object(preflight, "RULES", (rule,)), \
                mock.patch.object(preflight, "RULE_NAMES", ("r",)):
            with self.pointed_at():
                out = preflight.assess([contact], state=self.state(),
                                       control_rows=[{"ok": False}])
        self.assertEqual(preflight.UNKNOWN, out["verdict"])
        self.assertEqual(2, out["exit_code"])
        self.assertIn("controls did not hold", out["sentence"])

    def test_an_excluded_row_with_unknown_cells_counts_as_excluded(self):
        """And the sentence still names the UNKNOWN, because a finding must
        not hide an unanswered rule."""
        with self.pointed_at():
            out = preflight.assess(
                [{"key": "k", "email": "x@example.test",
                  "domain": "example.test"}],
                state=self.state(absent=("queue", "agency_dnc"),
                                 override={}),
                control_rows=[{"ok": True}])
        row = out["rows"][0]
        self.assertTrue(row["unknown_on"])
        self.assertEqual(preflight.UNKNOWN, row["verdict"])
        self.assertFalse(row["cleared"])


# ------------------------------------------------------------ the controls


class TheControlsProveTheInstrumentCanFail(unittest.TestCase):

    def test_every_control_holds_and_the_count_is_pinned(self):
        """THREE UNTIL TASK-0190, FIVE UNTIL TASK-0200, SEVEN UNTIL
        TASK-0250.

        The name no longer carries the number. It said `three` and had to be
        renamed when a fourth control was added, which is the same defect as
        a count typed into prose - so the number lives in the assertion,
        where changing it is a visible edit and not a rename.
        """
        rows = preflight.controls()
        self.assertEqual(9, len(rows))
        for row in rows:
            with self.subTest(control=row["control"]):
                self.assertTrue(row["ok"], "%s: expected %r observed %r"
                                % (row["control"], row["expected"],
                                   row["observed"]))

    def test_control_one_is_a_real_lookup_through_a_real_file(self):
        rows = preflight.controls()
        self.assertIn("EXCLUDED", rows[0]["control"])
        # THE AUTHORITY STATE IS IN THE OBSERVATION HERE TOO, for the same
        # reason it is in control 2: a cell checked without the state behind
        # it can be right for the wrong reason.
        self.assertEqual([preflight.PRESENT_POPULATED, preflight.EXCLUDED,
                          True], rows[0]["observed"])

    def test_control_two_is_unknown_with_a_non_zero_exit(self):
        rows = preflight.controls()
        self.assertIn("raises", rows[1]["control"])
        # The AUTHORITY STATE is part of the observation, so that blinding
        # the gate cannot leave this control green - see
        # `test_an_authority_gate_that_answers_pass_is_caught`.
        self.assertEqual(
            [preflight.PRESENT_UNREADABLE, preflight.UNKNOWN, 2],
            rows[1]["observed"])
        self.assertNotEqual(0, rows[1]["observed"][-1])

    def test_control_three_is_the_pass_the_other_two_cannot_show(self):
        """Without it an instrument answering EXCLUDED or UNKNOWN to
        everything would pass both the others."""
        rows = preflight.controls()
        self.assertIn("PASS", rows[2]["control"])
        self.assertEqual([preflight.PASS] * 4, rows[2]["observed"])

    def test_an_authority_gate_that_answers_pass_is_caught(self):
        """THE CONTROL THAT PROVES IT CAN FAIL. The gate is weakened so an
        absent authority reads PRESENT; control 2 must notice."""
        real = preflight.authorities

        def blind(*a, **kw):
            state = real(*a, **kw)
            for row in state.values():
                row["state"] = preflight.PRESENT_POPULATED
            return state

        with mock.patch.object(preflight, "authorities", blind):
            rows = preflight.controls()
        self.assertFalse(rows[1]["ok"],
                         "a blind authority gate passed control 2")


# -------------------------------------------------------------- the safety


class NothingHereCarriesARealAddressOrCallsAProvider(unittest.TestCase):

    #: An address on a domain that is not reserved for testing. Narrow on
    #: purpose: `example.test`, `example.invalid` and `other.invalid` are
    #: reserved by RFC 2606/6761 and cannot reach anybody.
    ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
    RESERVED = ("example.test", "example.invalid", "other.invalid",
                "example.com", "example.org", "test", "invalid", "localhost")

    def addresses_in(self, path):
        text = io.open(path, encoding="utf-8").read()
        out = []
        for match in self.ADDRESS.finditer(text):
            domain = match.group(1).lower()
            if any(domain == r or domain.endswith("." + r)
                   for r in self.RESERVED):
                continue
            out.append(match.group(0))
        return out

    def test_no_real_address_in_the_module_the_script_or_this_file(self):
        """Operator's condition in the brief: these are real people's
        addresses and they belong in `resonate-ops/` and gitignored paths
        only, never in a test fixture."""
        for path in (os.path.join(ROOT, "src", "preflight.py"), SCRIPT,
                     os.path.abspath(__file__)):
            with self.subTest(file=os.path.basename(path)):
                self.assertEqual([], self.addresses_in(path))

    #: The ONLY module with "provider" in its name the preflight may reach,
    #: and the only attributes of it that may be touched. TASK-0200 added
    #: `internal_campaign_membership`, which has to classify a campaign, and
    #: `providerwrites` is where that classification lives - so the ban moved
    #: from the NAME to the SURFACE. `perform` is the writer; it is named
    #: here so that reaching it fails this test rather than a review.
    GUARD = "providerwrites"
    GUARD_SURFACE = ("classify_campaign", "declared_internal",
                     "internal_campaigns_path", "DECLARED_CHANNELS",
                     "RESONATE_OS", "RESONATE_INTERNAL", "UNKNOWN_OWNER",
                     "_provider_key")
    GUARD_FORBIDDEN = ("perform", "transport", "execute", "write")

    def imports_and_attributes(self, relpath):
        """(imported names, attributes read off the guard) by AST walk.

        AST rather than text, so a docstring mentioning EmailBison does not
        fail it - this repository has been bitten by that exact false
        positive.
        """
        import ast
        tree = ast.parse(io.open(os.path.join(ROOT, relpath),
                                 encoding="utf-8").read())
        imported, attributes = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                for alias in node.names:
                    imported.add("%s.%s" % (node.module or "", alias.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif (isinstance(node, ast.Attribute)
                  and isinstance(node.value, ast.Name)
                  and node.value.id == self.GUARD):
                attributes.add(node.attr)
        return imported, attributes

    def test_the_module_reaches_no_provider(self):
        """No PROVIDER ADAPTER, and only the guard's read-only surface.

        Before TASK-0200 this banned every import whose name contained
        "provider", which caught `providerwrites` - the ownership classifier,
        not an adapter. Keeping that ban would have meant reaching the
        classifier through `campaignmembership` instead, which is the same
        edge with one module in front of it, so the assertion is now about
        what is REACHED rather than what is spelled.
        """
        for relpath in ("src/preflight.py", "src/campaignmembership.py"):
            imported, attributes = self.imports_and_attributes(relpath)
            with self.subTest(file=relpath):
                offenders = sorted(
                    n for n in imported
                    if (("provider" in n and self.GUARD not in n)
                        or n.endswith("bison") or n.endswith("heyreach")))
                self.assertEqual([], offenders)
                # THE WRITER IS NOT ON THE SURFACE. `perform` is what
                # actually reaches a provider.
                self.assertEqual(
                    [], sorted(a for a in attributes
                               if a in self.GUARD_FORBIDDEN),
                    "%s reaches the provider-WRITE surface" % relpath)
                self.assertEqual(
                    [], sorted(a for a in attributes
                               if a not in self.GUARD_SURFACE),
                    "%s touches a providerwrites attribute that is not on "
                    "the declared read-only surface" % relpath)

    def test_the_script_writes_no_file(self):
        """READ-ONLY, asserted. The report is produced on stdout and
        redirected by the caller, so the script itself opens nothing for
        writing — which is also why it cannot write into production `work/`.
        """
        text = io.open(SCRIPT, encoding="utf-8").read()
        for banned in ('"w"', "'w'", '"a"', "'a'", "os.replace("):
            self.assertNotIn(banned, text,
                             "%s opens a file for writing" % SCRIPT)

    def test_the_script_takes_its_cohort_as_an_argument(self):
        """So the repository carries no cohort of its own and a grep for a
        prospect finds nothing."""
        module = _script()
        with self.assertRaises(SystemExit):
            module.main(["--cohort"])
        rows = module.main(["--controls-only"])
        self.assertEqual(0, rows)

    def test_every_rule_names_what_decides_it(self):
        """A table nobody can check against the code is a table that drifts.
        Each row names the module and function; the module half must import.
        """
        import importlib
        for rule in preflight.RULES:
            with self.subTest(rule=rule["name"]):
                self.assertTrue(rule["decides"].strip())
                head = rule["decides"].split(".")[0].split()[0]
                importlib.import_module("src.%s" % head)

    def test_production_work_is_named_rather_than_read(self):
        """It reports the MAIN checkout's path, because `store.PRODUCTION_WORK`
        resolves against the calling tree and a preflight run from a worktree
        would otherwise resolve the queue to that worktree's empty `work/`."""
        path, why = preflight.production_work()
        if path is None:
            self.skipTest("git could not be asked here: %s" % why)
        self.assertTrue(path.endswith("work"))
        self.assertNotIn("wt-suppression", path)


class TheGapListIsPinnedInBothDirections(unittest.TestCase):
    """`RULES_EXPECTED_BUT_NOT_FOUND` is a claim about the code, so it is
    checked against the code. Both halves, for the reason
    `test_the_direct_reader_exemption_list_has_not_fallen_behind` gives: an
    entry that outlives its own gap is a false finding, and a gap with no
    entry is the thing the list exists to stop."""

    #: THE FOUR MODULES A SEND ACTUALLY GOES THROUGH. `preflight` was in
    #: this tuple until TASK-0200 and was removed deliberately: the preflight
    #: now DOES ask the ownership classifier, which is what the rewritten
    #: entry says, and `test_the_preflight_does_ask_it` below pins that half.
    #: A send that does not go through the preflight is still checked by
    #: nobody, and that is the half of the gap that remains.
    SEND_PATH = ("eligibility", "suppression", "hygiene", "channels")

    def imports_of(self, name):
        import ast
        path = os.path.join(ROOT, "src", "%s.py" % name)
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        out = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    out.add(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    out.add(alias.name.split(".")[-1])
        return out

    def test_no_send_path_module_asks_the_ownership_classifier(self):
        """The half that keeps the REWRITTEN entry honest. If somebody
        implements CLAUDE.md's standing rule 2 on a send path, this fails and
        `internal_campaign_membership_on_the_send_path` must be deleted."""
        asking = [name for name in self.SEND_PATH
                  if "providerwrites" in self.imports_of(name)]
        self.assertEqual(
            [], asking,
            "%s now imports providerwrites - if that is the ownership "
            "classifier being consulted, delete the "
            "internal_campaign_membership_on_the_send_path entry from "
            "RULES_EXPECTED_BUT_NOT_FOUND" % (asking,))

    def test_the_preflight_does_ask_it(self):
        """The OTHER half, and the one that stops the rewritten entry being
        a claim about nothing: the preflight really does consult the
        classifier, through a rule that really is in RULES."""
        self.assertIn("providerwrites", self.imports_of("campaignmembership"))
        self.assertIn("internal_campaign_membership", preflight.RULE_NAMES)
        rule = [r for r in preflight.RULES
                if r["name"] == "internal_campaign_membership"][0]
        self.assertEqual(("internal_campaign_declaration", "campaign_ledger",
                          "campaign_lead_rows"), rule["needs"])
        self.assertTrue(callable(rule["ask"]))
        # AND THE GAP ENTRY STILL EXISTS, under its narrowed name. A rule
        # implemented in one place is not the same claim as a rule
        # implemented everywhere it is declared.
        self.assertIn("internal_campaign_membership_on_the_send_path",
                      preflight.EXPECTED_NOT_FOUND_NAMES)

    def test_the_ownership_classifier_really_exists_where_the_entry_says(self):
        """The other half of the same claim: the entry says the classifier
        exists for provider writes, so that must be true too."""
        from src import providerwrites
        self.assertEqual(("resonate_os", "resonate_internal", "unknown"),
                         providerwrites.OWNERSHIP)

    def test_the_cooling_window_lifts_a_hold_and_does_not_impose_one(self):
        """The `ninety_day_no_contact` entry, measured rather than argued.

        90 days is real and is consulted - and the recency hold is 30. A
        contact touched 45 days ago is inside the cooling window and outside
        the recency hold, so nothing holds them. If either number moves, or
        if a 90-day refusal appears, this fails.
        """
        from src import suppression
        limits = suppression.thresholds()
        self.assertEqual(90, limits["cooling_days"])
        self.assertEqual(30, limits["hold_after_last_touch_days"])
        self.assertLess(limits["hold_after_last_touch_days"],
                        limits["cooling_days"])
        touched = {"last_touch_at": "2026-09-01T00:00:00Z", "total_sends": 1,
                   "active_sequence": False}
        verdict = suppression.decide(
            {"id": "r", "domain": "example.invalid"},
            {"key": "c", "email": "someone@example.invalid"},
            provider_touches=touched,
            now="2026-10-16T00:00:00Z")
        self.assertEqual(suppression.ALLOW, verdict.action,
                         "a contact touched 45 days ago is held by %r - the "
                         "ninety_day_no_contact entry is stale"
                         % (list(verdict.reasons),))
        self.assertTrue(verdict.sendable)
        self.assertEqual((), verdict.reasons)

    def test_suppressions_agency_argument_is_accepted_and_never_used(self):
        """A minor finding, pinned so it is not mistaken for a working seam.

        `suppression.decide` takes `agency=` and does not forward it to
        `eligibility.must_not_contact`, which calls
        `agencydnc.lookup(index=None)` and so re-reads from disk every time.
        Harmless today - the docstring says reading from disk is deliberate -
        but a caller passing a pre-built index believes it is used.
        """
        import inspect
        from src import suppression
        source = inspect.getsource(suppression.decide)
        self.assertIn("agency=None", source)
        body = source.split('"""', 2)[-1]
        self.assertNotIn("agency", body,
                         "decide now uses `agency` - delete this test and the "
                         "finding it pins")

    def test_every_gap_entry_says_all_four_things(self):
        for row in preflight.RULES_EXPECTED_BUT_NOT_FOUND:
            with self.subTest(rule=row["name"]):
                for key in ("declared_in", "what_exists", "what_is_missing",
                            "would_need"):
                    self.assertTrue(row.get(key, "").strip(),
                                    "%s has no %s" % (row["name"], key))

    def test_a_gap_entry_is_not_also_a_rule(self):
        """A name in both lists would be asked and reported missing at once."""
        self.assertEqual(set(), set(preflight.EXPECTED_NOT_FOUND_NAMES)
                         & set(preflight.RULE_NAMES))


class TheReportsOwnProvenanceIsMeasuredNotTyped(unittest.TestCase):
    """TASK-0170 re-dispatch, 2026-10-16. Two defects in 0170's own artefact.

    **F1.** `CANARY-01-PREFLIGHT-2026-10-16.md` named SHA `117d96595` as the
    SHA the check ran at. `src/preflight.py` and `scripts/canary_preflight.py`
    are ABSENT from git at that SHA - they first exist at `045babe5f`. The run
    was made from a tree holding them uncommitted, so the one line a reader
    needs in order to reproduce the table points at a commit that does not
    contain the instrument. `--sha` was free text and nothing checked it.

    **F2.** `assessment["at"]` had exactly ONE occurrence in the whole tree
    and it was the `.get` that READ it. Nothing ever produced it, so every
    report said *"Measured see the lane entry on SHA ..."* - the fallback
    string standing in for the run time, which is both ungrammatical and a
    silently lost measurement. It is the same reader-with-no-producer shape
    TASK-0180 found in `delivered` one commit later.

    Both are pinned here rather than in prose, because a provenance line
    nothing measures is this repository's signature defect wearing the
    costume of an audit trail.
    """

    def test_the_assessment_names_the_time_it_ran(self):
        """F2. `at` must have a PRODUCER, not only a reader."""
        at = preflight.assess([]).get("at")
        self.assertTrue(at, "assess() produces no `at` - the report's "
                            "timestamp has a reader and no producer")
        self.assertRegex(
            str(at), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$",
            "`at` is not a UTC timestamp: %r" % (at,))

    def test_the_fallback_phrase_never_reaches_a_report(self):
        """F2, on the bytes a person actually reads - WITH `at` ABSENT.

        The first version of this test passed a live `assess([])`, which now
        carries `at`, so `.get("at", <fallback>)` never reached its default
        and restoring the fallback killed NOTHING. The producer masked the
        reader. `at` is deleted here so this test guards the report line on
        its own, independently of whether anything produced a timestamp -
        which is the only way it can speak to the defect it is named for.
        """
        assessment = preflight.assess([])
        assessment.pop("at", None)
        body = _script().markdown(assessment, sha="deadbeef")
        self.assertNotIn("see the lane entry", body)
        self.assertIn("AT AN UNRECORDED TIME", body,
                      "a missing run time must be said out loud, not "
                      "defaulted into prose")

    def test_the_comparison_is_one_git_normalises(self):
        """M3. The line-ending claim in `provenance`'s docstring, pinned.

        This tree is MIXED: `requirements.txt` is CRLF and the instrument's
        own files are LF. `git hash-object` without `--path` applies no
        filter, so comparing a raw hash of the working file against the
        committed blob would report MODIFIED for a line ending alone - a
        provenance check that cries wolf on every tree with the other
        convention. `git diff <sha> -- <path>` asks git, which normalises.

        Pinning the call rather than the verdict is deliberate and is the
        weaker of the two kinds of test: the claim IS the choice of
        comparison, and no verdict distinguishes the two implementations in
        a tree where the endings happen to agree.
        """
        seen = []

        def recorder(args):
            seen.append(list(args))
            if args[:2] == ["rev-parse", "HEAD"]:
                return 0, "c0ffee1234567890" + chr(10), ""
            return 0, "", ""

        preflight.provenance(runner=recorder)
        compares = [a for a in seen if a and a[0] == "diff"]
        self.assertEqual(
            len(compares), len(preflight.INSTRUMENT_FILES),
            "one normalising comparison per instrument file; saw %r" % (seen,))
        for args in compares:
            self.assertIn("--quiet", args)
            self.assertIn("--", args, "the pathspec must be separated so git "
                                      "normalises the working file")
            self.assertNotIn("hash-object", args)
        self.assertFalse([a for a in seen if "hash-object" in a],
                         "a raw hash would report MODIFIED for a line ending")

    def test_a_sha_that_does_not_carry_the_instrument_is_refused(self):
        """F1. The detector must say NO when the blob is not there.

        Injected rather than taken from real history: a hardcoded SHA would
        make this test a statement about this branch's shape instead of about
        the detector.
        """
        def absent(args):
            if args[:2] == ["rev-parse", "HEAD"]:
                return 0, "c0ffee1234567890\n", ""
            if args[0] == "cat-file":
                return 1, "", "Not a valid object name"
            return 0, "", ""

        prov = preflight.provenance(sha="c0ffee12", runner=absent)
        self.assertFalse(prov["confirmed"])
        self.assertIn("ABSENT", str(prov["detail"]).upper())

    def test_a_modified_instrument_is_refused_too(self):
        """F1's other half: present at the SHA but not what ran."""
        def modified(args):
            if args[0] == "cat-file":
                return 0, "", ""
            if args[0] == "diff":
                return 1, "", ""          # differs from the working tree
            return 0, "c0ffee1234567890\n", ""

        prov = preflight.provenance(sha="c0ffee12", runner=modified)
        self.assertFalse(prov["confirmed"])
        self.assertIn("MODIFIED", str(prov["detail"]).upper())

    def test_the_instrument_is_confirmed_at_head_in_this_tree(self):
        """THE CONTROL, and it uses the REAL git.

        Without it the two refusals above are satisfied by a detector that
        answers "not confirmed" to everything - which is the vacuous-control
        trap this lane fixed once already in TASK-0080. This one can only
        pass if the committed blobs really do match the working tree, so it
        also fails if somebody edits the instrument and does not commit it.
        """
        prov = preflight.provenance()
        self.assertTrue(
            prov["confirmed"],
            "the instrument at HEAD does not match the working tree: %s"
            % (prov["detail"],))
        self.assertRegex(prov["sha"], r"^[0-9a-f]{7,40}$")

    def test_the_report_never_prints_a_sha_without_its_verification(self):
        """A bare SHA in a provenance line is an unverified claim."""
        body = _script().markdown(preflight.assess([]),
                                  sha=preflight.provenance()["sha"])
        line = [ln for ln in body.splitlines() if ln.startswith("Measured ")]
        self.assertTrue(line, "no Measured line in the report")
        self.assertRegex(line[0], r"instrument (CONFIRMED|NOT CONFIRMED)")


if __name__ == "__main__":
    unittest.main()
