"""Client reports: the document a workspace's results leave the building in.

Three properties, and they are why this file exists rather than a couple of
assertions bolted onto the reporting tests:

**A report cannot disagree with a screen.** Every figure comes from
`src/report.py`, the same functions the dashboards read. A report that
recomputed a funnel would be a second definition of the funnel, and the second
one goes stale.

**A template is a permission, not a dropdown.** The internal operations report
names providers, verification counts and held records. A client-facing role
cannot select it, cannot forge it in a form field, and cannot reach one
section of it by naming the section instead of the template.

**Nothing unknowable is printed as a number.** Meetings are not tracked; the
report says so in words rather than showing zero.
"""
import io
import re
import unittest
import zlib

from src import clientreport as cr
from src import pdf, reports as report_store
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
OTHER = "ops@contactout.test"


def text_of(raw):
    """Every string drawn into the PDF, so a test can assert what it says."""
    found = []
    for stream in re.findall(rb"stream\n(.*?)\nendstream", raw, re.S):
        try:
            body = zlib.decompress(stream).decode("latin-1")
        except zlib.error:
            continue
        found += re.findall(r"\((.*?)\) Tj", body)
    # PDF string literals escape backslash and both parentheses.
    # Reading them back without unescaping means a test looking for
    # "Acme (Holdings)" never matches the document that contains it.
    return "\n".join(_unescape(f) for f in found)


def _unescape(text):
    out, i = [], 0
    while i < len(text):
        if text[i] == chr(92) and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def pages_of(raw):
    return raw.count(b"/Type /Page ")


class ThePdfItself(unittest.TestCase):
    """The writer, before any of the reporting on top of it."""

    def doc(self, lines=1):
        document = pdf.Document(title="T")
        page = document.page()
        for index in range(lines):
            page.text(56, 700 - index * 12, f"line {index}")
        return document.render()

    def test_it_is_a_pdf(self):
        raw = self.doc()
        self.assertTrue(raw.startswith(b"%PDF-1.4"))
        self.assertTrue(raw.rstrip().endswith(b"%%EOF"))

    def test_every_xref_offset_resolves_to_its_object(self):
        """A wrong offset is a file that opens in nothing."""
        raw = self.doc(5)
        at = int(re.search(rb"startxref\s+(\d+)", raw).group(1))
        tail = raw[at:].split(b"\n")
        count = int(tail[1].split()[1])
        for number, line in enumerate(tail[3:count + 2], start=1):
            offset = int(line.split()[0])
            self.assertTrue(raw[offset:].startswith(b"%d 0 obj" % number),
                            f"object {number} is not at its stated offset")

    def test_the_same_input_produces_the_same_bytes(self):
        """No timestamp in the trailer, so two reports can be compared."""
        self.assertEqual(self.doc(3), self.doc(3))

    def test_a_document_with_no_pages_is_refused(self):
        with self.assertRaises(pdf.PdfError):
            pdf.Document().render()

    def test_parentheses_in_text_do_not_corrupt_the_page(self):
        """An unbalanced paren in a company name ends the string early."""
        document = pdf.Document()
        document.page().text(56, 700, "Acme (Holdings) Ltd :-) \\ backslash")
        raw = document.render()
        self.assertIn("Acme (Holdings) Ltd", text_of(raw))

    def test_a_name_outside_winansi_still_renders(self):
        """A report that will not generate is worse than one that transliterates."""
        document = pdf.Document()
        document.page().text(56, 700, "Łukasz Żuk 北京 – café")
        raw = document.render()
        drawn = text_of(raw)
        self.assertIn("Lukasz Zuk", drawn)
        self.assertIn("caf", drawn)

    def test_width_grows_with_the_string(self):
        self.assertGreater(pdf.width_of("mmmmm"), pdf.width_of("iii"))

    def test_wrapping_respects_the_width(self):
        for line in pdf.wrap("a b c d e f g h i j k l m n o p", 60):
            self.assertLessEqual(pdf.width_of(line), 60 + 1)

    def test_one_unbreakable_word_is_broken_rather_than_overflowing(self):
        lines = pdf.wrap("averyveryverylongdomainname.example.com", 50)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(pdf.width_of(line), 50 + 1)

    def test_truncation_ends_in_an_ellipsis(self):
        out = pdf.truncate("a very long company name indeed", 60)
        self.assertTrue(out.endswith("..."))
        self.assertLessEqual(pdf.width_of(out), 60 + 1)


