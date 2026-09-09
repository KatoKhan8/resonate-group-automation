"""The report editor: a person writes the words, the system counts the numbers.

The property this file exists to defend:

    A manual edit cannot change a metric.

Not "does not by convention" - cannot. A draft has narrative fields and no
metric fields, so there is nowhere to put an edited number. The tests below
try to put one there several ways and each is refused by the shape of the
object rather than by a check somebody could remove.

The second property is versioning: editing appends, and a stored version is
never rewritten. "What did we tell them in July" has to be answerable.
"""
import os
import re
import shutil
import tempfile
import unittest
import zlib

from src import clientreport as cr
from src import reportdraft as rd
from src import store
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
OTHER = "ops@contactout.test"

WS = "productive"


def text_of(raw):
    found = []
    for stream in re.findall(rb"stream\n(.*?)\nendstream", raw, re.S):
        try:
            found += re.findall(r"\((.*?)\) Tj",
                                zlib.decompress(stream).decode("latin-1"))
        except zlib.error:
            continue
    out = []
    for piece in found:
        cleaned, i = [], 0
        while i < len(piece):
            if piece[i] == chr(92) and i + 1 < len(piece):
                cleaned.append(piece[i + 1])
                i += 2
            else:
                cleaned.append(piece[i])
                i += 1
        out.append("".join(cleaned))
    return "\n".join(out)


