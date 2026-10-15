"""Criterion 7 in its PER-CAMPAIGN form, and the fence that admitted a
second endpoint.

TASK 0200 (pilotcaps), 2026-10-16. Two things are proven here and they are
separate claims.

ONE. CRITERION 7 IS PER CAMPAIGN AND THE PER-CAMPAIGN CHECK NOW EXISTS.
TASK 0190 repaired the ESTATE-wide instrument - all 181 mailboxes, one
owner. Criterion 7 says "one owner across the ATTACHED pool", which is a
subset, and the 0160 audit recorded that the per-campaign form did not
exist anywhere. `scripts/canary_pool_readback.py` is that form. It is driven
from here, not re-implemented here, and it is fail-closed by construction:
UNKNOWN dominates NOT MET, an empty scope is UNKNOWN, an unread membership
is UNKNOWN, and MET requires every rung evaluated and clean.

TWO. THE 0180 FENCE MATCHED THE PATH'S LAST SEGMENT, AND THE SECOND
ENDPOINT SHARES IT. Measured at the transport seam, offline:

    bison.sender_emails()        GET /api/sender-emails             leaf sender-emails
    bison.campaign_senders(499)  GET /api/campaigns/499/sender-emails  leaf sender-emails

0180 enforced "GET, and the leaf must be `sender-emails`, and no body". So
its fence returns ALLOWED for `/api/campaigns/{id}/sender-emails` - an
endpoint the 2026-10-15 23:00 authorisation did not cover. Nothing was in
fact sent there: 0180's self-check records 13 requests, `distinct_paths ==
['/api/sender-emails']`, nothing refused during the read. What failed is the
PROOF. The negative control meant to cover this - `GET
/api/campaigns/499/senders` - names a path NO adapter in this repository
generates, so it refused on a leaf that could never have arrived.

A straw negative control is this project's signature defect in a new place:
a guard that cannot fire, reported as a guard that held.

THE REACHABILITY PIN, carried forward from 0190's own lesson.
`unittest.skipUnless` replaces a method with a wrapper that raises
`SkipTest` WHEN CALLED, so a control that invokes a gated method directly
reports `skipped` and the run says OK. 0190 lost seven cases that way and
caught it. `TheGatedLegStaysReachable` below pins both halves - the live leg
stays gated, AND its body is still reachable through `inspect.unwrap` - so
if either changes this module fails loudly instead of going quiet.

HYGIENE. Sender mailboxes are provider ids, owners are px values, names in
the synthetic rows are abstract. No address, surname or signature string
appears in this file. The recorded 181-row walk lives in `resonate-ops`,
outside git, because it carries 181 real addresses.
"""
import importlib.util
import inspect
import os
import sys
import unittest

from src import providers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READBACK = os.path.join(ROOT, "scripts", "canary_pool_readback.py")

# The gated class is reached through the MODULE OBJECT, never bound here by
# name. MEASURED while writing this module: a `TestCase` subclass bound into
# a second module's namespace is DISCOVERED AND RUN AGAIN from that module,
# minting a duplicate test name and a second skip in this module's own tally
# - a name the merge gate would see appear out of nowhere. Only non-TestCase
# values are bound below.
from tests import (  # noqa: E402
    test_every_body_is_signed_by_the_pools_owner as instrument,
)

PROVIDER_SIGNATURE_FIELD = instrument.PROVIDER_SIGNATURE_FIELD
px_of = instrument.px_of