class TheTemplateIsAPermission(WebTest):

    def test_an_operator_is_offered_the_internal_report(self):
        _, body, _ = self.signin(OPERATOR).get("/reporting/client")
        self.assertIn("Internal Operations Report", body)

    def test_a_viewer_is_not_offered_it(self):
        _, body, _ = self.signin(VIEWER).get("/reporting/client")
        self.assertNotIn("Internal Operations Report", body)

    def test_a_viewer_forging_the_template_gets_the_executive_one(self):
        """The least privileged document, never a refusal to probe with."""
        viewer = self.signin(VIEWER)
        status, body, headers = viewer.post_bytes(
            "/reporting/client/generate",
            {"csrf": viewer.csrf("/reporting/client"),
             "template": "internal"})
        self.assertEqual(status, 200)
        drawn = text_of(body)
        self.assertIn("Executive Report", drawn)
        self.assertNotIn("Provider Usage", drawn)

    def test_a_viewer_cannot_reach_a_provider_section_by_naming_it(self):
        """The template decides what exists; the request only narrows it."""
        viewer = self.signin(VIEWER)
        _, body, _ = viewer.post_bytes(
            "/reporting/client/generate",
            {"csrf": viewer.csrf("/reporting/client"),
             "template": "executive", "sections": "providers"})
        drawn = text_of(body)
        self.assertNotIn("Provider Usage", drawn)
        self.assertNotIn("Verification", drawn)

    def test_an_unknown_template_falls_back_rather_than_erroring(self):
        operator = self.signin(OPERATOR)
        status, body, _ = operator.post_bytes(
            "/reporting/client/generate",
            {"csrf": operator.csrf("/reporting/client"),
             "template": "../../etc/passwd"})
        self.assertEqual(status, 200)
        self.assertIn("Executive Report", text_of(body))

    def test_the_internal_report_carries_the_operator_sections(self):
        operator = self.signin(OPERATOR)
        _, body, _ = operator.post_bytes(
            "/reporting/client/generate",
            {"csrf": operator.csrf("/reporting/client"),
             "template": "internal"})
        drawn = text_of(body)
        self.assertIn("Provider Usage", drawn)
        self.assertIn("Email Security and MX", drawn)