class DraftTest(unittest.TestCase):
    """A throwaway state directory, because these tests create real drafts.

    They did not have one. `rd.create` writes through
    `store.file_transaction`, which resolves `report-drafts.jsonl` beside the
    queue, so every run of this file appended to the developer's own
    `work/report-drafts.jsonl` - 4,944 rows of `a@b.test` drafts had
    accumulated there, sixteen per suite run since 2026-08-28. The queue
    itself was never at risk, because the queue was the only file the second
    barrier covered.

    The `WebTest` classes below always isolated. These four did not, and
    nothing said so until `store.refuse_production_write` started guarding
    every writer into `work/` rather than only the queue.
    """

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="rga-drafts-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        saved = {name: os.environ.get(name)
                 for name in ("QUEUE",) + store.STATE_OVERRIDES}
        self.addCleanup(self._restore_env, saved)
        store.use_directory(os.path.join(tmp, "work"))

    @staticmethod
    def _restore_env(saved):
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class TheDraftHasNowhereToPutAMetric(DraftTest):
    """The structural half of the guarantee."""

    def test_the_editable_blocks_are_all_prose(self):
        for key in rd.NARRATIVE_KEYS:
            self.assertIn(key, ("title", "summary", "takeaways",
                                "what_worked", "what_changed", "learned",
                                "next_steps"), key)

    def test_no_editable_block_is_a_number(self):
        forbidden = ("contacts", "replies", "sent", "positive", "meetings",
                     "rate", "count", "total", "funnel")
        for key in rd.NARRATIVE_KEYS:
            for word in forbidden:
                self.assertNotIn(word, key, f"{key} looks like a metric")

    def test_editing_an_unknown_block_is_refused(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        with self.assertRaises(rd.DraftError):
            rd.edit(draft["id"], "a@b.test",
                    narrative={"positive_replies": "999"})

    def test_a_custom_section_holds_text_not_markup(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        updated = rd.edit(draft["id"], "a@b.test", custom=[
            {"kind": "text", "heading": "A note",
             "body": "<script>alert(1)</script>"}])
        stored = updated["custom"][0]["body"]
        # Stored as text; the renderer escapes. What must not exist is a
        # path that treats it as markup.
        self.assertIn("script", stored)
        self.assertEqual(stored, "<script>alert(1)</script>")

    def test_an_unknown_custom_kind_is_refused(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        with self.assertRaises(rd.DraftError):
            rd.edit(draft["id"], "a@b.test",
                    custom=[{"kind": "html", "body": "x"}])

    def test_an_unknown_recommendation_kind_is_refused(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        with self.assertRaises(rd.DraftError):
            rd.edit(draft["id"], "a@b.test",
                    recommendations=[{"kind": "shout", "text": "x"}])


class VersionsAreAppendOnly(DraftTest):

    def draft(self):
        return rd.create(WS, cr.MONTHLY, "a@b.test", period="2026-07")

    def test_an_edit_makes_a_new_version(self):
        draft = self.draft()
        self.assertEqual(draft["version"], 1)
        updated = rd.edit(draft["id"], "a@b.test",
                          narrative={"summary": "first"})
        self.assertEqual(updated["version"], 2)

    def test_the_previous_version_is_kept(self):
        draft = self.draft()
        rd.edit(draft["id"], "a@b.test", narrative={"summary": "first"})
        second = rd.edit(draft["id"], "b@b.test",
                         narrative={"summary": "second"})
        self.assertEqual(len(second["history"]), 2)
        self.assertEqual(second["narrative"]["summary"], "second")
        self.assertEqual(second["history"][-1]["narrative"]["summary"],
                         "first")

    def test_each_version_records_who_made_it(self):
        draft = self.draft()
        updated = rd.edit(draft["id"], "somebody@resonate.test",
                          narrative={"summary": "x"})
        self.assertEqual(updated["updated_by"], "somebody@resonate.test")

    def test_editing_one_block_leaves_the_others_alone(self):
        draft = self.draft()
        rd.edit(draft["id"], "a@b.test", narrative={"summary": "kept"})
        updated = rd.edit(draft["id"], "a@b.test",
                          narrative={"what_worked": "new"})
        self.assertEqual(updated["narrative"]["summary"], "kept")
        self.assertEqual(updated["narrative"]["what_worked"], "new")

    def test_a_final_report_refuses_an_edit(self):
        draft = self.draft()
        rd.finalise(draft["id"], "a@b.test")
        with self.assertRaises(rd.DraftError):
            rd.edit(draft["id"], "a@b.test", narrative={"summary": "x"})

    def test_reopening_makes_a_version_rather_than_erasing_one(self):
        draft = self.draft()
        rd.edit(draft["id"], "a@b.test", narrative={"summary": "sent"})
        rd.finalise(draft["id"], "a@b.test")
        reopened = rd.reopen(draft["id"], "b@b.test")
        self.assertEqual(reopened["status"], rd.DRAFT)
        self.assertTrue(any(v["narrative"].get("summary") == "sent"
                            for v in reopened["history"]))


class SectionsAreOrderedByTheEditorAndBoundedByTheTemplate(DraftTest):

    def test_reordering_is_honoured(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        updated = rd.edit(draft["id"], "a@b.test",
                          sections=["replies", "summary", "funnel"])
        self.assertEqual(updated["sections"][:3],
                         ["replies", "summary", "funnel"])

    def test_a_section_the_template_lacks_is_dropped(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        updated = rd.edit(draft["id"], "a@b.test",
                          sections=["summary", "providers"])
        self.assertNotIn("providers", updated["sections"])

    def test_clearing_every_section_falls_back_to_the_template(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        updated = rd.edit(draft["id"], "a@b.test", sections=[])
        self.assertEqual(updated["sections"],
                         cr.sections_for(cr.MONTHLY))


class TheSeededNarrativeIsDeterministic(DraftTest):
    """No model writes into a document a client will read."""

    def data(self):
        return {"domains_uploaded": 100, "domains_qualified": 60,
                "contacts_found": 200, "contacts_verified": 150,
                "emails_pushed": 90, "replies": 12, "positive_replies": 4}

    def test_the_same_data_seeds_the_same_words(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        self.assertEqual(rd.seed_narrative(draft, self.data()),
                         rd.seed_narrative(draft, self.data()))

    def test_it_states_the_counted_figures(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        summary = rd.seed_narrative(draft, self.data())["summary"]
        self.assertIn("100", summary)
        self.assertIn("150", summary)

    def test_no_outreach_is_said_rather_than_shown_as_a_zero_rate(self):
        draft = rd.create(WS, cr.MONTHLY, "a@b.test")
        summary = rd.seed_narrative(draft, dict(self.data(),
                                                emails_pushed=0))["summary"]
        self.assertIn("no reply rate can be reported", summary)


class TheEditorOverHttp(WebTest):

    def new_draft(self, who=OPERATOR, template="monthly"):
        """Create a draft and identify it by diffing ids.

        Reading the first `draft=` out of the redirected page finds whatever
        the draft list happens to show first, and two drafts created in the
        same second tie. That made this helper return a *previous* test's
        draft and the version assertions fail for a reason unrelated to the
        code under test.
        """
        session = self.signin(who)
        before = {d["id"] for d in rd.for_workspace(WS)}
        session.post("/reporting/editor/new", {
            "csrf": session.csrf("/reporting/editor"),
            "template": template, "period": "2026-07-01 to 2026-07-31"})
        fresh = [d for d in rd.for_workspace(WS) if d["id"] not in before]
        self.assertEqual(len(fresh), 1, "no new draft was created")
        return session, fresh[0]["id"]

    def test_creating_a_draft_seeds_the_narrative(self):
        _, draft_id = self.new_draft()
        draft = rd.get(draft_id)
        self.assertTrue(draft["narrative"]["summary"])

    def test_the_editor_renders(self):
        session, draft_id = self.new_draft()
        status, body, _ = session.get("/reporting/editor?draft=" + draft_id)
        self.assertEqual(status, 200)
        self.assertIn("Narrative", body)
        self.assertIn("Executive summary", body)

    def test_it_shows_the_counted_figures_as_read_only(self):
        session, draft_id = self.new_draft()
        _, body, _ = session.get("/reporting/editor?draft=" + draft_id)
        self.assertIn("Figures in this report", body)
        self.assertIn("cannot change one", body)

    def test_saving_creates_a_version_and_keeps_the_metrics(self):
        session, draft_id = self.new_draft()
        before = rd.get(draft_id)["version"]
        session.post("/reporting/editor/save", {
            "csrf": session.csrf("/reporting/editor?draft=" + draft_id),
            "draft": draft_id, "n:summary": "Rewritten by a person.",
            "sections": ["summary", "funnel"]})
        after = rd.get(draft_id)
        self.assertGreater(after["version"], before)
        self.assertEqual(after["narrative"]["summary"],
                         "Rewritten by a person.")
        for key in after:
            self.assertNotIn(key, ("replies", "positive_replies", "contacts"))

    def test_the_exported_pdf_carries_the_edit_and_the_counted_numbers(self):
        session, draft_id = self.new_draft()
        session.post("/reporting/editor/save", {
            "csrf": session.csrf("/reporting/editor?draft=" + draft_id),
            "draft": draft_id,
            "n:summary": "A deliberately quiet month."})
        status, raw, headers = session.get_bytes(
            "/reporting/editor/export?draft=" + draft_id)
        self.assertEqual(status, 200)
        self.assertTrue(raw.startswith(b"%PDF"))
        drawn = text_of(raw)
        self.assertIn("A deliberately quiet month.", drawn)
        self.assertIn("Companies", drawn)

    def test_an_export_is_recorded_in_the_report_history(self):
        from src import reports as report_store

        session, draft_id = self.new_draft()
        before = len(report_store.for_workspace(WS))
        session.get_bytes("/reporting/editor/export?draft=" + draft_id)
        self.assertGreater(len(report_store.for_workspace(WS)), before)

    def test_marking_final_then_editing_is_refused(self):
        session, draft_id = self.new_draft()
        session.post("/reporting/editor/finalise", {
            "csrf": session.csrf("/reporting/editor?draft=" + draft_id),
            "draft": draft_id})
        self.assertEqual(rd.get(draft_id)["status"], rd.FINAL)
        status, _, _ = session.post("/reporting/editor/save", {
            "csrf": session.csrf("/reporting/editor?draft=" + draft_id),
            "draft": draft_id, "n:summary": "sneaked in"})
        self.assertEqual(status, 400)
        self.assertNotEqual(rd.get(draft_id)["narrative"].get("summary"),
                            "sneaked in")

    def test_hostile_text_in_a_block_renders_inert_on_the_screen(self):
        session, draft_id = self.new_draft()
        session.post("/reporting/editor/save", {
            "csrf": session.csrf("/reporting/editor?draft=" + draft_id),
            "draft": draft_id,
            "n:summary": "<script>alert(1)</script>"})
        _, body, _ = session.get("/reporting/editor?draft=" + draft_id)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)


class OneWorkspaceCannotEditAnothersDraft(WebTest):

    def their_draft(self):
        session = self.signin(OTHER)
        body = session.post("/reporting/editor/new", {
            "csrf": session.csrf("/reporting/editor"),
            "template": "monthly"})[1]
        return re.search(r"draft=(draft-[a-z0-9]+)", body).group(1)

    def test_reading_it_is_a_404(self):
        draft_id = self.their_draft()
        status, _, _ = self.signin(OPERATOR).get(
            "/reporting/editor?draft=" + draft_id)
        self.assertEqual(status, 404)

    def test_editing_it_is_refused_and_changes_nothing(self):
        draft_id = self.their_draft()
        before = dict(rd.get(draft_id)["narrative"])
        session = self.signin(OPERATOR)
        session.post("/reporting/editor/save", {
            "csrf": session.csrf("/reporting/editor"),
            "draft": draft_id, "n:summary": "hijacked"})
        self.assertEqual(rd.get(draft_id)["narrative"], before)

    def test_exporting_it_is_a_404(self):
        draft_id = self.their_draft()
        status, _, _ = self.signin(OPERATOR).get(
            "/reporting/editor/export?draft=" + draft_id)
        self.assertEqual(status, 404)

    def test_the_draft_list_shows_only_this_workspace(self):
        draft_id = self.their_draft()
        _, body, _ = self.signin(OPERATOR).get("/reporting/editor")
        self.assertNotIn(draft_id, body)


class WhoMayEdit(WebTest):

    def test_a_viewer_may_read_but_not_create(self):
        viewer = self.signin(VIEWER)
        self.assertEqual(viewer.get("/reporting/editor")[0], 200)
        status, _, _ = viewer.post("/reporting/editor/new", {
            "csrf": viewer.csrf("/reporting/editor"), "template": "monthly"})
        self.assertEqual(status, 403)

    def test_an_operator_may_create(self):
        operator = self.signin(OPERATOR)
        status, _, _ = operator.post("/reporting/editor/new", {
            "csrf": operator.csrf("/reporting/editor"),
            "template": "monthly"})
        self.assertIn(status, (200, 303))


class TheMonthlyTemplate(unittest.TestCase):

    def meta(self, **extra):
        base = {"workspace_name": "Productive", "workspace_slug": "productive",
                "template": cr.MONTHLY, "period": "2026-07"}
        base.update(extra)
        return base

    def rich(self):
        return {
            "domains_uploaded": 400, "domains_qualified": 260,
            "contacts_found": 812, "contacts_selected": 700,
            "contacts_verified": 640, "emails_pushed": 590,
            "replies": 61, "positive_replies": 23, "meetings": None,
            "companies_paused": 44,
            "contacts_multichannel": 300, "contacts_email_only": 200,
            "contacts_linkedin_only": 140, "contacts_mx_blocked": 32,
            "reply_breakdown": {"positive": 23, "neutral": 24,
                                "negative": 14},
            "by_persona": {"COO": 300, "CFO": 220, "Founder": 180},
            "by_country": {"United Kingdom": 400, "Germany": 240},
            "by_region": {"UK & Ireland": 400, "DACH": 240},
            "linkedin": {"requests": 300, "accepted": 141, "messages": 120,
                         "replies": 18},
            "pipeline": [{"contact": "Marta Kowalski", "company": "Harbour",
                          "title": "COO", "channel": "email",
                          "sender": "Anna Novak", "status": "Hot"}],
            "accounts": {"targeted": 260, "contacted": 240, "engaged": 51,
                         "positive": 21, "multi_dm": 96, "referrals": 7},
            "by_sender": [{"sender": "Anna Novak", "channel": "email",
                           "touches": 300, "replies": 34, "positive": 12}],
            "months": [{"month": "2026-05", "contacted": 400, "touches": 500,
                        "replies": 40, "positive": 12},
                       {"month": "2026-06", "contacted": 500, "touches": 600,
                        "replies": 52, "positive": 18}],
            "campaign_rows": [{"name": "UK services", "status": "approved",
                               "companies": 160, "contacts": 400,
                               "sent": 380, "replies": 40, "positive": 15}],
        }

    def test_it_renders_every_section(self):
        raw = cr.build(self.rich(), self.meta())
        drawn = text_of(raw)
        for heading in ("Executive Summary", "Outbound Funnel",
                        "Email Performance", "LinkedIn Performance",
                        "Multichannel Performance", "Campaign Performance",
                        "Reply Analysis", "Pipeline", "Account Engagement",
                        "Geography", "Sender Performance",
                        "Month over Month", "Meetings"):
            self.assertIn(heading, drawn, heading)

    def test_linkedin_acceptance_is_never_inferred(self):
        data = dict(self.rich())
        data.pop("linkedin")
        drawn = text_of(cr.build(data, self.meta()))
        self.assertIn("never inferred", drawn)

    def test_a_single_month_says_so_rather_than_charting_one_bar(self):
        data = dict(self.rich(), months=[{"month": "2026-06", "replies": 1}])
        self.assertIn("at least two periods",
                      text_of(cr.build(data, self.meta())))

    def test_sender_performance_refuses_to_rank(self):
        self.assertIn("No ranking", text_of(cr.build(self.rich(),
                                                     self.meta())))

    def test_it_is_a_substantial_document(self):
        raw = cr.build(self.rich(), self.meta())
        self.assertGreaterEqual(raw.count(b"/Type /Page "), 15)

    def test_an_empty_workspace_still_produces_one(self):
        raw = cr.build({}, self.meta())
        self.assertTrue(raw.startswith(b"%PDF"))

    def test_the_narrative_replaces_the_generated_summary(self):
        meta = self.meta(narrative={"summary": "Written by a human being."})
        drawn = text_of(cr.build(self.rich(), meta))
        self.assertIn("Written by a human being.", drawn)
        self.assertIn("Companies", drawn, "the counted figures went missing")

    def test_recommendations_render_under_their_categories(self):
        meta = self.meta(recommendations=[
            {"kind": "scale", "text": "Double the UK segment"},
            {"kind": "stop", "text": "Pause the DACH test"}])
        drawn = text_of(cr.build(self.rich(), meta))
        self.assertIn("Scale", drawn)
        self.assertIn("Double the UK segment", drawn)
        self.assertIn("Stop", drawn)


if __name__ == "__main__":
    unittest.main()