def _readback():
    """Load the script under test by path, as this repository's other
    script-backed tests do (`test_no_new_write_bypasses_the_door`)."""
    spec = importlib.util.spec_from_file_location(
        "canary_pool_readback_under_test", READBACK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rb = _readback()

#: The measured shape of every one of the 181 captured signatures.
SHAPE = "<p>%s<br>Productive</p>"

#: An abstract owner name. The real one is never written here; what matters
#: is that `px_of` of it is a stable px and that the pool agrees on it.
OWNER = "Grace Hopper"
OTHER = "Ada Lovelace"


def row(id_, name=OWNER, field=PROVIDER_SIGNATURE_FIELD):
    """One `/sender-emails`-shaped row. `email` is a reserved-domain
    fiction; the real addresses are outside git."""
    return {"id": id_, "name": name, "email": f"m{id_}@example.invalid",
            field: SHAPE % name}


def estate(ids, name=OWNER):
    return [row(i, name) for i in ids]


POOL = list(rb.APPROVED_POOL)
PX = px_of(OWNER)


class TheRouteIsMeasuredNotAssumed(unittest.TestCase):
    """What the adapter actually asks for, taken at the transport seam.

    NO NETWORK, three ways. The transport is a raiser installed before the
    first call; `urllib.request.urlopen` is replaced by a tripwire so
    anything bypassing the seam dies loudly; and the key is the suite's own
    placeholder, never a real credential and never printed.

    THE PLACEHOLDER IS NOT A CONVENIENCE. `tests/__init__`'s firewall points
    `providers.ENV_FILE` at a path that cannot exist and pops every key, so
    `campaign_senders` raises `MissingKey` BEFORE it builds a URL - which
    0190 recorded and this class first reproduced: all three route tests
    failed on their own `assertTrue(self.seen)` rather than passing while
    measuring nothing. A placeholder key lets URL construction finish; the
    raiser is what guarantees nothing is sent. Exactly `ProviderTest`'s
    arrangement, inlined because this module is a plain `TestCase`.
    """

    def setUp(self):
        import urllib.request
        self.seen = []

        def raiser(method, url, headers=None, body=None, timeout=None):
            self.seen.append((method, url, body))
            raise self.Sealed("TASK 0200: nothing is sent")

        providers.set_transport(raiser)
        self.addCleanup(providers.reset_transport)

        previous = {k: os.environ.get(k) for k in ("BISON_KEY",)}
        self.addCleanup(self._restore, previous)
        os.environ["BISON_KEY"] = "test-key-not-real"

        real_urlopen = urllib.request.urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", real_urlopen)

        def forbidden(*a, **k):
            raise AssertionError("a request bypassed the transport seam")

        urllib.request.urlopen = forbidden

    class Sealed(Exception):
        """Raised by this class's transport. Narrow on purpose: catching
        bare `Exception` here would swallow a `MissingKey` and leave the
        measurement empty, which is how the first version of this class
        reported nothing."""

    @staticmethod
    def _restore(previous):
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def ask(self, fn, *a):
        with self.assertRaises(self.Sealed):
            fn(*a)
        self.assertTrue(self.seen, "the adapter never reached the transport, "
                                   "so this measures nothing")
        return self.seen[-1]

    def test_campaign_senders_hits_the_per_campaign_sender_emails_route(self):
        from src.providers import bison
        _, url, _ = self.ask(bison.campaign_senders, 499)
        self.assertIn(
            rb.ROUTE_CAMPAIGN_SENDERS.format(campaign_id=499), url,
            "the per-campaign sender route moved; every verdict in this "
            "module and in the 0200 report is measured against it")

    def test_the_estate_walk_hits_the_one_authorised_route(self):
        from src.providers import bison
        _, url, _ = self.ask(bison.sender_emails)
        self.assertIn(rb.ROUTE_ESTATE, url)

    def test_neither_sender_read_carries_a_body(self):
        """0180's fence also refused `bool(body)`. Worth pinning, because
        if a GET ever grew a body the path-exact fence would refuse the
        authorised route and the refusal would look like a bug."""
        from src.providers import bison
        for fn, args in ((bison.sender_emails, ()),
                         (bison.campaign_senders, (499,))):
            self.seen = []
            _, _, body = self.ask(fn, *args)
            self.assertFalse(body)

    def test_the_two_routes_share_their_last_segment(self):
        """The whole reason the leaf fence was not narrow."""
        def leaf(path):
            return path.rstrip("/").rsplit("/", 1)[-1]
        self.assertEqual(
            leaf(rb.ROUTE_ESTATE),
            leaf(rb.ROUTE_CAMPAIGN_SENDERS.format(campaign_id=499)))

    def test_no_adapter_route_ends_in_the_path_the_control_used(self):
        """`/campaigns/{id}/senders` is generated by nothing here, which is
        why refusing it proved nothing. Measured against both sender reads
        rather than argued from the name."""
        from src.providers import bison
        straw = rb.ROUTE_NOBODY_GENERATES.format(campaign_id=499)
        for fn, args in ((bison.campaign_senders, (499,)),
                         (bison.sender_emails, ())):
            with self.subTest(fn=fn.__name__):
                self.seen = []
                _, url, _ = self.ask(fn, *args)
                self.assertNotIn(straw, url)


class TheLeafFenceAdmittedASecondEndpoint(unittest.TestCase):
    """The defect, and the repair, as two verdicts on the same request."""

    CAMPAIGN_ROUTE = rb.ROUTE_CAMPAIGN_SENDERS.format(campaign_id=499)
    BASE = "https://send.resonategroup.co"

    def test_the_leaf_fence_allows_the_per_campaign_route(self):
        self.assertEqual(
            rb.fence_0180_leaf_verdict(
                "GET", self.BASE + self.CAMPAIGN_ROUTE + "?page=1", None),
            "ALLOWED",
            "if this ever refuses, 0180's fence was narrow after all and "
            "the finding in this module's docstring must be re-measured")

    def test_the_leaf_fence_still_refuses_what_it_was_built_to_refuse(self):
        """Negative control FOR the control: the ALLOWED above is a property
        of the shared leaf, not of a predicate that allows everything."""
        for method, url in (("POST", self.BASE + rb.ROUTE_ESTATE),
                            ("GET", self.BASE + "/api/campaigns"),
                            ("GET", self.BASE + "/api/campaigns/499")):
            with self.subTest(method=method, url=url):
                self.assertEqual(
                    rb.fence_0180_leaf_verdict(method, url, None),
                    "REFUSED_BY_FENCE")

    def test_the_leaf_fence_refuses_the_straw_control_for_the_wrong_reason(self):
        """It refuses on leaf `senders` - a leaf no request could carry."""
        straw = self.BASE + rb.ROUTE_NOBODY_GENERATES.format(campaign_id=499)
        self.assertEqual(rb.fence_0180_leaf_verdict("GET", straw, None),
                         "REFUSED_BY_FENCE")

    def test_the_path_exact_fence_refuses_the_per_campaign_route(self):
        """THE REPAIR. Same request, compared whole instead of by leaf."""
        transport, observed = rb.path_exact_fence([rb.ROUTE_ESTATE])
        with self.assertRaises(rb.OutsideAuthorisation) as caught:
            transport("GET", self.BASE + self.CAMPAIGN_ROUTE + "?page=1")
        self.assertIn(self.CAMPAIGN_ROUTE, str(caught.exception))
        self.assertIn("Nothing was sent", str(caught.exception))
        self.assertEqual([r["verdict"] for r in observed],
                         ["REFUSED_BY_FENCE"])

    def test_the_path_exact_fence_sends_nothing_even_when_it_allows(self):
        """An allowed path still reaches no network from here: this module
        has no live mode, so the fence is for proving narrowness only."""
        transport, observed = rb.path_exact_fence([rb.ROUTE_ESTATE])
        with self.assertRaises(rb.OutsideAuthorisation) as caught:
            transport("GET", self.BASE + rb.ROUTE_ESTATE + "?page=1")
        self.assertIn("sends nothing", str(caught.exception))
        self.assertEqual([r["verdict"] for r in observed],
                         ["ALLOWED_BY_FENCE_BUT_NOT_SENT"])

    def test_the_fence_refuses_a_body_and_a_wrong_method(self):
        transport, observed = rb.path_exact_fence([rb.ROUTE_ESTATE])
        for method, body in (("POST", None), ("GET", b"x"), ("PATCH", None)):
            with self.subTest(method=method, body=body):
                with self.assertRaises(rb.OutsideAuthorisation):
                    transport(method, self.BASE + rb.ROUTE_ESTATE, None, body)
        self.assertEqual({r["verdict"] for r in observed},
                         {"REFUSED_BY_FENCE"})

    def test_the_fence_never_records_a_header(self):
        """`headers` is the only argument that could carry a credential."""
        transport, observed = rb.path_exact_fence([rb.ROUTE_ESTATE])
        with self.assertRaises(rb.OutsideAuthorisation):
            transport("GET", self.BASE + "/api/campaigns",
                      {"Authorization": "Bearer sentinel-0200"})
        blob = repr(observed)
        self.assertNotIn("sentinel-0200", blob)
        self.assertNotIn("Authorization", blob)

    def test_the_corrected_controls_include_the_route_that_exists(self):
        """The control set a live read-back must refuse. All of them must
        refuse under the path-exact fence, and the per-campaign route must
        be among them - that is the correction."""
        self.assertIn(("GET", self.CAMPAIGN_ROUTE), rb.NEGATIVE_CONTROLS)
        transport, observed = rb.path_exact_fence([rb.ROUTE_ESTATE])
        for method, path in rb.NEGATIVE_CONTROLS:
            with self.subTest(method=method, path=path):
                with self.assertRaises(rb.OutsideAuthorisation):
                    transport(method, self.BASE + path)
        self.assertEqual(len(observed), len(rb.NEGATIVE_CONTROLS))
        self.assertEqual({r["verdict"] for r in observed},
                         {"REFUSED_BY_FENCE"})


class TheResolutionStepIsOffline(unittest.TestCase):
    """id -> address is a join onto the recorded walk, not a provider call."""

    def test_every_approved_id_resolves(self):
        resolved, unresolved, dup = rb.resolve(POOL, estate(POOL))
        self.assertEqual(len(resolved), 10)
        self.assertEqual(unresolved, [])
        self.assertEqual(dup, [])
        self.assertEqual([r["id"] for r in resolved], POOL,
                         "resolution must preserve the order it was asked in")

    def test_an_id_outside_the_walk_is_named_not_dropped(self):
        """2738 carried the pool's attestation and has LEFT the estate. An
        id that resolves to nothing must be reported, because dropping it
        silently shrinks the pool and a smaller pool agrees more easily."""
        resolved, unresolved, _ = rb.resolve([2763, 2738], estate([2763]))
        self.assertEqual(len(resolved), 1)
        self.assertEqual(unresolved, [2738])

    def test_a_repeated_id_is_reported(self):
        _, _, dup = rb.resolve([2763, 2763, 2760], estate([2763, 2760]))
        self.assertEqual(dup, [2763])

    def test_resolution_makes_no_provider_call(self):
        """The transport is a raiser for the duration; resolution must not
        touch it."""
        def raiser(*a, **k):
            raise AssertionError("resolve() reached the transport")
        providers.set_transport(raiser)
        self.addCleanup(providers.reset_transport)
        self.assertEqual(len(rb.resolve(POOL, estate(POOL))[0]), 10)


class ThePerCampaignVerdict(unittest.TestCase):
    """The check itself. Every rung, and the precedence between them."""

    def verdict(self, membership, rows=None, **kw):
        return rb.verdict_for_campaign(
            499, membership, rows if rows is not None else estate(POOL),
            approved_ids=POOL, expected_px=PX, **kw)

    def reasons(self, result):
        return " | ".join(f["reason"] for f in result["findings"])

    # --- the one way to be MET -------------------------------------------

    def test_exactly_the_approved_ten_under_one_owner_is_MET(self):
        result = self.verdict(POOL, estate_total=10)
        self.assertEqual(result["verdict"], rb.MET, self.reasons(result))
        self.assertEqual(result["owner_px"], PX)
        self.assertEqual(result["findings"], [])

    def test_MET_does_not_depend_on_the_order_of_the_read_back(self):
        self.assertEqual(self.verdict(list(reversed(POOL)))["verdict"], rb.MET)

    # --- UNKNOWN, and it never becomes MET -------------------------------

    def test_an_unread_membership_is_UNKNOWN(self):
        """THE ANSWER TODAY. Nothing is attached and `campaign_senders` is
        outside the spent authorisation, so there is no read-back."""
        result = self.verdict(None)
        self.assertEqual(result["verdict"], rb.UNKNOWN)
        self.assertIsNone(result["attached"])
        self.assertIn("no read-back", self.reasons(result))
        self.assertIn("unread pool is not an empty one", self.reasons(result))

    def test_an_empty_membership_is_UNKNOWN_not_MET(self):
        result = self.verdict([])
        self.assertEqual(result["verdict"], rb.UNKNOWN)
        self.assertIn("no senders attached", self.reasons(result))

    def test_an_unresolvable_attached_id_is_UNKNOWN(self):
        """The brief's own requirement: a campaign whose senders cannot be
        resolved is UNKNOWN, never MET."""
        result = self.verdict(POOL + [2738])
        self.assertEqual(result["verdict"], rb.UNKNOWN)
        self.assertIn("2738", self.reasons(result))

    def test_a_partial_estate_walk_is_UNKNOWN_even_when_every_row_agrees(self):
        """Completeness is not implied by agreement. 10 of 181 rows all
        attesting one owner says nothing about resolving the other 171."""
        result = self.verdict(POOL, estate_total=181)
        self.assertEqual(result["verdict"], rb.UNKNOWN)
        self.assertIn("partial", self.reasons(result))

    def test_an_unreadable_signature_is_UNKNOWN(self):
        rows = estate(POOL[1:])
        rows.append({"id": POOL[0], PROVIDER_SIGNATURE_FIELD:
                     f"{OWNER}<br>Productive"})          # no <p> wrapper
        result = self.verdict(POOL, rows=rows)
        self.assertEqual(result["verdict"], rb.UNKNOWN)
        self.assertIn("cannot read", self.reasons(result))

    def test_a_row_without_the_signature_field_is_UNKNOWN(self):
        """An absent authority is UNKNOWN. The old instrument's exact
        defect: it read a field the provider does not have and called every
        row ownerless."""
        rows = estate(POOL[1:])
        rows.append({"id": POOL[0], "signature": SHAPE % OWNER})
        result = self.verdict(POOL, rows=rows)
        self.assertEqual(result["verdict"], rb.UNKNOWN)
        self.assertIn(PROVIDER_SIGNATURE_FIELD, self.reasons(result))

    def test_a_duplicated_id_is_UNKNOWN(self):
        result = self.verdict(POOL + [POOL[0]])
        self.assertEqual(result["verdict"], rb.UNKNOWN)
        self.assertIn("more than once", self.reasons(result))

    # --- NOT MET ----------------------------------------------------------

    def test_a_second_owner_in_the_pool_is_NOT_MET_and_names_both(self):
        rows = estate(POOL[:-1]) + [row(POOL[-1], OTHER)]
        result = self.verdict(POOL, rows=rows)
        self.assertEqual(result["verdict"], rb.NOT_MET)
        self.assertIn("distinct owners", self.reasons(result))
        self.assertIn(str(POOL[-1]), self.reasons(result))

    def test_one_owner_who_is_the_wrong_owner_is_NOT_MET(self):
        """A homogeneous pool is not a correct pool. This is the 09-13
        precedent: the engine signed one name and the mailboxes were
        someone else's."""
        result = self.verdict(POOL, rows=estate(POOL, OTHER))
        self.assertEqual(result["verdict"], rb.NOT_MET)
        self.assertIn("every approved body signs", self.reasons(result))
        self.assertEqual(result["owner_px"], px_of(OTHER))

    def test_an_ownerless_mailbox_is_NOT_MET_and_not_UNKNOWN(self):
        """A signature block with NO text attests no owner - a measured
        fact about the mailbox, not an unreadable authority. The two are
        kept apart deliberately: collapsing them is what made 181 blind
        rows look like a clean estate."""
        rows = estate(POOL[1:]) + [{"id": POOL[0],
                                    PROVIDER_SIGNATURE_FIELD: "<p></p>"}]
        result = self.verdict(POOL, rows=rows)
        self.assertEqual(result["verdict"], rb.NOT_MET)
        self.assertIn("no attested owner", self.reasons(result))

    def test_an_eleventh_unapproved_sender_is_NOT_MET(self):
        """The failure criterion 7 exists to catch, and it is catchable
        even when the extra mailbox has the SAME owner - so the test uses
        one that does."""
        extra = 2757                                 # a reserve, same owner
        self.assertIn(extra, rb.RESERVES_NOT_IN_POOL)
        result = self.verdict(POOL + [extra], rows=estate(POOL + [extra]))
        self.assertEqual(result["verdict"], rb.NOT_MET)
        self.assertIn("were not approved", self.reasons(result))
        self.assertIn(str(extra), self.reasons(result))

    def test_a_short_attach_is_NOT_MET(self):
        result = self.verdict(POOL[:-2], rows=estate(POOL))
        self.assertEqual(result["verdict"], rb.NOT_MET)
        self.assertIn("did not land in full", self.reasons(result))

    # --- precedence -------------------------------------------------------

    def test_UNKNOWN_dominates_NOT_MET(self):
        """Both wrong AND unreadable must report UNKNOWN: a verdict built
        on a partial reading is not a verdict, even a negative one."""
        rows = estate(POOL[1:], OTHER)
        result = self.verdict(POOL + [2738], rows=rows)
        verdicts = {f["verdict"] for f in result["findings"]}
        self.assertIn(rb.NOT_MET, verdicts)
        self.assertIn(rb.UNKNOWN, verdicts)
        self.assertEqual(result["verdict"], rb.UNKNOWN)

    def test_worst_of_nothing_is_UNKNOWN(self):
        self.assertEqual(rb.worst([]), rb.UNKNOWN)
        self.assertEqual(rb.worst([rb.MET]), rb.MET)
        self.assertEqual(rb.worst([rb.MET, rb.NOT_MET]), rb.NOT_MET)
        self.assertEqual(rb.worst([rb.NOT_MET, rb.UNKNOWN]), rb.UNKNOWN)

    def test_every_finding_is_reported_not_only_the_first(self):
        result = self.verdict(POOL[:-1] + [2738, 2757],
                              rows=estate(POOL + [2757]))
        self.assertGreater(len(result["findings"]), 1,
                           "a human must read the whole state of the "
                           "campaign, not the earliest rung")


class TheScopeIsNeverVacuous(unittest.TestCase):
    """An instrument that examines nothing must not report ok. This is the
    0190 defect generalised one level up, and it is the live question: there
    is no canary campaign, so the scope is empty today."""

    def test_an_empty_scope_is_UNKNOWN(self):
        report = rb.verdict_over_campaigns({}, estate(POOL))
        self.assertEqual(report["overall"]["verdict"], rb.UNKNOWN)
        self.assertIn("proves nothing", report["overall"]["reason"])
        self.assertEqual(report["per_campaign"], {})

    def test_one_UNKNOWN_campaign_makes_the_whole_report_UNKNOWN(self):
        report = rb.verdict_over_campaigns(
            {1: POOL, 2: None}, estate(POOL),
            approved_ids=POOL, expected_px=PX)
        self.assertEqual(report["per_campaign"][1]["verdict"], rb.MET)
        self.assertEqual(report["per_campaign"][2]["verdict"], rb.UNKNOWN)
        self.assertEqual(report["overall"]["verdict"], rb.UNKNOWN)

    def test_every_campaign_MET_is_MET(self):
        report = rb.verdict_over_campaigns(
            {1: POOL, 2: POOL}, estate(POOL),
            approved_ids=POOL, expected_px=PX)
        self.assertEqual(report["overall"]["verdict"], rb.MET)

    def test_the_report_is_json_serialisable(self):
        """The artifact has to survive the process that produced it. 0180
        lost a whole authorised walk to a post-processing error."""
        import json
        report = rb.verdict_over_campaigns({499: None}, estate(POOL))
        self.assertEqual(json.loads(json.dumps(report))["overall"]["verdict"],
                         rb.UNKNOWN)


class TheCheckNeverDials(unittest.TestCase):
    """The whole per-campaign path with the transport armed as a tripwire."""

    def test_the_whole_report_runs_with_the_transport_a_raiser(self):
        calls = []

        def raiser(*a, **k):
            calls.append(a[:2])
            raise AssertionError("the criterion-7 check reached the transport")

        providers.set_transport(raiser)
        self.addCleanup(providers.reset_transport)
        report = rb.verdict_over_campaigns(
            {499: POOL, 500: None, 501: []}, estate(POOL),
            estate_total=10, approved_ids=POOL, expected_px=PX)
        self.assertEqual(calls, [])
        self.assertEqual(report["per_campaign"][499]["verdict"], rb.MET)
        self.assertEqual(report["overall"]["verdict"], rb.UNKNOWN)

    def test_the_module_has_no_live_mode(self):
        """`main()` takes no flag that would make it read. Asserted on the
        parser's own options rather than on the source text, because a
        test that greps for a word fails when somebody writes a comment."""
        import argparse
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf), \
                self.assertRaises(SystemExit):
            rb.main(["--estate", os.devnull, "--live"])
        self.assertIn("unrecognized arguments", buf.getvalue())
        del argparse

    def test_importing_the_script_leaves_the_credential_firewall_up(self):
        """The script imports the instrument, which imports `tests`, which
        points `providers.ENV_FILE` at a path that cannot exist. So a live
        call from this process fails loudly rather than succeeding."""
        self.assertFalse(os.path.exists(providers.ENV_FILE))