class WhatAClientReportSays(WebTest):

    def generate(self, who=OPERATOR, **fields):
        session = self.signin(who)
        payload = {"csrf": session.csrf("/reporting/client"),
                   "template": "executive"}
        payload.update(fields)
        status, body, headers = session.post_bytes(
            "/reporting/client/generate", payload)
        self.assertEqual(status, 200, body[:200])
        return body, headers

    def test_it_is_a_pdf_attachment(self):
        raw, headers = self.generate()
        self.assertTrue(raw.startswith(b"%PDF"))
        self.assertIn("attachment", headers.get("Content-Disposition", ""))
        self.assertIn(".pdf", headers.get("Content-Disposition", ""))

    def test_it_names_the_workspace_and_not_another(self):
        raw, _ = self.generate()
        drawn = text_of(raw)
        self.assertIn("Productive", drawn)
        self.assertNotIn("ContactOut", drawn)

    def test_meetings_are_named_as_untracked_never_zero(self):
        """Counting "let's chat" as a meeting is how a report lies."""
        raw, _ = self.generate()
        drawn = text_of(raw)
        self.assertIn("Not tracked", drawn)
        self.assertIn("calendar", drawn.lower())

    def test_every_rate_carries_its_fraction(self):
        raw, _ = self.generate()
        drawn = text_of(raw)
        rates = re.findall(r"\d+\.\d% \(\d[\d,]*/\d[\d,]*\)", drawn)
        self.assertTrue(rates, "no rate states its own numerator and "
                               "denominator")

    def test_contactable_is_the_screened_figure_not_the_verified_one(self):
        """The sentence claims email-security screening; it must apply it.

        `contacts_verified` counts addresses that survived double
        verification. `contacts_email_reachable` additionally requires email
        security to allow the domain. Printing the first under a sentence
        that promises the second overstates the reachable audience by every
        contact that screen removed.
        """
        from src import clientreport, report

        data = report.for_client("productive")
        self.assertLessEqual(data["contacts_email_reachable"],
                             data["contacts_verified"])
        self.assertEqual(
            data["contacts_email_reachable"],
            (data["contacts_multichannel"] or 0)
            + (data["contacts_email_only"] or 0),
            "the funnel and the multichannel split must count one audience")
        self.assertEqual(clientreport._reachable(data),
                         data["contacts_email_reachable"])

    def test_the_funnel_and_the_multichannel_page_agree(self):
        """Two sections of one document disagreeing is worse than either."""
        raw, _ = self.generate()
        drawn = text_of(raw)
        from src import report

        data = report.for_client("productive")
        reachable = data["contacts_email_reachable"]
        self.assertIn(f"{reachable:,} are contactable by email", drawn)
        # And the split it must reconcile with is on the same document.
        self.assertIn("Email and LinkedIn", drawn)

    def test_contactable_is_not_one_word_over_two_numbers(self):
        """The screen funnel and the report funnel count different things.

        The screen's stage is anybody reachable on either channel; the
        report's row is the email-reachable count, because the stage under
        it is email touches. Both are right and they must not share a bare
        label - a client reads both documents.
        """
        from src import clientreport, report, store

        self.assertNotEqual(report.FUNNEL_LABEL["contactable"],
                            "Contactable")
        self.assertIn("either channel", report.FUNNEL_LABEL["contactable"])

        raw, _ = self.generate()
        drawn = text_of(raw)
        self.assertIn("Contactable by email", drawn)
        self.assertNotIn(report.FUNNEL_LABEL["contactable"], drawn)

        # And they are genuinely different counts, not two names for one.
        recs = [r for r in store.load() if r.get("client") == "productive"]
        by_email = clientreport._reachable(report.for_client("productive"))
        either = report.funnel_for(recs)["contactable"]
        self.assertLess(by_email, either,
                        "if these were equal the two labels would be noise")

    def test_it_says_where_the_numbers_came_from(self):
        raw, _ = self.generate()
        self.assertIn("counted from recorded", text_of(raw))

    def test_the_appendix_names_what_cannot_be_measured(self):
        raw, _ = self.generate()
        self.assertIn("Cannot Measure", text_of(raw))

    def test_demo_data_is_labelled_as_demo(self):
        raw, _ = self.generate()
        self.assertIn("DEMONSTRATION DATA", text_of(raw))

    def test_it_has_a_cover_and_several_pages(self):
        raw, _ = self.generate()
        self.assertGreaterEqual(pages_of(raw), 5)

    def test_pages_are_numbered_and_the_cover_is_not(self):
        raw, _ = self.generate()
        drawn = text_of(raw)
        self.assertIn("Page 2 of", drawn)
        self.assertNotIn("Page 1 of", drawn)

    def test_no_provider_name_reaches_a_client_facing_report(self):
        """Including the appendix, which is the page nobody re-reads."""
        for template in ("executive", "detailed"):
            raw, _ = self.generate(template=template)
            drawn = text_of(raw).lower()
            for vendor in ("reoon", "contactout", "emailbison", "heyreach",
                           "apify", "aiark", "deliverable"):
                self.assertNotIn(vendor, drawn, f"{vendor} in {template}")

    def test_the_client_appendix_is_shorter_than_the_internal_one(self):
        """The entries left out are the ones that name a supplier."""
        client, _ = self.generate(template="executive")
        internal, _ = self.generate(template="internal")
        self.assertIn("Actual credits per record", text_of(internal))
        self.assertNotIn("Actual credits per record", text_of(client))

    def test_no_credential_reaches_any_report(self):
        for template in ("executive", "detailed", "internal"):
            raw, _ = self.generate(template=template)
            drawn = text_of(raw).lower()
            for secret in ("xoxb-", "api_key", "bearer ", "signing_secret",
                           "webhook_url"):
                self.assertNotIn(secret, drawn, template)

    def test_selecting_sections_changes_the_document(self):
        everything, _ = self.generate()
        trimmed, _ = self.generate(sections="summary")
        self.assertLess(pages_of(trimmed), pages_of(everything))
        self.assertIn("Executive Summary", text_of(trimmed))
        self.assertNotIn("Observations", text_of(trimmed))

    def test_every_ticked_section_renders_not_just_the_first(self):
        """A checkbox group submits one name many times.

        `parse_qs` collapses that to the first value, which would silently
        generate a different document from the one somebody ticked - the
        summary, and nothing else they asked for. One section exercises
        neither branch of `form_list`; two is what makes the collapse
        visible.
        """
        raw, _ = self.generate(sections=["summary", "funnel", "replies"])
        drawn = text_of(raw)
        self.assertIn("Executive Summary", drawn)
        self.assertIn("Funnel", drawn)
        self.assertIn("Replies", drawn)
        self.assertNotIn("Observations", drawn)

    def test_the_recorded_sections_are_the_ones_that_rendered(self):
        """History records what the client got, not what was requested.

        The row is found by diffing ids rather than taking the newest: two
        reports generated in the same second tie, and "the first of an
        arbitrary order" is not a row this test can assert about.
        """
        session = self.signin(OPERATOR)
        before = {r["id"] for r in report_store.for_workspace("productive")}
        session.post("/reporting/client/generate",
                     {"csrf": session.csrf("/reporting/client"),
                      "template": "executive",
                      "sections": ["summary", "funnel", "providers"]})
        fresh = [r for r in report_store.for_workspace("productive")
                 if r["id"] not in before]
        self.assertEqual(len(fresh), 1)
        row = fresh[0]
        self.assertEqual(row["template"], "executive")
        self.assertIn("summary", row["sections"])
        self.assertIn("funnel", row["sections"])
        self.assertNotIn("providers", row["sections"])


