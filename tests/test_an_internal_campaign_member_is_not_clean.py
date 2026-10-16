#!/usr/bin/env python3
"""TASK-0200. The rule nobody asked: a lead row in a campaign that is not ours.

## THE HOLE, MEASURED

CLAUDE.md standing rule 2 and `docs/OPERATING-MODE.md` both say it in words:

    anyone with a lead row in 327/328/352 is NOT CLEAN for outreach,
    whoever owns them

and UNKNOWN ownership means do-not-touch and members NOT CLEAN. Measured
2026-10-16 and recorded in `CANARY-01-PREFLIGHT-2026-10-16.md`: **nothing in
`eligibility`, `suppression`, `hygiene` or `channels` asked it**, and a member
of every declared internal campaign passed all twenty-two preflight rules.

`providerwrites.classify_campaign` was the near-miss: it answers *may we WRITE
to this campaign*, a different question in the same vocabulary. It classifies
a DESTINATION; nothing classified a CONTACT.

## WHAT IS PINNED HERE

* a planted member of a DECLARED internal campaign is EXCLUDED, by number
* a planted member of an UNKNOWN-OWNER campaign is EXCLUDED too
* a planted non-member is PASS **only** against a listing that can prove its
  own walk covered the campaigns in question
* the three campaign ids are **derived, never typed** - asserted on the code
  strings and numeric constants of both modules
* the authority's own `owner` field is IGNORED, because it is a retyped
  literal that disagrees with the operator's declaration in both directions
* `Undecided` is not an exclusion, which it would be by truthiness alone
* and the rule is UNKNOWN today, loudly, with the command that would change
  that

## NO REAL ADDRESS AND NO REAL COHORT IS IN THIS FILE

Reserved domains only, and the estate's fictional test people. The real
cohort lives in `resonate-ops/` and under gitignored `work/`.
"""
import ast
import io
import json
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

from src import campaignmembership, preflight, providerwrites   # noqa: E402

PRODUCER = os.path.join(ROOT, "scripts", "build_collision_index.py")

#: Reserved domains. `MEMBER` is Casey Wright's shape, not Casey Wright's
#: address, and nothing here resembles a real cohort row.
MEMBER = {"key": "member-1", "name": "Casey Wright", "company": "Casey Co",
          "email": "casey.wright@example.test", "domain": "example.test"}
STRANGER = {"key": "stranger-1", "name": "Morgan Ellis",
            "company": "Ellis Co", "email": "morgan.ellis@example.invalid",
            "domain": "example.invalid"}

#: The real provider campaign ids this rule is ABOUT, which is exactly why
#: they may not be written into the rule. From `config/internal-campaigns.txt`
#: (274, 327, 328, 352) and `build_collision_index` (which adds 418).
REAL_IDS = (274, 327, 328, 352, 418)

RULE = "internal_campaign_membership"


def code_strings_and_numbers(path):
    """Every literal a module USES, docstrings excluded.

    Lifted in shape from `test_invariants.code_strings`, and for the same
    reason: a module that EXPLAINS 327 in prose is doing the right thing,
    and a module that compares against it is not.
    """
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    docstrings = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None) or []
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            docstrings.add(id(body[0].value))
    strings, numbers = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in docstrings:
            continue
        if isinstance(node.value, str):
            strings.append(node.value)
        elif isinstance(node.value, int) and not isinstance(node.value, bool):
            numbers.append(node.value)
    return strings, numbers


