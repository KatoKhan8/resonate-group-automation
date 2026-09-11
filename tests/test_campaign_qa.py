"""Plan-level QA: what a reviewer needs before approving an ABM campaign.

`qa.py` checks the drafts, one message at a time. None of what this file
tests is visible from a single message:

  * a sender nobody authorised, appearing in step 27 of a 39-node cadence
  * a step that never says which decision maker it is for
  * a provider action nothing has validated
  * four correct sequences that together reach one person five times a week

Blocking is a policy decision here, not a severity. A finding blocks when
proceeding would do something this system exists to prevent; everything else
warns, because a reviewer blocked on untidiness learns to override blocks.
"""
import datetime
import unittest

from src import cadencegraph as cg, campaignqa, events
from src import senderidentity as si, senderteam as st, store
from tests.campaignbase import CampaignTest

WS = "productive"


class QATest(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install([
            si.new_sender(WS, "anna", "Anna Novak"),
            si.new_sender(WS, "mark", "Mark Weber"),
            si.new_sender(WS, "petar", "Petar Horvat"),
            si.new_sender(WS, "sara_s", "Sara Simic"),
            si.new_email_account(WS, "anna07", "anna", "a@productive.test"),
            si.new_email_account(WS, "mark02", "mark", "m@productive.test"),
            si.new_linkedin_account(WS, "petar-li", "petar",
                                    "https://www.linkedin.com/in/p"),
            si.new_linkedin_account(WS, "sara-li", "sara_s",
                                    "https://www.linkedin.com/in/s"),
        ])
        st.install([st.new_team(WS, "alpha", "Team Alpha",
                                email_senders=["anna", "mark"],
                                linkedin_senders=["petar", "sara_s"])])

    def record(self, rid="acme"):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            {"key": "john", "name": "John Smith", "title": "COO",
             "email": "j@acme.test", "selected": True},
            {"key": "sarah", "name": "Sarah Jones", "title": "CEO",
             "email": "s@acme.test", "selected": True},
        ]
        store.save([rec])
        return rec

    def campaign(self, rec):
        from src import campaigns as campaign_store

        campaign = campaign_store.new_campaign("c1", WS, "C1")
        campaign["record_ids"] = [rec["id"]]
        return campaign

    def review(self, graph, rec=None, config=None):
        rec = rec or self.record()
        return campaignqa.review(self.repo(), self.campaign(rec), graph=graph,
                                 recs=[rec], config=config)

    def repo(self):
        from src import repo as repo_module

        return repo_module.Repo.for_client(WS)

    def full(self, **senders):
        from src.web import democadence

        return democadence.build(**senders)

    def blocking(self, result):
        return [f["why"] for f in result["blocking"]]


class ARealisticPlanPasses(QATest):

    def test_the_full_cadence_has_nothing_blocking(self):
        result = self.review(self.full())
        self.assertEqual(self.blocking(result), [])

    def test_it_still_says_the_pacing_limits_are_defaults(self):
        """Passing is not the same as configured."""
        result = self.review(self.full())
        self.assertTrue(any("defaults are in force" in f["why"]
                            for f in result["findings"]))

    def test_configuring_the_limits_removes_that_warning(self):
        config = {"fatigue": {"contact": {"max_touches_per_week": 4,
                                          "min_hours_between_touches": 20,
                                          "max_touches_total": 15},
                              "account": {"max_active_contacts": 3,
                                          "min_hours_between_first_touches": 20,
                                          "max_touches_per_week": 9}}}
        result = self.review(self.full(), config=config)
        self.assertFalse(any("defaults are in force" in f["why"]
                             for f in result["findings"]))