class TheHistory(WebTest):

    def test_a_generation_is_recorded(self):
        before = len(report_store.for_workspace("productive"))
        session = self.signin(OPERATOR)
        session.post("/reporting/client/generate",
                     {"csrf": session.csrf("/reporting/client"),
                      "template": "executive"})
        self.assertGreater(len(report_store.for_workspace("productive")),
                           before)

    def test_the_row_names_who_ran_it(self):
        session = self.signin(OPERATOR)
        session.post("/reporting/client/generate",
                     {"csrf": session.csrf("/reporting/client"),
                      "template": "executive"})
        self.assertEqual(report_store.for_workspace("productive")[0]["by"],
                         OPERATOR)

    def test_the_history_renders_on_the_screen(self):
        session = self.signin(OPERATOR)
        session.post("/reporting/client/generate",
                     {"csrf": session.csrf("/reporting/client"),
                      "template": "executive"})
        _, body, _ = session.get("/reporting/client")
        self.assertIn("Report history", body)
        self.assertIn("rep-", body)

    def test_a_generation_reaches_the_audit_log(self):
        from src import workspaces as ws

        session = self.signin(OPERATOR)
        session.post("/reporting/client/generate",
                     {"csrf": session.csrf("/reporting/client"),
                      "template": "executive"})
        self.assertTrue(any("report.generated" in str(e)
                            for e in ws.audit(limit=50)))

    def test_downloading_re_renders_and_counts_the_download(self):
        session = self.signin(OPERATOR)
        session.post("/reporting/client/generate",
                     {"csrf": session.csrf("/reporting/client"),
                      "template": "executive"})
        row = report_store.for_workspace("productive")[0]
        status, body, headers = session.get_bytes(
            "/reporting/client/download?id=" + row["id"])
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"%PDF"))
        self.assertEqual(report_store.get(row["id"])["status"],
                         report_store.DOWNLOADED)

    def test_a_download_does_not_create_a_second_history_row(self):
        session = self.signin(OPERATOR)
        session.post("/reporting/client/generate",
                     {"csrf": session.csrf("/reporting/client"),
                      "template": "executive"})
        row = report_store.for_workspace("productive")[0]
        before = len(report_store.for_workspace("productive"))
        session.get("/reporting/client/download?id=" + row["id"])
        self.assertEqual(len(report_store.for_workspace("productive")), before)


class OneWorkspaceCannotReadAnothersReport(WebTest):

    def other_workspaces_report(self):
        session = self.signin(OTHER)
        session.post("/reporting/client/generate",
                     {"csrf": session.csrf("/reporting/client"),
                      "template": "executive"})
        return report_store.for_workspace("contactout")[0]

    def test_a_forged_report_id_is_a_404_not_a_403(self):
        """A report id that exists elsewhere must look like one that does not."""
        theirs = self.other_workspaces_report()
        status, body, _ = self.signin(OPERATOR).get(
            "/reporting/client/download?id=" + theirs["id"])
        self.assertEqual(status, 404)
        self.assertNotIn("ContactOut", body)

    def test_an_invented_report_id_answers_the_same_way(self):
        status, _, _ = self.signin(OPERATOR).get(
            "/reporting/client/download?id=rep-doesnotexist")
        self.assertEqual(status, 404)

    def test_the_history_screen_shows_only_this_workspace(self):
        self.other_workspaces_report()
        _, body, _ = self.signin(OPERATOR).get("/reporting/client")
        for row in report_store.for_workspace("contactout"):
            self.assertNotIn(row["id"], body)

    def test_a_viewer_cannot_read_another_workspaces_report(self):
        theirs = self.other_workspaces_report()
        status, _, _ = self.signin(VIEWER).get(
            "/reporting/client/download?id=" + theirs["id"])
        self.assertEqual(status, 404)