class TheGatedLegStaysReachable(unittest.TestCase):
    """0190's lesson, pinned at this module's level too.

    `unittest.skipUnless` replaces the method with a wrapper that raises
    `SkipTest` WHEN CALLED. A control that invokes a gated method directly
    therefore reports `skipped` and the run says OK - which is a control
    that cannot go red, the very defect being fixed. 0190 hit this and
    recorded it. This pin fails loudly if the arrangement changes, so the
    seven driven cases in 0190's control class cannot go quiet unnoticed.
    """

    LEG = "test_the_live_estate_classifies_under_the_same_ladder"

    def test_the_live_estate_leg_is_still_gated(self):
        gated = getattr(instrument.TheLiveRead, self.LEG)
        self.assertTrue(getattr(gated, "__unittest_skip__", False),
                        "the /sender-emails read must stay gated: the "
                        "2026-10-15 23:00 authorisation is spent")

    def test_the_gated_body_is_still_reachable_through_unwrap(self):
        gated = getattr(instrument.TheLiveRead, self.LEG)
        body = inspect.unwrap(gated)
        self.assertIsNot(body, gated,
                         "the skipped method exposes no __wrapped__, so "
                         "every control that drives it would raise SkipTest "
                         "and report as skipped rather than run")
        self.assertTrue(callable(body))

    def test_calling_the_gate_directly_would_skip(self):
        """The trap itself, demonstrated rather than described, so nobody
        has to take the docstring's word for it."""
        gated = getattr(instrument.TheLiveRead, self.LEG)
        with self.assertRaises(unittest.SkipTest):
            gated(instrument.TheLiveRead(self.LEG))


if __name__ == "__main__":
    unittest.main()
