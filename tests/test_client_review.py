"""The client's ruling, and getting it back without trusting the file.

This is the one file in the product that leaves the building, is edited by
somebody who is not us, in a spreadsheet, and comes back. Every property
here follows from that.

**The id is the identity.** A row whose id is missing, unknown or repeated
is refused rather than matched on company name. Name matching here would
mean a client's "do not contact" landing on a different company that
happened to be spelled similarly.

**Canonical columns are echoed and compared.** A changed `domain` is not
an edit to accept; it is a file that has been through something.

**Statuses are a closed set.** Free text in a decision column is a
decision nobody can act on consistently.

**Silence is not a decision.** A row the client did not return is a row
they did not get to.
"""
import csv
import io
import os
import shutil
import tempfile
import unittest

from src import clientreview as cr, discovery, export, store
from tests.base import ProviderTest

WS = "productive"
BATCH = "b1"


class ReviewTest(ProviderTest):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-review-")
        self._env = {k: os.environ.get(k) for k in
                     ("QUEUE", "CAMPAIGNS", "WORKSPACES", "AUDIT",
                      "CLIENT_REVIEW", "DISCOVERY", "CLIENTS_DIR", "OUT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.environ["OUT"] = os.path.join(self.tmp, "out")

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def candidates(self, *domains):
        return [discovery.candidate(
            WS, domain, evidence="digital agency, Berlin, 60 staff listed",
            company=domain.split(".")[0].title(),
            facts={"country": "Germany"}) for domain in domains]

    def sent(self, *domains):
        cands = self.candidates(*domains)
        return cands, cr.fingerprint(WS, BATCH, cands)

    def returned(self, sent, decisions, changes=None):
        """Build the file the client sends back.

        `decisions` maps domain -> status. `changes` maps domain -> a dict
        of canonical columns to tamper with.
        """
        by_domain = {row["domain"]: (entry_id, row)
                     for entry_id, row in sent.items()}
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(cr.COLUMNS)
        for domain, status in decisions.items():
            entry_id, row = by_domain[domain]
            values = dict(row)
            values.update((changes or {}).get(domain) or {})
            writer.writerow(
                [entry_id] + [values.get(c, "") for c in cr.CANONICAL_COLUMNS]
                + [status, "", ""])
        return out.getvalue().encode()


class TheClosedSetOfStatuses(unittest.TestCase):

    def test_every_status_has_an_effect_and_a_label(self):
        self.assertEqual(set(cr.STATUSES), set(cr.EFFECT))
        self.assertEqual(set(cr.STATUSES), set(cr.STATUS_LABEL))

    def test_only_a_removal_request_suppresses(self):
        """The strongest thing on the list, and the only one that writes
        to suppression."""
        suppressing = [s for s in cr.STATUSES
                       if cr.EFFECT[s] == cr.SUPPRESS]
        self.assertEqual(suppressing, [cr.DO_NOT_CONTACT])

    def test_a_relationship_status_excludes_without_suppressing(self):
        """The company may be worked later by a person, through another
        motion. It just may not receive a cold sequence."""
        for status in (cr.EXISTING_CLIENT, cr.EXISTING_OPPORTUNITY,
                       cr.PARTNER, cr.ACTIVE_PROSPECT):
            self.assertEqual(cr.EFFECT[status], cr.EXCLUDE, status)

    def test_bad_fit_does_not_suppress(self):
        """A judgement about fit is not a removal request."""
        self.assertEqual(cr.EFFECT[cr.BAD_FIT], cr.EXCLUDE)

    def test_review_later_defers_rather_than_deciding(self):
        self.assertEqual(cr.EFFECT[cr.REVIEW_LATER], cr.DEFER)


class TheOutgoingFile(ReviewTest):

    def test_it_carries_a_stable_id_per_candidate(self):
        cands, sent = self.sent("alpha-test.example", "beta-test.example")
        self.assertEqual(len(sent), 2)
        again = cr.fingerprint(WS, BATCH, cands)
        self.assertEqual(sorted(sent), sorted(again))

    def test_the_id_differs_between_workspaces(self):
        """So a file from one client cannot be applied to another: the
        ids simply are not found."""
        self.assertNotEqual(cr.candidate_id(WS, BATCH, "a-test.example"),
                            cr.candidate_id("other", BATCH, "a-test.example"))

    def test_the_id_differs_between_batches(self):
        self.assertNotEqual(cr.candidate_id(WS, "b1", "a-test.example"),
                            cr.candidate_id(WS, "b2", "a-test.example"))

    def test_every_cell_is_guarded_against_formula_execution(self):
        """It is opened in a spreadsheet by somebody who is not us."""
        cands = [discovery.candidate(
            WS, "evil-test.example", company="=cmd|calc",
            evidence="=HYPERLINK(\"http://x\") agency in Berlin")]
        text = cr.to_csv(WS, BATCH, cands)
        for line in text.splitlines()[1:]:
            for cell in next(csv.reader([line])):
                self.assertFalse(export.is_dangerous(cell), cell)

    def test_the_editable_columns_are_empty_on_the_way_out(self):
        cands, _ = self.sent("alpha-test.example")
        rows = cr.rows_for(WS, BATCH, cands)
        for column in cr.EDITABLE_COLUMNS:
            self.assertEqual(rows[0][column], "")


class ComingBack(ReviewTest):

    def test_an_honest_file_applies_every_decision(self):
        cands, sent = self.sent("alpha-test.example", "beta-test.example")
        data = self.returned(sent, {"alpha-test.example": cr.DO_NOT_CONTACT,
                                    "beta-test.example": cr.APPROVED})
        out = cr.parse(data, WS, BATCH, sent)
        self.assertEqual(out["counts"]["decided"], 2)
        self.assertEqual(out["counts"][cr.SUPPRESS], 1)
        self.assertEqual(out["counts"][cr.PROCEED], 1)
        self.assertEqual(out["refused"], [])

    def test_a_changed_canonical_column_is_refused_and_named(self):
        """The attack this exists to stop: move a client's "do not
        contact" onto a different company."""
        cands, sent = self.sent("alpha-test.example")
        data = self.returned(
            sent, {"alpha-test.example": cr.DO_NOT_CONTACT},
            changes={"alpha-test.example": {"domain": "victim-test.example"}})
        out = cr.parse(data, WS, BATCH, sent)
        self.assertEqual(out["applied"], [])
        self.assertIn("domain", out["refused"][0]["why"])

    def test_a_changed_score_is_refused_too(self):
        cands, sent = self.sent("alpha-test.example")
        data = self.returned(
            sent, {"alpha-test.example": cr.APPROVED},
            changes={"alpha-test.example": {"icp_tier": "A"}})
        out = cr.parse(data, WS, BATCH, sent)
        self.assertIn("icp_tier", out["refused"][0]["why"])

    def test_an_unknown_id_is_refused(self):
        cands, sent = self.sent("alpha-test.example")
        data = self.returned(sent, {"alpha-test.example": cr.APPROVED})
        data = data.replace(list(sent)[0].encode(), b"0000000000000000")
        out = cr.parse(data, WS, BATCH, sent)
        self.assertEqual(out["applied"], [])
        self.assertIn("not a candidate", out["refused"][0]["why"])

    def test_a_file_from_another_workspace_matches_nothing(self):
        """Its ids were hashed with a different workspace."""
        cands = self.candidates("alpha-test.example")
        theirs = cr.fingerprint("contactout", BATCH, cands)
        ours = cr.fingerprint(WS, BATCH, cands)
        data = self.returned(theirs, {"alpha-test.example": cr.APPROVED})
        out = cr.parse(data, WS, BATCH, ours)
        self.assertEqual(out["applied"], [])
        self.assertEqual(out["counts"]["refused"], 1)

    def test_a_duplicate_id_takes_the_first_and_refuses_the_second(self):
        cands, sent = self.sent("alpha-test.example")
        one = self.returned(sent, {"alpha-test.example": cr.APPROVED})
        body = one.decode().strip().split("\n")
        data = ("\n".join(body + [body[-1]]) + "\n").encode()
        out = cr.parse(data, WS, BATCH, sent)
        self.assertEqual(len(out["applied"]), 1)
        self.assertIn("more than once", out["refused"][0]["why"])

    def test_an_invalid_status_is_refused_with_the_list(self):
        cands, sent = self.sent("alpha-test.example")
        data = self.returned(sent, {"alpha-test.example": "maybe later"})
        out = cr.parse(data, WS, BATCH, sent)
        self.assertEqual(out["applied"], [])
        self.assertIn("approved", out["refused"][0]["why"])

    def test_a_status_is_read_forgivingly_but_still_from_the_set(self):
        """"Do Not Contact" and "do-not-contact" are the same decision. A
        spreadsheet will produce both."""
        cands, sent = self.sent("alpha-test.example")
        for typed in ("Do Not Contact", "DO-NOT-CONTACT", " do_not_contact "):
            data = self.returned(sent, {"alpha-test.example": typed})
            out = cr.parse(data, WS, BATCH, sent)
            self.assertEqual(out["applied"][0]["status"], cr.DO_NOT_CONTACT,
                             typed)

    def test_one_bad_row_does_not_cost_the_others(self):
        """A client who made four hundred decisions should not lose them
        to one mangled line."""
        cands, sent = self.sent("alpha-test.example", "beta-test.example")
        data = self.returned(
            sent, {"alpha-test.example": "nonsense",
                   "beta-test.example": cr.APPROVED})
        out = cr.parse(data, WS, BATCH, sent)
        self.assertEqual(len(out["applied"]), 1)
        self.assertEqual(len(out["refused"]), 1)

    def test_a_blank_status_is_not_a_decision(self):
        cands, sent = self.sent("alpha-test.example")
        data = self.returned(sent, {"alpha-test.example": ""})
        out = cr.parse(data, WS, BATCH, sent)
        self.assertEqual(out["applied"], [])
        self.assertEqual(out["counts"]["left_blank"], 1)

    def test_a_row_never_returned_is_reported_not_assumed(self):
        """Silence is not a rejection. It is a row they did not get to."""
        cands, sent = self.sent("alpha-test.example", "beta-test.example")
        data = self.returned(sent, {"alpha-test.example": cr.APPROVED})
        out = cr.parse(data, WS, BATCH, sent)
        self.assertEqual(out["counts"]["never_returned"], 1)
        self.assertEqual(len(out["never_returned"]), 1)

    def test_nothing_is_committed_by_parsing(self):
        cands, sent = self.sent("alpha-test.example")
        data = self.returned(sent, {"alpha-test.example": cr.DO_NOT_CONTACT})
        out = cr.parse(data, WS, BATCH, sent)
        self.assertFalse(out["committed"])
        self.assertEqual(cr.load(WS), [])


class MalformedFiles(ReviewTest):

    def test_an_empty_file_is_refused(self):
        cands, sent = self.sent("alpha-test.example")
        with self.assertRaises(cr.ReviewRefused):
            cr.parse(b"", WS, BATCH, sent)

    def test_a_file_with_no_id_column_is_refused(self):
        cands, sent = self.sent("alpha-test.example")
        with self.assertRaises(cr.ReviewRefused) as caught:
            cr.parse(b"domain,client_status\na.test,approved\n",
                     WS, BATCH, sent)
        self.assertIn(cr.ID_COLUMN, str(caught.exception))

    def test_a_file_with_no_status_column_is_refused(self):
        cands, sent = self.sent("alpha-test.example")
        with self.assertRaises(cr.ReviewRefused):
            cr.parse((cr.ID_COLUMN + ",domain\nx,a.test\n").encode(),
                     WS, BATCH, sent)

    def test_an_oversized_file_is_refused(self):
        cands, sent = self.sent("alpha-test.example")
        with self.assertRaises(cr.ReviewRefused):
            cr.parse(b"x" * (cr.MAX_BYTES + 1), WS, BATCH, sent)

    def test_client_notes_are_stripped_of_control_characters(self):
        cands, sent = self.sent("alpha-test.example")
        entry_id = list(sent)[0]
        row = sent[entry_id]
        out_file = io.StringIO()
        writer = csv.writer(out_file)
        writer.writerow(cr.COLUMNS)
        writer.writerow(
            [entry_id] + [row[c] for c in cr.CANONICAL_COLUMNS]
            + ["approved", "bad\x00note", ""])
        parsed = cr.parse(out_file.getvalue().encode(), WS, BATCH, sent)
        self.assertEqual(parsed["refused"], [])
        self.assertNotIn("\x00", parsed["applied"][0]["notes"])
        self.assertIn("badnote", parsed["applied"][0]["notes"])


class LearningIsAnObservation(ReviewTest):

    def test_fit_judgements_are_separated_from_relationships(self):
        """"They are already our customer" says nothing about fit."""
        cands, sent = self.sent("alpha-test.example", "beta-test.example")
        data = self.returned(sent, {"alpha-test.example": cr.EXISTING_CLIENT,
                                    "beta-test.example": cr.BAD_FIT})
        signal = cr.learning_signal(cr.parse(data, WS, BATCH, sent))
        self.assertEqual(signal["judged"], 1)
        self.assertEqual(signal["rejected_on_fit"], 1)

    def test_it_says_it_is_not_an_icp_change(self):
        cands, sent = self.sent("alpha-test.example")
        data = self.returned(sent, {"alpha-test.example": cr.BAD_FIT})
        signal = cr.learning_signal(cr.parse(data, WS, BATCH, sent))
        self.assertIn("not a change to the ICP", signal["note"])

    def test_it_returns_nothing_that_acts(self):
        """Only an authorised person moves the ICP."""
        cands, sent = self.sent("alpha-test.example")
        data = self.returned(sent, {"alpha-test.example": cr.BAD_FIT})
        signal = cr.learning_signal(cr.parse(data, WS, BATCH, sent))
        self.assertEqual(set(signal) & {"apply", "icp", "changed"}, set())


class DecisionsAreRemembered(ReviewTest):

    def test_a_recorded_decision_is_readable_by_domain(self):
        cr.record([{"workspace": WS, "domain": "alpha-test.example",
                    "status": cr.EXISTING_CLIENT, "at": store.now()}])
        self.assertEqual(cr.decided(WS),
                         {"alpha-test.example": cr.EXISTING_CLIENT})

    def test_a_correction_supersedes_and_the_first_survives(self):
        cr.record([{"workspace": WS, "domain": "alpha-test.example",
                    "status": cr.BAD_FIT, "at": "2026-01-01"}])
        cr.record([{"workspace": WS, "domain": "alpha-test.example",
                    "status": cr.APPROVED, "at": "2026-02-01"}])
        self.assertEqual(cr.decided(WS)["alpha-test.example"], cr.APPROVED)
        self.assertEqual(len(cr.load(WS)), 2)

    def test_decisions_are_scoped_to_one_workspace(self):
        cr.record([{"workspace": WS, "domain": "a-test.example",
                    "status": cr.APPROVED}])
        cr.record([{"workspace": "contactout", "domain": "b-test.example",
                    "status": cr.APPROVED}])
        self.assertEqual(list(cr.decided(WS)), ["a-test.example"])

    def test_a_decision_must_name_its_workspace(self):
        with self.assertRaises(cr.ReviewRefused):
            cr.record([{"domain": "a-test.example", "status": cr.APPROVED}])

    def test_a_decided_company_is_never_discovered_again(self):
        """The whole point of remembering: the client told us once."""
        cr.record([{"workspace": WS, "domain": "alpha-test.example",
                    "status": cr.EXISTING_CLIENT}])
        universe = {"workspace": WS, "records": set(), "in_campaign": set(),
                    "suppressed": set(), "previous": set(),
                    "unavailable": [], "counts": {}}
        out = discovery.delta(self.candidates("alpha-test.example"),
                              universe, decided=cr.decided(WS))
        self.assertEqual(out["new"], [])
        self.assertEqual(out["excluded"][0]["verdict"],
                         discovery.CLIENT_DECIDED)


if __name__ == "__main__":
    unittest.main()