class WhatBlocks(QATest):

    def test_a_sender_outside_the_team(self):
        result = self.review(self.full(second_email="outsider"))
        blocking = self.blocking(result)
        self.assertTrue(blocking)
        self.assertTrue(any("outside the team" in why for why in blocking),
                        blocking)
        self.assertTrue(any("outsider" in why for why in blocking))

    def test_one_finding_per_offending_human_not_per_node(self):
        """Eight identical rows about one person is a list nobody reads.

        The graph names `outsider` on four nodes. Both `senderteam` and
        `cadencegraph` can report it, which is why `_structure` filters the
        cadencegraph variant out - a reviewer reading the same violation
        eight times under two headings learns to skim.
        """
        result = self.review(self.full(second_email="outsider"))
        team_findings = [f for f in result["blocking"]
                         if "outsider" in f["why"]]
        self.assertEqual(len(team_findings), 1, team_findings)

    def test_an_unvalidated_provider_action(self):
        graph = self.full()
        graph["nodes"]["react"] = cg.node("react", "post_reaction",
                                          sender_id="petar",
                                          contact_role="primary")
        cg.connect(graph, "done", "react")
        blocking = self.blocking(self.review(graph))
        self.assertTrue(any("nothing in this build has validated" in why
                            for why in blocking))

    def test_it_is_reported_once_not_by_two_checks(self):
        graph = self.full()
        graph["nodes"]["react"] = cg.node("react", "post_reaction",
                                          sender_id="petar",
                                          contact_role="primary")
        cg.connect(graph, "done", "react")
        result = self.review(graph)
        about = [f for f in result["blocking"] if "React to a post" in
                 f["why"]]
        self.assertEqual(len(about), 1)

    def test_a_step_that_does_not_say_who_it_is_for(self):
        graph = cg.graph("x", [cg.node("a", "email", day=1,
                                       sender_id="anna")], "a")
        blocking = self.blocking(self.review(graph))
        self.assertTrue(any("which decision maker" in why
                            for why in blocking))

    def test_a_cadence_that_loops(self):
        nodes = [cg.node("a", "email", day=1, sender_id="anna",
                         contact_role="primary"),
                 cg.node("b", "email", day=2, sender_id="anna",
                         contact_role="primary")]
        graph = cg.graph("loop", nodes, "a")
        cg.connect(graph, "a", "b")
        cg.connect(graph, "b", "a")
        self.assertTrue(any("loops back" in why
                            for why in self.blocking(self.review(graph))))

    def test_a_contact_already_past_a_pacing_limit(self):
        """THE WEEK IS THE WEEK BEFORE NOW, so the fixture has to be recent.

        These were three fixed dates in August. `fatigue` measured its window
        from the most recent touch rather than from the proposed action, so
        three touches a day apart were "three touches this week" however long
        ago they happened - and this test went on passing while saying nothing
        about pacing. Dates relative to now keep it asserting what it claims.
        """
        rec = self.record()
        base = datetime.datetime.now(datetime.timezone.utc)
        for day, at in enumerate(
                [(base - datetime.timedelta(days=n)).isoformat()
                 for n in (3, 2, 1)], start=1):
            events.record(rec, events.PUSH_MARKED, contact_key="john",
                          channel="email", day=day, at=at, sender_id="anna")
        blocking = self.blocking(self.review(self.full(), rec=rec))
        self.assertTrue(any("pacing limit" in why for why in blocking))


class WhatOnlyWarns(QATest):

    def test_a_cadence_that_never_checks_for_a_reply(self):
        graph = cg.graph("flat", [cg.node("a", "email", day=1,
                                          sender_id="anna",
                                          contact_role="primary")], "a")
        result = self.review(graph)
        self.assertEqual(self.blocking(result), [])
        self.assertTrue(any("branches on whether the contact replied"
                            in f["why"] for f in result["findings"]))

    def test_no_cadence_graph_at_all(self):
        result = self.review(None)
        self.assertEqual(self.blocking(result), [])
        self.assertTrue(any("legacy linear cadence" in f["why"]
                            for f in result["findings"]))

    def test_a_handoff_with_every_reference_switched_off(self):
        result = self.review(self.full(),
                             config={"outreach": {
                                 "claim_same_contact": "off",
                                 "claim_colleague": "off",
                                 "claim_referral": "off"}})
        self.assertTrue(any("carry no context" in f["why"]
                            for f in result["findings"]))


class EveryVariantIsCheckedNotJustTheFirst(QATest):
    """A campaign is not safe because four of five variants are.

    A fifth of the audience receives the fifth one, so QA reads all of
    them and the worst answer is the answer.
    """

    def with_variants(self, entries, step="d1"):
        from src import variants as V

        graph = self.full()
        target = None
        for node in graph["nodes"].values():
            if V.is_message_node(node):
                target = node
                break
        self.assertIsNotNone(target, "the demo cadence has no message step")
        target["variants"] = entries
        return graph, target

    def five(self):
        from src import variants as V

        # Real length: `lint` refuses a body too short to be a message,
        # and a fixture that could not pass the product's own lint is not
        # modelling a campaign.
        body = ("Quick one about how the reporting side of this usually "
                "works at your size. Most teams end up reconciling the "
                "numbers after the month has closed, which is after the "
                "point where anything could have been done about them. "
                "Worth a short conversation, or is this already handled?")
        return [V.variant(f"v{i}", style, subject=f"a question about {i}",
                          body=body)
                for i, style in enumerate(
                    ("short_direct", "casual", "professional",
                     "consultative", "problem_led"), start=1)]

    def test_a_clean_experiment_raises_nothing_blocking(self):
        graph, _ = self.with_variants(self.five())
        result = self.review(graph)
        variant_blocks = [f for f in result["blocking"]
                          if "variant" in f["why"]]
        self.assertEqual(variant_blocks, [], variant_blocks)

    def test_one_bad_variant_blocks_the_campaign(self):
        """Variant D fails lint; A, B, C and E are clean."""
        entries = self.five()
        entries[3]["body"] = entries[3]["body"] + " — and more."
        graph, node = self.with_variants(entries)
        blocking = self.blocking(self.review(graph))
        self.assertTrue(any("v4" in why for why in blocking), blocking)

    def test_the_finding_names_the_step_and_the_variant(self):
        entries = self.five()
        entries[3]["body"] = entries[3]["body"] + " — and more."
        graph, node = self.with_variants(entries)
        found = [f for f in self.review(graph)["blocking"] if "v4" in f["why"]]
        self.assertTrue(found)
        self.assertEqual(found[0]["where"], node["key"])
        self.assertIn("consultative", found[0]["why"])

    def test_a_message_step_with_no_experiment_warns(self):
        graph = self.full()
        result = self.review(graph)
        self.assertTrue(any("no copy experiment" in f["why"]
                            for f in result["findings"]))

    def test_a_structural_problem_in_the_experiment_blocks(self):
        from src import variants as V

        entries = self.five()
        entries[1] = V.variant("v1", "casual", subject="s", body="b")
        graph, _ = self.with_variants(entries)
        self.assertTrue(any("share the id" in why
                            for why in self.blocking(self.review(graph))))


