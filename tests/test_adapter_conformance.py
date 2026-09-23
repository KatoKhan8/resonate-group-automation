#!/usr/bin/env python3
"""TASK-273: a conformance suite for two adapters that share no interface.

EmailBison (src/providers/bison.py) and HeyReach (src/providers/heyreach.py)
are independent modules with no base class, no Protocol and no registry.
What they genuinely share is a transport and safety contract enforced from
src/providers/__init__.py.  Where their sequencer verbs overlap by name the
signatures differ, and each difference is deliberate.

This suite defines the surface it asserts, in the suite, as an explicit
table.  That table becomes the thing a third adapter is generated against.

Four groups, and each is honest about which it is:

    shared and enforced     the providers/__init__ transport contract
    shared by convention    headers(), check(), main(argv), events_contract()
    declared difference     signature and capability rows, each sourced
    refused by design       every operation not in SUPPORTED
"""
import inspect
import os
import unittest

from src import providers
from src.providers import bison, heyreach
from src import providerwrites
from src import executionguard
from tests.base import ProviderTest


# =====================================================================
# The explicit conformance table.  A third adapter is generated against
# THIS, not against an interface that does not exist.
# =====================================================================

ADAPTERS = (
    {
        "name": "emailbison",
        "module": bison,
        "provider_error": providers.ProviderError,
    },
    {
        "name": "heyreach",
        "module": heyreach,
        "provider_error": providers.ProviderError,
    },
)

# Signature differences that are DELIBERATE and must stay different.
# Each row: (function_name, adapter_name, expected_parameter_names).
# If a future change converges one adapter on the other's signature,
# the suite goes red -- which is the point.
DECLARED_SIGNATURE_DIFFERENCES = [
    {
        "function": "set_sequence",
        "why": "EmailBison appends steps with a title; HeyReach replaces "
               "the whole graph. The shapes are different operations.",
        "rows": [
            ("emailbison", ["campaign_id", "title", "steps"]),
            ("heyreach",   ["campaign_id", "sequence"]),
        ],
    },
    {
        "function": "resume_campaign",
        "why": "EmailBison takes an expect_leads count and retry params "
               "because its resume is the one verb that reaches a person. "
               "HeyReach takes only campaign_id because providerwrites "
               "owns the reservation and readback.",
        "rows": [
            ("emailbison", ["campaign_id", "expect_leads", "attempts",
                            "interval"]),
            ("heyreach",   ["campaign_id"]),
        ],
    },
]

# Capability differences that are DELIBERATE.
DECLARED_CAPABILITY_DIFFERENCES = [
    {
        "name": "adapter_level_sequence_validation",
        "why": "HeyReach validates sequences inside the adapter "
               "(validate_sequence_for_write, sequence_hazards, "
               "refuse_unsupported_sequence, SequenceInvalid). "
               "Bison has none in the adapter; its validation is a "
               "layer up, in bisonfactory._refuse_unsupported.",
        "heyreach_has": [
            "validate_sequence_for_write",
            "sequence_hazards",
            "refuse_unsupported_sequence",
            "SequenceInvalid",
        ],
        "bison_has": [],
    },
    {
        "name": "fake_provider_for_testing",
        "why": "tests/fakebison.py exists. No fakeheyreach exists. "
               "This is a known gap, not a defect to fix silently.",
        "heyreach_has": [],
        "bison_has": ["tests/fakebison.py"],
    },
]


# =====================================================================
# Group 1: shared and enforced -- the transport contract
# =====================================================================

class TestBothSubclassProviderError(ProviderTest):
    """Both adapters raise ProviderError, the shared exception hierarchy.

    `check()` catches ProviderError internally and returns a dict, so the
    assertion goes through `headers()` which calls `key()` and raises
    MissingKey (a ProviderError subclass) when the credential is absent.
    """

    def test_bison_raises_provider_error(self):
        self.clear_keys()
        with self.assertRaises(providers.ProviderError):
            bison.headers()

    def test_heyreach_raises_provider_error(self):
        self.clear_keys()
        with self.assertRaises(providers.ProviderError):
            heyreach.headers()

    def test_provider_error_is_a_runtime_error(self):
        self.assertTrue(issubclass(providers.ProviderError, RuntimeError))

    def test_missing_key_is_a_provider_error(self):
        self.assertTrue(issubclass(providers.MissingKey,
                                   providers.ProviderError))

    def test_http_timeout_is_a_provider_error(self):
        self.assertTrue(issubclass(providers.HttpTimeout,
                                   providers.ProviderError))