class _World(unittest.TestCase):
    """A planted estate: a declaration, a ledger, and a lead-row listing."""

    def setUp(self):
        from src import operatorexclusion
        self.tmp = tempfile.mkdtemp(prefix="rga-0200-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(operatorexclusion.forget)
        operatorexclusion.forget()
        self.state, self.paths = preflight._planted_state(self.tmp)

    def listing(self, **kw):
        """Rewrite the planted listing and re-resolve the authority state."""
        path = self.paths["campaign_lead_rows"]
        index = preflight._write_lead_rows(path, members=kw.pop("members", ()))
        for key, value in kw.items():
            index[key] = value
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        return index

    def cell(self, contact, channel="email", state=None):
        with preflight._pointed(self.paths):
            row = preflight.evaluate(contact, state=state or self.state,
                                     channel=channel)
        return row["cells"][RULE]

    @property
    def internal(self):
        return preflight._CONTROL_INTERNAL_CAMPAIGN

    @property
    def ours(self):
        return preflight._CONTROL_OUR_CAMPAIGN


class AMemberIsExcludedByNumber(_World):

    def test_a_member_of_a_declared_internal_campaign_is_excluded(self):
        self.listing(members=[(MEMBER["email"], self.internal)])
        cell = self.cell(MEMBER)
        self.assertEqual(preflight.EXCLUDED, cell["cell"])
        self.assertIn(str(self.internal), cell["why"])
        # THE DECLARATION IS NAMED, so a reader can go and check the claim
        # against the file that makes it true.
        self.assertIn(self.paths["internal_campaign_declaration"],
                      cell["why"])
        self.assertIn("NOT CLEAN", cell["why"])

    def test_a_member_of_an_unknown_owner_campaign_is_excluded_too(self):
        """CLAUDE.md: UNKNOWN means do-not-touch and members NOT CLEAN. A
        campaign neither declared internal nor bound by a ledger row is one
        nobody can say is ours."""
        stranger_campaign = 999777
        self.listing(members=[(MEMBER["email"], stranger_campaign)])
        cell = self.cell(MEMBER)
        self.assertEqual(preflight.EXCLUDED, cell["cell"])
        self.assertIn(str(stranger_campaign), cell["why"])
        self.assertIn("UNKNOWN", cell["why"])

    def test_a_member_of_only_our_own_campaign_is_not_excluded_by_this_rule(
            self):
        """The rule is about campaigns that are NOT ours. Being in one of
        ours is `hold_active_sequence`'s and `hold_recent_touch`'s business,
        and answering it here would be a second opinion on a question
        another rule owns."""
        self.listing(members=[(MEMBER["email"], self.ours)])
        cell = self.cell(MEMBER)
        self.assertEqual(preflight.PASS, cell["cell"])

    def test_the_headline_moves_from_unknown_to_excluded(self):
        """§4: the cohort's sentence has to change. A cell nobody reads is
        not a gate, and the sentence is what a reader acts on."""
        self.listing(members=[(MEMBER["email"], self.internal)])
        with preflight._pointed(self.paths):
            out = preflight.assess([MEMBER], state=self.state,
                                   control_rows=[{"ok": True}])
        self.assertEqual(1, out["totals"]["excluded"])
        self.assertEqual(0, out["totals"]["cleared"])
        self.assertEqual(preflight.EXIT_EXCLUDED, out["exit_code"])
        self.assertIn("1 EXCLUDED by a rule that fired", out["sentence"])
        self.assertIn(RULE, out["rows"][0]["excluded_by"])


class ANonMemberNeedsAWalkThatCouldHaveSeenThem(_World):
    """`senderheadroom`'s rule, one layer down: a non-match is the ROOM
    answer, and ROOM is provable only from a complete walk."""

    def test_a_non_member_is_pass_against_a_proven_complete_listing(self):
        self.listing()
        cell = self.cell(STRANGER)
        self.assertEqual(preflight.PASS, cell["cell"])

    def test_a_non_member_is_unknown_when_a_walk_cannot_prove_itself(self):
        """THE STATE OF THE REAL AUTHORITY TODAY. The producer discards the
        provider's own total, so `complete: true` means only that nothing
        raised - and a walk truncated at the page cap is indistinguishable
        from a finished one."""
        index = self.listing()
        index["campaigns"][str(self.internal)].pop("leads_reported")
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        cell = self.cell(STRANGER)
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("leads_reported", cell["why"])
        self.assertIn(str(self.internal), cell["why"])

    def test_a_non_member_is_unknown_when_an_internal_campaign_was_not_walked(
            self):
        """A declared internal campaign with no entry in the listing at all.
        "Not in the listing" says nothing about a campaign nobody read."""
        index = self.listing()
        index["campaigns"].pop(str(self.internal))
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        cell = self.cell(STRANGER)
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("never walked", cell["why"])

    def test_a_non_member_is_unknown_when_the_listing_names_it_incomplete(
            self):
        index = self.listing()
        index["incomplete"] = [{"campaign": self.internal,
                                "why": "planted: walk did not complete"}]
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        cell = self.cell(STRANGER)
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("incomplete", cell["why"])

    def test_a_match_survives_the_same_partial_walk_that_blocks_a_pass(self):
        """THE ASYMMETRY, in one pair of tests with one planted world. A lead
        row that was READ exists whatever else the walk missed."""
        index = self.listing(members=[(MEMBER["email"], self.internal)])
        index["campaigns"][str(self.internal)].pop("leads_reported")
        index["incomplete"] = [{"campaign": self.ours, "why": "planted"}]
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        self.assertEqual(preflight.EXCLUDED, self.cell(MEMBER)["cell"])
        self.assertEqual(preflight.UNKNOWN, self.cell(STRANGER)["cell"])

    def test_an_incomplete_walk_of_one_of_our_own_cannot_hide_a_membership(
            self):
        """So completeness is required only of the campaigns the rule is
        about. Requiring it everywhere would make the rule permanently
        UNKNOWN for a reason that cannot affect its answer."""
        index = self.listing()
        index["campaigns"][str(self.ours)]["complete"] = False
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        self.assertEqual(preflight.PASS, self.cell(STRANGER)["cell"])


class TheChannelIsPartOfTheQuestion(_World):

    def test_linkedin_is_unknown_because_heyreach_was_never_walked(self):
        """Not a hypothetical: the producer records `{"read": false}` for
        HeyReach and says why in its own source. The LinkedIn canary is one
        of the things waiting on this gate."""
        self.listing(members=[(MEMBER["email"], self.internal)])
        cell = self.cell(MEMBER, channel="linkedin")
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("HeyReach", cell["why"])

    def test_a_walked_heyreach_listing_would_answer_linkedin(self):
        """The control on the test above: the refusal is about coverage, not
        about the channel being unsupported."""
        self.listing(members=[(MEMBER["email"], self.internal)],
                     heyreach={"read": True, "campaigns": {}})
        cell = self.cell(MEMBER, channel="linkedin")
        self.assertEqual(preflight.EXCLUDED, cell["cell"])


class TheAuthorityIsCheckedBeforeTheRule(_World):

    def test_an_absent_listing_is_unknown_and_names_the_command(self):
        os.remove(self.paths["campaign_lead_rows"])
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        self.assertEqual(preflight.ABSENT,
                         self.state["campaign_lead_rows"]["state"])
        cell = self.cell(STRANGER)
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("build_collision_index", cell["why"])

    def test_an_empty_listing_is_present_empty_and_not_nobody_in_327(self):
        """TASK-0190's distinction, reused rather than re-implemented: a
        listing that indexed no address is not a workspace where nobody is
        in an internal campaign."""
        index = self.listing()
        index["by_email"] = {}
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        self.assertEqual(preflight.PRESENT_EMPTY,
                         self.state["campaign_lead_rows"]["state"])
        self.assertEqual(preflight.UNKNOWN, self.cell(STRANGER)["cell"])

    def test_a_listing_missing_a_required_key_is_unreadable_not_empty(self):
        index = self.listing()
        index.pop("by_email")
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        self.assertEqual(preflight.PRESENT_UNREADABLE,
                         self.state["campaign_lead_rows"]["state"])
        self.assertEqual(preflight.UNKNOWN, self.cell(STRANGER)["cell"])

    def test_the_declaration_and_the_ledger_are_authorities_of_their_own(self):
        """Both are REQUIRED, and both say what their absence costs."""
        for name in ("internal_campaign_declaration", "campaign_ledger",
                     "campaign_lead_rows"):
            with self.subTest(authority=name):
                self.assertIn(name, preflight.AUTHORITY_NAMES)
                entry = [a for a in preflight.AUTHORITIES
                         if a["name"] == name][0]
                self.assertTrue(entry["absent_means"].strip())
                self.assertTrue(entry["empty_means"].strip())
        rule = [r for r in preflight.RULES if r["name"] == RULE][0]
        self.assertEqual(("internal_campaign_declaration", "campaign_ledger",
                          "campaign_lead_rows"), rule["needs"])

    def test_a_declared_internal_match_still_fires_without_the_ledger(self):
        """THE ASYMMETRY AT THE AUTHORITY LEVEL. A campaign the operator
        DECLARED internal needs no ledger to be recognised, so the exclusion
        survives a missing one - while a non-match against the same world is
        UNKNOWN."""
        self.listing(members=[(MEMBER["email"], self.internal)])
        state = preflight._planted_state(self.tmp, paths=self.paths)[0]
        os.remove(self.paths["campaign_ledger"])
        state = preflight.authorities(
            resolvers={n: (lambda _p=p: _p)
                       for n, p in self.paths.items()}, root=self.tmp)
        self.assertEqual(preflight.ABSENT, state["campaign_ledger"]["state"])
        self.assertEqual(preflight.EXCLUDED,
                         self.cell(MEMBER, state=state)["cell"])
        self.assertEqual(preflight.UNKNOWN,
                         self.cell(STRANGER, state=state)["cell"])


class TheCampaignSetIsDerivedAndNeverTyped(_World):

    #: A string this long is a sentence, not a value. The lexical half below
    #: exempts prose because both modules must keep EXPLAINING 274, 327, 328
    #: and 352 - naming the campaigns the rule is about is how a reader
    #: checks it. That exemption is why this test is the SUPPORT and
    #: `test_a_campaign_declared_internal_today_is_covered_without_an_edit`
    #: is the proof: that one shows the rule covering a campaign no file in
    #: this repository has ever named.
    PROSE = 40

    def test_no_real_campaign_id_is_a_usable_literal_in_either_module(self):
        """§2: the three ids are not a literal to retype.

        An id used as DATA is an int, or a short string holding the id or a
        list of them. An id used in an EXPLANATION sits inside a sentence.
        Both halves are asserted on code literals with docstrings excluded,
        never on the source text.
        """
        for relpath in ("src/preflight.py", "src/campaignmembership.py"):
            strings, numbers = code_strings_and_numbers(
                os.path.join(ROOT, relpath))
            with self.subTest(file=relpath):
                # AS A NUMBER: a comparison needs the value, so this is the
                # half that cannot be argued with.
                self.assertEqual([], sorted(set(numbers) & set(REAL_IDS)))
                typed = sorted({t for t in strings if len(t) < self.PROSE
                                for i in REAL_IDS
                                if re.search(r"\b%d\b" % i, t)})
                self.assertEqual([], typed)

    def test_a_campaign_declared_internal_today_is_covered_without_an_edit(
            self):
        """§2 again: "if a fourth campaign is internal or unknown-owner
        today, the rule must already cover it". Proven by adding one to the
        planted declaration and changing no code."""
        fourth = 999123
        with io.open(self.paths["internal_campaign_declaration"], "a",
                     encoding="utf-8", newline="\n") as handle:
            handle.write("bison %d\n" % fourth)
        index = self.listing(members=[(MEMBER["email"], fourth)])
        index["campaigns"][str(fourth)] = {
            "leads_read": 1, "leads_reported": 1, "complete": True}
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        cell = self.cell(MEMBER)
        self.assertEqual(preflight.EXCLUDED, cell["cell"])
        self.assertIn(str(fourth), cell["why"])

    def test_the_listings_own_owner_field_is_ignored(self):
        """The authority carries `owner`, set from a retyped literal that
        disagrees with the declaration in both directions. A rule that
        trusted it would clear a member of a declared internal campaign."""
        index = self.listing(members=[(MEMBER["email"], self.internal)])
        index["campaigns"][str(self.internal)]["owner"] = "ours"
        for row in index["by_email"].values():
            for touch in row["touches"]:
                touch["owner"] = "ours"
        with io.open(self.paths["campaign_lead_rows"], "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump(index, handle, indent=1, sort_keys=True)
        self.state = preflight._planted_state(self.tmp,
                                              paths=self.paths)[0]
        self.assertEqual(preflight.EXCLUDED, self.cell(MEMBER)["cell"])

    def test_the_classifier_is_the_one_providerwrites_owns(self):
        """Not a copy of it. If the three states ever change, this fails and
        the rule has to be re-read against them."""
        self.assertEqual(("resonate_os", "resonate_internal", "unknown"),
                         providerwrites.OWNERSHIP)
        self.assertEqual(
            {"email": "bison", "linkedin": "heyreach"},
            providerwrites.DECLARED_CHANNELS)


class UndecidedIsNotAnExclusion(unittest.TestCase):
    """Every instance is truthy, which is the trap."""

    def test_a_rule_returning_undecided_is_unknown_and_not_excluded(self):
        tmp = tempfile.mkdtemp(prefix="rga-0200-u-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        state, paths = preflight._planted_state(tmp)
        rule = dict(preflight.RULES[0], name="undecided_rule",
                    ask=lambda ctx: preflight.Undecided("planted reason"))
        with mock.patch.object(preflight, "RULES", (rule,)), \
                mock.patch.object(preflight, "RULE_NAMES",
                                  ("undecided_rule",)):
            with preflight._pointed(paths):
                row = preflight.evaluate(STRANGER, state=state)
        cell = row["cells"]["undecided_rule"]
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("planted reason", cell["why"])
        self.assertNotIn("undecided_rule", row["excluded_by"])
        # AND IT IS TRUTHY, which is the whole reason the branch is ordered
        # the way it is.
        self.assertTrue(preflight.Undecided("x"))

    def test_undecided_on_a_partial_read_is_not_an_exclusion_either(self):
        """The other branch, which `fires_on_partial` reaches - and which had
        the same trap."""
        tmp = tempfile.mkdtemp(prefix="rga-0200-u2-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        state, paths = preflight._planted_state(tmp, empty=("queue",))
        rule = dict(preflight.RULES[0], name="partial_rule",
                    needs=("queue",), fires_on_partial=True,
                    ask=lambda ctx: preflight.Undecided("planted reason"))
        with mock.patch.object(preflight, "RULES", (rule,)), \
                mock.patch.object(preflight, "RULE_NAMES", ("partial_rule",)):
            with preflight._pointed(paths):
                row = preflight.evaluate(STRANGER, state=state)
        cell = row["cells"]["partial_rule"]
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("could not answer", cell["why"])
        self.assertIn("planted reason", cell["why"])

    def test_a_string_is_still_an_exclusion(self):
        """The control: the ordering must not have broken the normal case."""
        tmp = tempfile.mkdtemp(prefix="rga-0200-u3-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        state, paths = preflight._planted_state(tmp)
        rule = dict(preflight.RULES[0], name="string_rule",
                    ask=lambda ctx: "a planted reason")
        with mock.patch.object(preflight, "RULES", (rule,)), \
                mock.patch.object(preflight, "RULE_NAMES", ("string_rule",)):
            with preflight._pointed(paths):
                row = preflight.evaluate(STRANGER, state=state)
        self.assertEqual(preflight.EXCLUDED,
                         row["cells"]["string_rule"]["cell"])


class TheTwoNewControlsCanBothGoRed(unittest.TestCase):

    def test_controls_six_and_seven_hold(self):
        rows = preflight.controls()
        self.assertEqual(7, len(rows))
        self.assertEqual([preflight.PRESENT_POPULATED, preflight.EXCLUDED,
                          True, 1], rows[5]["observed"])
        self.assertEqual([preflight.PRESENT_POPULATED, preflight.PASS],
                         rows[6]["observed"])

    def test_a_rule_that_ignores_membership_breaks_control_six_only(self):
        """§4: weaken the rule so membership is ignored. Control 6 must go
        red; control 7 must NOT, because it is the row that would stay green
        under a rule that sees nothing - which is why both exist."""
        real = campaignmembership.lookup

        def blind(index, email=None):
            found = real(index, email=email)
            found["campaigns"] = []
            return found

        with mock.patch.object(campaignmembership, "lookup", blind):
            rows = preflight.controls()
        self.assertFalse(rows[5]["ok"],
                         "a membership check that ignores membership passed "
                         "control 6")
        self.assertTrue(rows[6]["ok"],
                        "control 7 should not move: a blind rule still "
                        "clears a non-member")

    def test_a_rule_that_answers_unknown_to_everybody_breaks_control_seven(
            self):
        """And the other direction. Without control 7, a rule that refused to
        answer anything would pass control 6 and the exit code both."""
        def never(ctx):
            return preflight.Undecided("planted: answers nothing")

        rule = [r for r in preflight.RULES if r["name"] == RULE][0]
        weakened = tuple(dict(r, ask=never) if r["name"] == RULE else r
                         for r in preflight.RULES)
        self.assertTrue(callable(rule["ask"]))
        with mock.patch.object(preflight, "RULES", weakened):
            rows = preflight.controls()
        self.assertFalse(rows[6]["ok"],
                         "an all-UNKNOWN rule passed control 7")
        self.assertFalse(rows[5]["ok"],
                         "and control 6 too, since UNKNOWN is not EXCLUDED")


class TheProducerGapIsPinnedInBothDirections(unittest.TestCase):
    """The authority's producer exists and is not quite good enough. Both
    halves pinned, so the claim cannot outlive the defect OR be forgotten."""

    def producer(self):
        return io.open(PRODUCER, encoding="utf-8").read()

    def test_the_producer_still_discards_the_providers_own_total(self):
        """`page_rows, _total = bison._paged(...)`. If somebody keeps that
        total, this test fails - and `campaignmembership`'s PROVEN COMPLETE
        paragraph has to be rewritten, because a walk could then prove
        itself and the rule could clear somebody."""
        self.assertIn("page_rows, _total = bison._paged(", self.producer())

    def test_the_producer_sets_complete_only_in_its_except_branch(self):
        source = self.producer()
        self.assertEqual(1, source.count("complete = False"))
        before = source.index("complete = False")
        self.assertIn("except Exception",
                      source[max(0, before - 400):before])

    def test_the_producers_owner_literal_disagrees_with_the_declaration(self):
        """MEASURED, in both directions, from the two files themselves. This
        is why the `owner` field is ignored - and if either file changes so
        that they agree, this test fails and that paragraph is stale."""
        source = self.producer()
        match = re.search(r"CLIENT_EMAIL_CAMPAIGNS = \{([0-9,\s]+)\}", source)
        self.assertIsNotNone(match, "the literal moved; re-read the producer")
        literal = {int(n) for n in match.group(1).split(",") if n.strip()}
        declared = {int(c) for c in providerwrites.declared_internal()[
            providerwrites.DECLARED_CHANNELS["email"]]}
        self.assertTrue(declared, "config/internal-campaigns.txt declares "
                                  "nothing; this test is about a conflict "
                                  "between two populated sources")
        self.assertTrue(declared - literal,
                        "declared-internal campaigns the producer does not "
                        "call the client's: expected a non-empty difference")
        self.assertTrue(literal - declared,
                        "campaigns the producer calls the client's that "
                        "nobody declared: expected a non-empty difference")

    def test_the_command_in_the_contract_is_the_script_that_exists(self):
        """A command named in a refusal has to be runnable, or the refusal
        sends somebody looking for a script nobody wrote."""
        self.assertTrue(os.path.exists(PRODUCER))
        self.assertIn("build_collision_index",
                      campaignmembership.HOW_TO_PRODUCE)
        self.assertIn("py -3 scripts/build_collision_index.py",
                      campaignmembership.HOW_TO_PRODUCE)

    def test_the_authority_path_is_the_one_the_producer_writes(self):
        """Both resolve beside the queue, by the same rule, so the reader
        cannot read one file while the operator fills another."""
        source = self.producer()
        self.assertIn("collision-index.json", source)
        self.assertIn("os.path.dirname(store.queue_path())", source)
        self.assertTrue(campaignmembership.path().endswith(
            "collision-index.json"))


class NothingHereCarriesARealAddressOrCohort(unittest.TestCase):

    ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
    RESERVED = ("example.test", "example.invalid", "other.invalid",
                "example.com", "example.org", "test", "invalid", "localhost")

    def test_no_real_address_in_this_file_or_the_new_module(self):
        for path in (os.path.abspath(__file__),
                     os.path.join(ROOT, "src", "campaignmembership.py"),
                     os.path.join(ROOT, "src", "preflight.py")):
            text = io.open(path, encoding="utf-8").read()
            found = []
            for match in self.ADDRESS.finditer(text):
                domain = match.group(1).lower()
                if any(domain == r or domain.endswith("." + r)
                       for r in self.RESERVED):
                    continue
                found.append(match.group(0))
            with self.subTest(file=os.path.basename(path)):
                self.assertEqual([], found)

    def test_the_new_module_writes_nothing(self):
        """READ ONLY, asserted. It is a reader of an authority somebody else
        produces, and a reader that can write is a reader that can corrupt
        the thing it is judging."""
        source = io.open(os.path.join(ROOT, "src", "campaignmembership.py"),
                         encoding="utf-8").read()
        for banned in ('"w"', "'w'", '"a"', "'a'", "os.replace(",
                       "json.dump("):
            self.assertNotIn(banned, source)

    def test_the_new_module_makes_no_provider_call(self):
        tree = ast.parse(io.open(
            os.path.join(ROOT, "src", "campaignmembership.py"),
            encoding="utf-8").read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
        self.assertEqual([], sorted(n for n in imported
                                    if n.endswith("bison")
                                    or n.endswith("heyreach")
                                    or n == "providers"))


if __name__ == "__main__":
    unittest.main()