class TheFindingsAreUsable(QATest):

    def test_every_finding_belongs_to_a_group(self):
        for finding in self.review(self.full())["findings"]:
            self.assertIn(finding["group"], campaignqa.GROUPS)

    def test_every_blocking_finding_says_what_to_do(self):
        result = self.review(self.full(second_email="outsider"))
        for finding in result["blocking"]:
            self.assertTrue(finding["fix"] or finding["where"],
                            finding["why"])

    def test_the_state_is_the_worst_level_present(self):
        self.assertEqual(
            self.review(self.full(second_email="outsider"))["state"],
            campaignqa.BLOCK)
        self.assertIn(self.review(self.full())["state"],
                      (campaignqa.OK, campaignqa.WARN))

    def test_it_reports_the_team_and_the_graph(self):
        result = self.review(self.full())
        self.assertEqual((result["team"] or {}).get("name"), "Team Alpha")
        self.assertGreaterEqual(result["graph"]["nodes"], 30)


class TheTemplatePreviewDoesNotManufactureItsOwnBlock(QATest):
    """A stock shape, unmodified, must not open with a red block.

    The preview used to fill a template from the roster in whatever order it
    came back, so it could pick somebody the outreach team does not contain -
    and then report them as a blocking violation of a team the reader never
    chose. A reviewer who meets two blocks on an untouched template learns
    that blocks are decoration.
    """

    def setUp(self):
        super().setUp()
        # Somebody with both channels who is deliberately not on the team,
        # and listed first so order alone cannot make this pass.
        si.install([
            si.new_sender(WS, "outsider", "Olga Utsider"),
            si.new_email_account(WS, "out01", "outsider", "o@productive.test"),
            si.new_linkedin_account(WS, "out-li", "outsider",
                                    "https://www.linkedin.com/in/o"),
            si.new_sender(WS, "anna", "Anna Novak"),
            si.new_sender(WS, "petar", "Petar Horvat"),
            si.new_email_account(WS, "anna07", "anna", "a@productive.test"),
            si.new_linkedin_account(WS, "petar-li", "petar",
                                    "https://www.linkedin.com/in/p"),
        ])
        st.install([st.new_team(WS, "alpha", "Team Alpha",
                                email_senders=["anna"],
                                linkedin_senders=["petar"])])

    def view(self):
        from src.web import api

        return api.cadence_view(self.repo(), template="standard")

    def test_it_picks_senders_the_team_authorises(self):
        data = self.view()
        self.assertIsNotNone(data)
        offenders = [f["why"] for f in data["findings"]
                     if "outreach team" in f["why"]]
        self.assertEqual(offenders, [], offenders)

    def test_the_outsider_is_reachable_but_simply_not_chosen(self):
        """Not passing because the roster is too small to fail."""
        able = [r for r in si.load()
                if r.get("kind") == "linkedin_account"
                and r.get("sender_id") == "outsider"]
        self.assertTrue(able)



class TheClaimScanSaysHowMuchItRead(CampaignTest):
    """A safety check that inspects two hundred of thirty thousand and
    reports like it read the campaign is the worst kind of green: the
    reviewer cannot tell "nothing is wrong" from "nothing was looked at".
    """

    def findings(self, count):
        recs = []
        for index in range(count):
            rec = store.new_record(f"q{index}", "domains", WS,
                                   f"Company {index}", f"q{index}.test")
            rec["contacts"] = [{"key": "a", "name": "A Person",
                                "email": f"a@q{index}.test",
                                "selected": True}]
            recs.append(rec)
        graph = {"nodes": {}}
        return campaignqa._claims(recs, graph, WS, self.config, None)

    def test_a_capped_scan_says_what_it_covered(self):
        found = self.findings(campaignqa_cap() + 5)
        notes = [f for f in found if "not all of them" in f["why"]]
        self.assertEqual(len(notes), 1)
        self.assertIn(str(campaignqa_cap()), notes[0]["why"])

    def test_a_full_scan_says_nothing_extra(self):
        """The note is only interesting when something was skipped."""
        found = self.findings(3)
        self.assertEqual([f for f in found if "not all of them" in f["why"]],
                         [])

    def test_the_note_does_not_read_as_an_all_clear(self):
        found = self.findings(campaignqa_cap() + 5)
        note = [f for f in found if "not all of them" in f["why"]][0]
        self.assertIn("unchecked", note["fix"])


def campaignqa_cap():
    return campaignqa.CLAIM_SCAN_CAP


if __name__ == "__main__":
    unittest.main()
