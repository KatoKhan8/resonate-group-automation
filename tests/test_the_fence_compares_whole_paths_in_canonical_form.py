"""TASK 0220: the fence compares whole paths, and it says WHY it refused.

0180 fenced its one authorised read by the path's LAST SEGMENT, so
`/api/campaigns/{id}/sender-emails` was ALLOWED by a fence written for
`/api/sender-emails`. 0200 replaced it with `path_exact_fence`, which compares
the whole path against a set, and corrected the negative controls. Both
repairs hold and are pinned in
`tests/test_the_attached_pool_is_one_owner_per_campaign.py`.

WHAT THIS MODULE ADDS, AND WHY IT IS NOT DECORATION.

`path_exact_fence` already refuses every non-canonical path, because a raw
string like `/api/campaigns/499/../sender-emails` is simply not in the allowed
set. **The verdict was right and the REASON was unrecorded** - and this task's
sibling finding is precisely that a guard which refuses for the wrong reason
reads exactly like a guard that refuses for the right one. TASK 0210 planted a
brake path of `C:\\Temp\\nowhere\\BRAKE` and watched two tests go red, and the
tests were red because the PARENT directory was missing, not because the path
was wrong - a plant "caught" by an accident.

So two properties are pinned here:

1. **The fence states its reason.** A refusal carries `refused_because`, so a
   test can tell the canonical-form leg from the set-membership leg from the
   method leg. Without it, test 3 below cannot be written at all: it can only
   observe "refused", which the fence already was.

2. **A path is compared whole and only in CANONICAL form.** Any path that is
   not byte-identical to its own normalisation is REFUSED rather than
   normalised. This is the load-bearing direction: the obvious future
   "cleanup" - canonicalise the path, then compare - **fails open**, because
   `/api/campaigns/499/../sender-emails` normalises to `/api/sender-emails`
   and would then be ALLOWED, while the raw string a server receives may be
   routed somewhere else entirely. Test 3 goes red on that refactor.

Nothing here makes a request. `path_exact_fence` wraps no inner transport and
raises on every outcome, allowed or refused.
"""
import os
import sys
import unittest
import urllib.request
from urllib.parse import urlsplit

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "canary_pool_readback",
    os.path.join(ROOT, "scripts", "canary_pool_readback.py"))
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)

from src import providers  # noqa: E402

#: A path whose RAW form sits under the per-campaign endpoint and whose
#: NORMALISED form is the authorised estate route. The whole point of the
#: canonical rule.
#:
#: TWO `..`, not one, and the premise test below is why: a single `..`
#: cancels only `499` and leaves `/api/campaigns/sender-emails`, which is not
#: the allowed path and so would have proved nothing. The first draft of this
#: module used one, and `test_the_traversal_path_really_does_normalise_into_
#: the_allowed_one` failed on exactly that - a premise test earning its place
#: on its first run.
TRAVERSAL = "/api/campaigns/499/../../sender-emails"


def _refuse(allowed, method, path, body=None):
    """Drive the fence once and return its recorded row.

    Asserts the refusal itself, so a caller that stops raising cannot be
    read as a caller that refused with a different reason.
    """
    transport, observed = rb.path_exact_fence(allowed)
    try:
        transport(method, "https://send.resonategroup.co" + path, body=body)
    except rb.OutsideAuthorisation:
        return observed[-1]
    raise AssertionError(
        "the fence did not refuse %s %s - nothing below is meaningful"
        % (method, path))


class TheFenceStatesItsReason(unittest.TestCase):
    """Property 1. A verdict without a reason cannot be controlled."""

    def test_the_fence_says_why_it_refused(self):
        row = _refuse([rb.ROUTE_ESTATE], "GET", "/api/campaigns")
        self.assertEqual(row["verdict"], "REFUSED_BY_FENCE")
        self.assertIn("refused_because", row,
                      "a refusal that cannot say which leg fired is a "
                      "refusal no control can distinguish from an accident")

    def test_a_wrong_method_is_refused_as_method_not_as_path(self):
        row = _refuse([rb.ROUTE_ESTATE], "POST", rb.ROUTE_ESTATE)
        self.assertEqual(row["refused_because"], "method")

    def test_an_unknown_path_is_refused_as_path(self):
        row = _refuse([rb.ROUTE_ESTATE], "GET", "/api/campaigns/499")
        self.assertEqual(row["refused_because"], "path")

    def test_a_body_is_refused_as_body(self):
        row = _refuse([rb.ROUTE_ESTATE], "GET", rb.ROUTE_ESTATE, body=b"x")
        self.assertEqual(row["refused_because"], "body")