class WhoMayGenerate(WebTest):

    def test_a_viewer_may_take_its_own_numbers_as_a_pdf(self):
        """The one person the report is for can have it.

        Everything in the executive report is already on the client's
        dashboard, so the PDF discloses nothing new. What a VIEWER cannot
        reach is the internal template, which `allowed_template` decides -
        the template is the boundary, not the button.
        """
        viewer = self.signin(VIEWER)
        status, body, _ = viewer.post_bytes("/reporting/client/generate", {
            "csrf": viewer.csrf("/reporting/client"),
            "template": "executive"})
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"%PDF"))

    def test_a_viewer_still_cannot_export_contact_rows(self):
        """A summary is not row data. The CSV gate is unchanged."""
        status, _, _ = self.signin(VIEWER).get("/export/contacts.csv")
        self.assertEqual(status, 403)

    def test_an_anonymous_visitor_gets_the_sign_in_page_not_a_pdf(self):
        """The whole app answers 200 with a sign-in page when there is no
        session, so the status is not the assertion that matters - what
        matters is that no document came back."""
        status, body, headers = self.anonymous().post_bytes(
            "/reporting/client/generate", {"template": "executive"})
        self.assertFalse(body.startswith(b"%PDF"))
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn(b"Sign in", body)


class SectionResolution(unittest.TestCase):
    """The guard that keeps a forged section list from widening a template."""

    def test_a_section_the_template_lacks_is_dropped(self):
        chosen = cr.resolve_sections(cr.EXECUTIVE, ["summary", "providers"])
        self.assertIn("summary", chosen)
        self.assertNotIn("providers", chosen)

    def test_no_sections_requested_means_all_of_them(self):
        self.assertEqual(cr.resolve_sections(cr.EXECUTIVE),
                         cr.sections_for(cr.EXECUTIVE))

    def test_every_executive_section_is_client_safe(self):
        for key in cr.sections_for(cr.EXECUTIVE):
            self.assertIn(key, cr.CLIENT_SAFE_SECTIONS, key)

    def test_every_detailed_section_is_client_safe(self):
        for key in cr.sections_for(cr.DETAILED):
            self.assertIn(key, cr.CLIENT_SAFE_SECTIONS, key)

    def test_the_internal_template_is_the_only_one_with_unsafe_sections(self):
        """The structural half of the guarantee.

        `allowed_template` stops a forged template. This stops a section that
        should never have been in a client template from being there at all.
        """
        unsafe = {key for key, _, _, safe in cr.SECTIONS if not safe}
        self.assertTrue(unsafe, "no section is marked operator-only, so this "
                                "test proves nothing")
        for key in unsafe:
            self.assertIn(key, cr.sections_for(cr.INTERNAL), key)
            self.assertNotIn(key, cr.sections_for(cr.EXECUTIVE), key)
            self.assertNotIn(key, cr.sections_for(cr.DETAILED), key)


class SectionNamesMatchTheirHeadings(unittest.TestCase):
    """A section ticked as "Reply Analysis" must not print "Replies".

    The section list is what somebody chooses from and the heading is what
    the client reads. Two names for one section is how a report ends up with
    a contents page that does not match its pages.
    """

    def test_every_rendered_heading_matches_its_section_label(self):
        mismatches = []
        for key in cr.sections_for(cr.MONTHLY) + cr.sections_for(cr.INTERNAL):
            label = cr.SECTION_LABEL[key]
            raw = cr.build({}, {"workspace_name": "W", "workspace_slug": "w",
                                "template": cr.INTERNAL
                                if key in ("verification", "security",
                                           "providers", "operations")
                                else cr.MONTHLY},
                           [key])
            drawn = text_of(raw)
            # The appendix's label is longer than its heading by design.
            if key == "appendix":
                continue
            if label not in drawn:
                mismatches.append(f"{key}: label {label!r} not in the page")
        self.assertEqual(sorted(set(mismatches)), [],
                         chr(10).join(sorted(set(mismatches))))