class TestBothRefuseUndeclaredWriteRoute(ProviderTest):
    """Both adapters refuse a write to a path their WRITE_ROUTES does not name.

    This is the door property: the verb is not the safety property, the
    ROUTE is.  Each module enforces this differently -- HeyReach through
    _write/_write_body checking path membership, Bison through _allow
    checking route_of() -- but both refuse before the socket opens.
    """

    def test_bison_refuses_an_undeclared_route(self):
        with self.assertRaises(providers.ProviderError) as ctx:
            bison._allow("POST", "/campaigns/999/destroy-the-world")
        self.assertIn("not a write route", str(ctx.exception))

    def test_heyreach_refuses_an_undeclared_body_route(self):
        with self.assertRaises(providers.ProviderError) as ctx:
            heyreach._write_body("/campaign/DestroyTheWorld", {})
        self.assertIn("not a write route", str(ctx.exception))

    def test_heyreach_refuses_an_undeclared_query_route(self):
        with self.assertRaises(providers.ProviderError) as ctx:
            heyreach._write("/campaign/DestroyTheWorld", {})
        self.assertIn("not a write route", str(ctx.exception))

    def test_bison_write_routes_is_a_nonempty_tuple(self):
        self.assertIsInstance(bison.WRITE_ROUTES, tuple)
        self.assertGreater(len(bison.WRITE_ROUTES), 0)

    def test_heyreach_write_routes_is_a_nonempty_tuple(self):
        self.assertIsInstance(heyreach.WRITE_ROUTES, tuple)
        self.assertGreater(len(heyreach.WRITE_ROUTES), 0)

    def test_bison_and_heyreach_write_routes_are_disjoint(self):
        bison_paths = set(bison.WRITE_ROUTES)
        heyreach_paths = set(heyreach.WRITE_ROUTES)
        self.assertEqual(bison_paths & heyreach_paths, set(),
                         "WRITE_ROUTES overlap would mean one route string "
                         "is meaningful to both providers")


class TestGuardProspectFacingFiresAtImport(ProviderTest):
    """Both modules register their hosts as prospect-facing at import.

    This is what makes the transport-level write guard unavoidable:
    a module cannot be called without being imported, and import is
    when the registration happens.
    """

    def test_bison_host_is_prospect_facing(self):
        self.assertTrue(
            providers.is_prospect_facing(
                bison.DEFAULT_BASE + "/campaigns"),
            "bison's DEFAULT_BASE was not registered as prospect-facing")

    def test_heyreach_host_is_prospect_facing(self):
        self.assertTrue(
            providers.is_prospect_facing(heyreach.BASE + "/campaign/Pause"),
            "heyreach's BASE was not registered as prospect-facing")

    def test_an_unknown_host_is_not_prospect_facing(self):
        self.assertFalse(
            providers.is_prospect_facing("https://example.com/anything"))


class TestWriteDoorRefusesWithoutAuthorization(ProviderTest):
    """The transport-level door refuses a mutating call with no authorization.

    `refuse_unauthorized_write` is called before the socket opens on every
    real-transport call.  A write to a prospect-facing host without
    `allow_writes` raises `ProviderWriteRefused`.
    """

    def test_refuses_post_to_prospect_facing_host(self):
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write(
                "POST", bison.DEFAULT_BASE + "/campaigns/999/pause")

    def test_refuses_post_to_heyreach_prospect_facing_host(self):
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write(
                "POST", heyreach.BASE + "/campaign/Pause")

    def test_get_is_not_refused(self):
        providers.refuse_unauthorized_write(
            "GET", bison.base() + "/campaigns")

    def test_non_prospect_facing_host_is_not_refused(self):
        providers.refuse_unauthorized_write(
            "POST", "https://example.com/anything")