class APathIsComparedOnlyInCanonicalForm(unittest.TestCase):
    """Property 2, and the reason the rule is refuse-rather-than-normalise."""

    def test_a_traversal_path_is_refused_as_non_canonical(self):
        """NOT merely "refused". The reason has to be the canonical-form leg,
        because a refusal on set membership would survive the refactor that
        canonicalises first - and that refactor fails open."""
        row = _refuse([rb.ROUTE_ESTATE], "GET", TRAVERSAL)
        self.assertEqual(row["refused_because"], "not-canonical")

    def test_the_traversal_path_really_does_normalise_into_the_allowed_one(self):
        """The premise of the test above, measured rather than asserted. If
        this ever fails, TRAVERSAL stopped being a hazard and the test above
        stopped proving anything."""
        import posixpath
        self.assertEqual(posixpath.normpath(TRAVERSAL), rb.ROUTE_ESTATE)
        self.assertNotEqual(TRAVERSAL, rb.ROUTE_ESTATE)

    def test_a_trailing_slash_is_refused_as_non_canonical(self):
        row = _refuse([rb.ROUTE_ESTATE], "GET", rb.ROUTE_ESTATE + "/")
        self.assertEqual(row["refused_because"], "not-canonical")

    def test_a_doubled_separator_is_refused_as_non_canonical(self):
        row = _refuse([rb.ROUTE_ESTATE], "GET", "/api//sender-emails")
        self.assertEqual(row["refused_because"], "not-canonical")

    def test_a_percent_encoded_form_is_refused_as_non_canonical(self):
        """`%2D` is `-`. Decoding before comparing is the same class of
        mistake as normalising before comparing."""
        row = _refuse([rb.ROUTE_ESTATE], "GET", "/api/sender%2Demails")
        self.assertEqual(row["refused_because"], "not-canonical")

    def test_the_authorised_path_itself_is_canonical_and_passes(self):
        """THE CONTROL. A fence that refuses everything proves nothing, and
        the authorised route must not become collateral damage."""
        transport, observed = rb.path_exact_fence([rb.ROUTE_ESTATE])
        with self.assertRaises(rb.OutsideAuthorisation) as caught:
            transport("GET", "https://send.resonategroup.co"
                      + rb.ROUTE_ESTATE + "?page=1")
        self.assertEqual(observed[-1]["verdict"],
                         "ALLOWED_BY_FENCE_BUT_NOT_SENT")
        self.assertNotIn("refused_because", observed[-1])
        self.assertIn("sends nothing", str(caught.exception))

    def test_the_per_campaign_route_is_canonical_and_still_refused_on_path(self):
        """The second endpoint 0180 admitted. It is perfectly canonical, so
        it must be refused by SET MEMBERSHIP - this is what keeps the
        canonical rule from quietly becoming the only check."""
        row = _refuse([rb.ROUTE_ESTATE], "GET",
                      rb.ROUTE_CAMPAIGN_SENDERS.format(campaign_id=499))
        self.assertEqual(row["refused_because"], "path")


class EveryNegativeControlNamesARouteAnAdapterGenerates(unittest.TestCase):
    """0180's third control named `/api/campaigns/{id}/senders`, which no
    adapter here emits, so refusing it proved nothing. 0200 corrected it and
    measured provenance for the two SENDER routes. This measures all five,
    at the transport seam, so a control cannot drift back into decoration.

    NO NETWORK, three ways: the transport is a raiser installed before the
    first call, `urlopen` is replaced by a tripwire, and the key is the
    suite's placeholder. The placeholder is load-bearing - `tests/__init__`
    pops every credential, so without it the adapter raises `MissingKey`
    before it builds a URL and this class measures nothing.
    """

    class Sealed(Exception):
        """Narrow on purpose: catching bare `Exception` would swallow a
        `MissingKey` and leave the measurement empty."""

    def setUp(self):
        self.seen = []

        def raiser(method, url, headers=None, body=None, timeout=None):
            self.seen.append((str(method).upper(), url))
            raise self.Sealed("TASK 0220: nothing is sent")

        providers.set_transport(raiser)
        self.addCleanup(providers.reset_transport)

        previous = {"BISON_KEY": os.environ.get("BISON_KEY")}
        self.addCleanup(self._restore, previous)
        os.environ["BISON_KEY"] = "test-key-not-real"

        real = urllib.request.urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", real)

        def forbidden(*a, **k):
            raise AssertionError("a request bypassed the transport seam")

        urllib.request.urlopen = forbidden

    @staticmethod
    def _restore(previous):
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _paths(self, fn, *args):
        self.seen = []
        try:
            fn(*args)
        except self.Sealed:
            pass
        self.assertTrue(self.seen, "the adapter never reached the transport, "
                                   "so this measures nothing")
        return {urlsplit(url).path for _m, url in self.seen}

    def test_every_control_path_is_emitted_by_some_adapter(self):
        from src.providers import bison
        emitted = set()
        for fn, args in ((bison.sender_emails, ()),
                         (bison.campaign_senders, (499,)),
                         (bison.campaign, (499,)),
                         (bison.list_all_campaigns, ())):
            emitted |= self._paths(fn, *args)
        for method, path in rb.NEGATIVE_CONTROLS:
            with self.subTest(control="%s %s" % (method, path)):
                self.assertIn(
                    path, emitted,
                    "this control names a path no adapter in this tree "
                    "generates, which is 0180's defect: refusing it proves "
                    "nothing about the routes that can actually arrive")

    def test_the_straw_path_0180_used_is_still_emitted_by_nobody(self):
        """The control FOR the control above: the assertion can fail."""
        from src.providers import bison
        emitted = set()
        for fn, args in ((bison.sender_emails, ()),
                         (bison.campaign_senders, (499,)),
                         (bison.campaign, (499,)),
                         (bison.list_all_campaigns, ())):
            emitted |= self._paths(fn, *args)
        self.assertNotIn(rb.ROUTE_NOBODY_GENERATES.format(campaign_id=499),
                         emitted)

    def test_every_control_is_actually_refused_by_the_fence(self):
        transport, observed = rb.path_exact_fence([rb.ROUTE_ESTATE])
        for method, path in rb.NEGATIVE_CONTROLS:
            with self.subTest(control="%s %s" % (method, path)):
                with self.assertRaises(rb.OutsideAuthorisation):
                    transport(method,
                              "https://send.resonategroup.co" + path)
        self.assertEqual(len(observed), len(rb.NEGATIVE_CONTROLS))
        self.assertTrue(all(r["verdict"] == "REFUSED_BY_FENCE"
                            for r in observed))


if __name__ == "__main__":
    unittest.main()