class ObservationsAreDeterministic(unittest.TestCase):
    """No model writes a strategic conclusion into a client's document."""

    def test_the_same_data_gives_the_same_observations(self):
        data = {"contacts_found": 100, "contacts_verified": 60,
                "emails_pushed": 50, "replies": 10, "positive_replies": 4}
        self.assertEqual(cr.observations(data), cr.observations(data))

    def test_a_high_held_share_is_called_out(self):
        data = {"contacts_found": 100, "contacts_verified": 50,
                "emails_pushed": 40}
        text = " ".join(t for _, t in cr.observations(data))
        self.assertIn("cannot be used", text)
        self.assertIn("50", text)

    def test_a_contact_with_no_address_is_not_held(self):
        """The count is explained as verification failure, disagreement or
        email security. A contact with no address at all is none of those,
        and was being counted anyway."""
        data = {"contacts_found": 100, "contacts_email_reachable": 50,
                "confirmation": {"contacts_with_an_address": 55},
                "emails_pushed": 40}
        text = " ".join(t for _, t in cr.observations(data))
        # Five, not fifty: forty-five of those contacts have no address.
        self.assertNotIn("50 of 100", text)
        self.assertEqual(
            [t for _, t in cr.observations(data) if "cannot be used" in t],
            [], "5 of 100 is under the threshold and should say nothing")

    def test_a_small_sample_is_called_out(self):
        data = {"contacts_found": 20, "contacts_verified": 20,
                "emails_pushed": 5, "replies": 1}
        text = " ".join(t for _, t in cr.observations(data))
        self.assertIn("readable sample", text)

    def test_no_outreach_is_stated_rather_than_shown_as_a_zero_rate(self):
        text = " ".join(t for _, t in cr.observations({"emails_pushed": 0}))
        self.assertIn("no reply rate can be reported", text)

    def test_there_is_always_at_least_one_observation(self):
        self.assertTrue(cr.observations({}))


class ReportsWithAwkwardData(unittest.TestCase):
    """The shapes that break a layout: nothing, and far too much."""

    def meta(self, **extra):
        base = {"workspace_name": "Productive", "workspace_slug": "productive",
                "template": cr.EXECUTIVE, "period": "All time"}
        base.update(extra)
        return base

    def test_an_empty_workspace_still_produces_a_report(self):
        raw = cr.build({}, self.meta())
        self.assertTrue(raw.startswith(b"%PDF"))
        self.assertGreaterEqual(pages_of(raw), 2)

    def test_a_workspace_with_no_replies_says_so(self):
        raw = cr.build({"contacts_found": 10, "replies": 0,
                        "emails_pushed": 0}, self.meta())
        self.assertIn("no reply rate can be reported", text_of(raw))

    def test_a_very_long_company_name_does_not_overflow(self):
        rows = [{"name": "A" * 400, "status": "approved", "companies": 1,
                 "contacts": 1, "sent": 1, "replies": 0, "positive": 0}]
        raw = cr.build({"campaign_rows": rows}, self.meta())
        self.assertIn("...", text_of(raw))

    def test_many_campaigns_break_across_pages_with_a_repeated_header(self):
        rows = [{"name": f"Campaign {i}", "status": "approved",
                 "companies": i, "contacts": i, "sent": i, "replies": 0,
                 "positive": 0} for i in range(120)]
        raw = cr.build({"campaign_rows": rows}, self.meta())
        drawn = text_of(raw)
        self.assertGreater(drawn.count("Campaign"), 100)
        self.assertGreater(pages_of(raw), 4)

    def test_unicode_survives_into_the_document(self):
        rows = [{"name": "Ćwikła & Söhne – Ünïcodé", "status": "approved",
                 "companies": 1, "contacts": 1, "sent": 0, "replies": 0,
                 "positive": 0}]
        raw = cr.build({"campaign_rows": rows}, self.meta())
        self.assertIn("Sohne", text_of(raw).replace("ö", "o"))

    def test_the_detailed_template_renders(self):
        raw = cr.build({"contacts_found": 10}, self.meta(template=cr.DETAILED))
        self.assertIn("Audience Breakdown", text_of(raw))

    def test_the_internal_template_renders(self):
        raw = cr.build({"contacts_found": 10}, self.meta(template=cr.INTERNAL))
        self.assertIn("Provider Usage", text_of(raw))

    def test_an_unknown_template_is_refused_at_the_builder(self):
        with self.assertRaises(ValueError):
            cr.build({}, self.meta(template="nonsense"))


if __name__ == "__main__":
    unittest.main()