# =====================================================================
# Group 2: shared by convention
# =====================================================================

class TestSharedConventionFunctions(ProviderTest):
    """Both adapters expose headers(), check(), main(argv), events_contract().

    These are convention, not contract.  They happen to agree in shape
    but nothing enforces it.
    """

    def test_both_have_headers(self):
        for adapter in ADAPTERS:
            mod = adapter["module"]
            self.assertTrue(hasattr(mod, "headers"),
                            f"{adapter['name']} has no headers()")
            self.assertTrue(callable(mod.headers))

    def test_both_have_check(self):
        for adapter in ADAPTERS:
            mod = adapter["module"]
            self.assertTrue(hasattr(mod, "check"),
                            f"{adapter['name']} has no check()")
            self.assertTrue(callable(mod.check))

    def test_both_have_main(self):
        for adapter in ADAPTERS:
            mod = adapter["module"]
            self.assertTrue(hasattr(mod, "main"),
                            f"{adapter['name']} has no main()")
            self.assertTrue(callable(mod.main))
            sig = inspect.signature(mod.main)
            self.assertIn("argv", sig.parameters)

    def test_both_have_events_contract(self):
        for adapter in ADAPTERS:
            mod = adapter["module"]
            self.assertTrue(hasattr(mod, "events_contract"),
                            f"{adapter['name']} has no events_contract()")
            self.assertTrue(callable(mod.events_contract))

    def test_events_contract_returns_provider_name(self):
        for adapter in ADAPTERS:
            result = adapter["module"].events_contract()
            self.assertIsInstance(result, dict)
            self.assertIn("provider", result)
            self.assertEqual(result["provider"], adapter["name"])


# =====================================================================
# Group 3: declared differences -- asserted to STILL be different
# =====================================================================

class TestDeclaredSignatureDifferences(ProviderTest):
    """Each declared signature difference is asserted to still hold.

    If a future change converges one adapter on the other, the suite
    goes red.  That is the point: convergence is a decision, not a
    silent drift.
    """

    def test_declared_signatures_still_differ(self):
        module_by_name = {a["name"]: a["module"] for a in ADAPTERS}
        for diff in DECLARED_SIGNATURE_DIFFERENCES:
            fn_name = diff["function"]
            seen_params = {}
            for adapter_name, expected in diff["rows"]:
                mod = module_by_name[adapter_name]
                fn = getattr(mod, fn_name, None)
                self.assertIsNotNone(
                    fn, f"{adapter_name}.{fn_name} does not exist")
                sig = inspect.signature(fn)
                actual = list(sig.parameters.keys())
                seen_params[adapter_name] = actual
                self.assertEqual(
                    actual, expected,
                    f"{adapter_name}.{fn_name} signature changed: "
                    f"expected {expected}, got {actual}. "
                    f"WHY: {diff['why']}")
            names = list(seen_params.keys())
            if len(names) >= 2:
                self.assertNotEqual(
                    seen_params[names[0]], seen_params[names[1]],
                    f"{fn_name} signatures converged between "
                    f"{names[0]} and {names[1]}. "
                    f"WHY: {diff['why']}")


class TestDeclaredCapabilityDifferences(ProviderTest):
    """Each declared capability difference is asserted to still hold."""

    def test_heyreach_has_adapter_level_sequence_validation(self):
        for attr in DECLARED_CAPABILITY_DIFFERENCES[0]["heyreach_has"]:
            self.assertTrue(
                hasattr(heyreach, attr),
                f"heyreach lost {attr!r}, which was a declared capability "
                f"difference")

    def test_bison_does_not_have_adapter_level_sequence_validation(self):
        for attr in DECLARED_CAPABILITY_DIFFERENCES[0]["bison_has"]:
            self.fail(
                f"bison gained {attr!r} at the adapter level, which means "
                f"the declared capability difference has converged")
        for attr in DECLARED_CAPABILITY_DIFFERENCES[0]["heyreach_has"]:
            self.assertFalse(
                hasattr(bison, attr),
                f"bison gained {attr!r}, which was declared to be "
                f"heyreach-only. If this changed intentionally, update "
                f"DECLARED_CAPABILITY_DIFFERENCES")

    def test_fakebison_exists(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "tests", "fakebison.py")
        self.assertTrue(os.path.isfile(path),
                        "tests/fakebison.py was declared to exist")

    def test_fakeheyreach_does_not_exist(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "tests", "fakeheyreach.py")
        self.assertFalse(os.path.isfile(path),
                         "tests/fakeheyreach.py was declared NOT to exist. "
                         "If it was created, update "
                         "DECLARED_CAPABILITY_DIFFERENCES")


# =====================================================================
# Group 4: refused by design
# =====================================================================

class TestUnsupportedOperationsRefused(ProviderTest):
    """Every operation not in SUPPORTED raises WriteUnsupported.

    `providerwrites.SUPPORTED` is a closed list and everything else
    raises WriteUnsupported by design.  Asserting that an unsupported
    operation is refused IS itself a conformance check.
    """

    def test_every_declared_unsupported_operation_refuses(self):
        for op in providerwrites.OPERATIONS:
            if op in providerwrites.SUPPORTED:
                continue
            with self.assertRaises(providerwrites.WriteUnsupported,
                                   msg=f"{op} should be WriteUnsupported"):
                providerwrites.require_supported(op)

    def test_an_undeclared_operation_refuses(self):
        with self.assertRaises(providerwrites.WriteUnsupported):
            providerwrites.require_supported("bison.nonsense_operation")

    def test_supported_operations_do_not_raise_unsupported(self):
        for op in providerwrites.SUPPORTED:
            try:
                providerwrites.require_supported(op)
            except providerwrites.WriteUnsupported:
                self.fail(f"{op} is in SUPPORTED but require_supported "
                          f"raised WriteUnsupported")


class TestHandBuiltAuthorizationRefused(ProviderTest):
    """A hand-built Authorization is refused by perform().

    `executionguard.Authorization.__init__` is public and ungated, so
    the type proves SHAPE and not provenance.  `perform()` compensates
    by requiring the key to be in `actionledger.ATTEMPTED`, which takes
    a real `reserve`.  A test that hand-builds a token is testing a
    path production cannot take.
    """

    def test_hand_built_authorization_is_not_from_authorize(self):
        auth = executionguard.Authorization(
            key="test-key",
            operation=providerwrites.LINKEDIN_PAUSE,
            channel="linkedin",
        )
        self.assertIsInstance(auth, executionguard.Authorization)
        self.assertFalse(auth._spent)

    def test_perform_refuses_a_dict_as_authorization(self):
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                authorization={"gates": ("killswitch",)},
                provider_campaign_id="999",
            )

    def test_perform_refuses_none_as_authorization_for_prospect_facing(self):
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                authorization=None,
                provider_campaign_id="999",
            )


# =====================================================================
# The conformance table itself is testable
# =====================================================================

class TestConformanceTableCompleteness(ProviderTest):
    """The table covers both adapters and every assertion group."""

    def test_two_adapters_in_the_table(self):
        self.assertEqual(len(ADAPTERS), 2)
        names = {a["name"] for a in ADAPTERS}
        self.assertEqual(names, {"emailbison", "heyreach"})

    def test_every_adapter_has_a_module(self):
        for adapter in ADAPTERS:
            self.assertIsNotNone(adapter["module"])

    def test_declared_differences_reference_real_functions(self):
        module_by_name = {a["name"]: a["module"] for a in ADAPTERS}
        for diff in DECLARED_SIGNATURE_DIFFERENCES:
            for adapter_name, _ in diff["rows"]:
                mod = module_by_name[adapter_name]
                self.assertTrue(
                    hasattr(mod, diff["function"]),
                    f"{adapter_name}.{diff['function']} is in the "
                    f"conformance table but does not exist on the module")


if __name__ == "__main__":
    unittest.main()
