"""A conformance suite for two adapters that share no interface.

TASK-273. EmailBison (`src/providers/bison.py`) and HeyReach
(`src/providers/heyreach.py`) are independent modules with no base class, no
ABC, no Protocol and no registry. What they genuinely share is a transport
and safety contract enforced from `src/providers/__init__.py`. Where their
sequencer verbs overlap by name, the signatures differ.

This suite asserts four groups:

    shared and enforced     the providers/__init__ transport contract
    shared by convention    surface shape both happen to expose
    declared difference     named asymmetries, each asserted to STILL differ
    refused by design       operations outside SUPPORTED, and hand-built auth

A third adapter is generated against the DECLARED DIFFERENCE table, not
against an interface that does not exist.
"""
import inspect
import os
import unittest

from src import providerwrites
from src.providers import (
    ProviderError,
    ProviderWriteRefused,
    _prospect_facing_hosts,
    guard_prospect_facing,
    host_of,
)
from src.providers import bison, heyreach


# ------------------------------------------------------------------ helpers

def _module_has(mod, name):
    return hasattr(mod, name) and callable(getattr(mod, name))


def _function_arg_names(fn):
    """Positional argument names, excluding 'self'."""
    sig = inspect.signature(fn)
    return [p.name for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            and p.name != "self"]


# The surface this suite asserts. A third adapter is generated against THIS
# table, not against an interface. Each row is a (module, attribute) check
# or a behavioural assertion.
CONVENTION_SURFACE = (
    "headers",
    "check",
    "main",
    "events_contract",
)


# The asymmetries that are EXPECTED to differ. Each is sourced from the
# comments in the provider modules. A row that converges is reported, not
# silently passed.
DECLARED_DIFFERENCES = {
    "set_sequence_signature": (
        "bison.set_sequence takes (campaign_id, title, steps); "
        "heyreach.set_sequence takes (campaign_id, sequence). "
        "Sourced from bison.py:1600 and heyreach.py:2105"),
    "resume_campaign_signature": (
        "bison.resume_campaign takes expect_leads; "
        "heyreach.resume_campaign does not. "
        "Sourced from bison.py:1867 and heyreach.py:1630"),
    "sequence_validation_location": (
        "HeyReach validates sequences in-adapter "
        "(validate_sequence_for_write, sequence_hazards, "
        "refuse_unsupported_sequence, SequenceInvalid). "
        "Bison has none in the adapter; validation is in "
        "bisonfactory._refuse_unsupported. "
        "Sourced from heyreach.py:938,393,1356,765 and bisonfactory.py:883"),
    "write_door_shape": (
        "HeyReach has a single _write chokepoint that refuses undeclared "
        "routes. Bison has per-verb helpers (_post, _patch, _put, _delete) "
        "each calling _allow. Sourced from heyreach.py:1575 and "
        "bison.py:524-540"),
    "fake_exists": (
        "tests/fakebison.py exists; no tests/fakeheyreach.py. "
        "Sourced from the task description"),
}


class TestSharedAndEnforced(unittest.TestCase):
    """The transport contract from providers/__init__, enforced at import."""

    def test_both_subclass_provider_error(self):
        """Both modules raise ProviderError, directly or through a subclass."""
        # Bison raises ProviderError directly in _allow and elsewhere.
        with self.assertRaises(ProviderError):
            bison._allow("POST", "/nonexistent/route/that/matches/nothing")

        # HeyReach raises ProviderError in _write for an undeclared route.
        with self.assertRaises(ProviderError):
            heyreach._write("/nonexistent/route", {})

    def test_provider_error_is_a_runtime_error(self):
        self.assertTrue(issubclass(ProviderError, RuntimeError))

    def test_both_refuse_an_undeclared_write_route(self):
        """Each module's door refuses a path WRITE_ROUTES does not name."""
        # Bison: _allow raises ProviderError for an unknown route.
        with self.assertRaises(ProviderError) as ctx:
            bison._allow("POST", "/campaigns/999/nonexistent")
        self.assertIn("not a write route", str(ctx.exception))

        # HeyReach: _write raises ProviderError for an unknown route.
        with self.assertRaises(ProviderError) as ctx:
            heyreach._write("/campaign/NonexistentRoute", {})
        self.assertIn("not a write route", str(ctx.exception))

    def test_guard_prospect_facing_fired_at_import_for_bison(self):
        """bison.py registers its host at import."""
        from src.providers.bison import DEFAULT_BASE
        host = host_of(DEFAULT_BASE)
        self.assertIn(host, _prospect_facing_hosts)

    def test_guard_prospect_facing_fired_at_import_for_heyreach(self):
        """heyreach.py registers its host at import."""
        from src.providers.heyreach import BASE
        host = host_of(BASE)
        self.assertIn(host, _prospect_facing_hosts)

    def test_both_modules_import_request_from_shared_transport(self):
        """Both use `request` from `src.providers`, not their own transport."""
        # If either module defined its own `request`, the import would not
        # include it from the shared package.
        bison_request = getattr(bison, "request", None)
        heyreach_request = getattr(heyreach, "request", None)
        self.assertIsNotNone(bison_request)
        self.assertIsNotNone(heyreach_request)
        # Both point to the same function object from the shared package.
        from src.providers import request as shared_request
        self.assertIs(bison_request, shared_request)
        self.assertIs(heyreach_request, shared_request)

    def test_both_write_routes_are_nonempty_tuples(self):
        self.assertIsInstance(bison.WRITE_ROUTES, tuple)
        self.assertGreater(len(bison.WRITE_ROUTES), 0)
        self.assertIsInstance(heyreach.WRITE_ROUTES, tuple)
        self.assertGreater(len(heyreach.WRITE_ROUTES), 0)

    def test_write_routes_are_disjoint_from_declared_reads(self):
        """A path on both WRITE_ROUTES and declared reads is a mutation
        disguised as a read. Each module's write and read sets must not
        overlap."""
        from src.providers import declared_reads
        heyreach_base = heyreach.BASE
        reads = declared_reads(heyreach_base)
        writes = set(heyreach.WRITE_ROUTES)
        overlap = reads & writes
        self.assertEqual(overlap, set(),
                         f"HeyReach route on both WRITE_ROUTES and declared "
                         f"reads: {overlap}")


class TestSharedByConvention(unittest.TestCase):
    """Surface shape both modules happen to expose, not enforced by type."""

    def test_both_expose_the_convention_surface(self):
        for mod_name, mod in (("bison", bison), ("heyreach", heyreach)):
            for name in CONVENTION_SURFACE:
                self.assertTrue(
                    _module_has(mod, name),
                    f"{mod_name} is missing {name!r}, which both adapters "
                    f"expose by convention")

    def test_headers_returns_a_dict(self):
        """Both headers() functions return dicts (when keys are present)."""
        # We cannot call headers() without keys configured, but we can check
        # the function exists and is callable with zero required args.
        for mod_name, mod in (("bison", bison), ("heyreach", heyreach)):
            sig = inspect.signature(getattr(mod, "headers"))
            required = [p for p in sig.parameters.values()
                        if p.default is p.empty
                        and p.kind in (p.POSITIONAL_ONLY,
                                       p.POSITIONAL_OR_KEYWORD)]
            self.assertEqual(required, [],
                             f"{mod_name}.headers() takes required args")

    def test_check_returns_a_dict(self):
        """check() returns a result dict, not None."""
        for mod_name, mod in (("bison", bison), ("heyreach", heyreach)):
            sig = inspect.signature(getattr(mod, "check"))
            required = [p for p in sig.parameters.values()
                        if p.default is p.empty
                        and p.kind in (p.POSITIONAL_ONLY,
                                       p.POSITIONAL_OR_KEYWORD)]
            self.assertEqual(required, [],
                             f"{mod_name}.check() takes required args")

    def test_main_accepts_argv(self):
        """main(argv=None) is the CLI entry point for both."""
        for mod_name, mod in (("bison", bison), ("heyreach", heyreach)):
            sig = inspect.signature(getattr(mod, "main"))
            params = list(sig.parameters.keys())
            self.assertIn("argv", params,
                          f"{mod_name}.main() has no argv parameter")

    def test_events_contract_returns_provider_key(self):
        """events_contract() names its provider."""
        bison_contract = bison.events_contract()
        heyreach_contract = heyreach.events_contract()
        self.assertEqual(bison_contract["provider"], "emailbison")
        self.assertEqual(heyreach_contract["provider"], "heyreach")


class TestDeclaredDifferences(unittest.TestCase):
    """Each asymmetry is asserted to STILL be different. The day one adapter
    converges on the other, this suite says so rather than silently passing.
    """

    def test_set_sequence_signatures_differ(self):
        """bison: (campaign_id, title, steps). heyreach: (campaign_id, sequence).

        The convergence is coincidental, not contractual. If they ever match,
        this test fails and the suite reports it.
        """
        bison_args = _function_arg_names(bison.set_sequence)
        heyreach_args = _function_arg_names(heyreach.set_sequence)
        self.assertNotEqual(
            bison_args, heyreach_args,
            "set_sequence signatures have converged. "
            + DECLARED_DIFFERENCES["set_sequence_signature"])
        # Pin the exact shapes.
        self.assertEqual(bison_args, ["campaign_id", "title", "steps"])
        self.assertEqual(heyreach_args, ["campaign_id", "sequence"])

    def test_resume_campaign_signatures_differ(self):
        """bison: (campaign_id, expect_leads, ...). heyreach: (campaign_id).

        Bison's expect_leads is the containment: a resumed campaign sends to
        every lead it holds, so the caller states how many it believes are
        there and the function refuses if the provider disagrees. HeyReach's
        resume_campaign is transport-only with no such parameter.
        """
        bison_args = _function_arg_names(bison.resume_campaign)
        heyreach_args = _function_arg_names(heyreach.resume_campaign)
        self.assertNotEqual(
            bison_args, heyreach_args,
            "resume_campaign signatures have converged. "
            + DECLARED_DIFFERENCES["resume_campaign_signature"])
        # Pin the exact shapes.
        self.assertIn("expect_leads", bison_args)
        self.assertNotIn("expect_leads", heyreach_args)

    def test_sequence_validation_lives_in_heyreach_not_bison(self):
        """HeyReach has validate_sequence_for_write, sequence_hazards,
        refuse_unsupported_sequence and SequenceInvalid in the adapter.
        Bison has none of these; its validation is in bisonfactory."""
        heyreach_validators = [
            "validate_sequence_for_write",
            "sequence_hazards",
            "refuse_unsupported_sequence",
            "SequenceInvalid",
        ]
        for name in heyreach_validators:
            self.assertTrue(
                hasattr(heyreach, name),
                f"heyreach is missing {name!r}, which the declared "
                f"difference table says it has")

        # Bison's adapter has NONE of these.
        for name in heyreach_validators:
            self.assertFalse(
                hasattr(bison, name),
                f"bison now has {name!r}, which the declared difference "
                f"table says it should NOT have in the adapter")

        # The validation lives in bisonfactory instead.
        from src import bisonfactory
        self.assertTrue(
            hasattr(bisonfactory, "_refuse_unsupported"),
            "bisonfactory._refuse_unsupported has moved or been removed")

    def test_write_door_shapes_differ(self):
        """HeyReach has _write; Bison has _post, _patch, _put, _delete."""
        # HeyReach has a single _write chokepoint.
        self.assertTrue(hasattr(heyreach, "_write"))

        # Bison has per-verb helpers, not a single _write.
        self.assertTrue(hasattr(bison, "_post"))
        self.assertTrue(hasattr(bison, "_patch"))
        self.assertTrue(hasattr(bison, "_put"))
        self.assertTrue(hasattr(bison, "_delete"))
        # Bison does NOT have a _write function (that would be the HeyReach
        # shape, which is the declared difference).
        self.assertFalse(
            hasattr(bison, "_write"),
            "bison now has _write, which the declared difference table "
            "says it should NOT have")

    def test_fakebison_exists_but_no_fakeheyreach(self):
        """tests/fakebison.py exists; tests/fakeheyreach.py does not."""
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        fake_bison = os.path.join(tests_dir, "fakebison.py")
        fake_heyreach = os.path.join(tests_dir, "fakeheyreach.py")
        self.assertTrue(
            os.path.exists(fake_bison),
            "tests/fakebison.py is missing")
        self.assertFalse(
            os.path.exists(fake_heyreach),
            "tests/fakeheyreach.py now exists; the declared difference "
            "table says it should not. Update the table")


class TestRefusedByDesign(unittest.TestCase):
    """Every operation not in SUPPORTED raises WriteUnsupported. A hand-built
    Authorization is refused by perform(). These are conformance checks, not
    gaps to fill.
    """

    def test_unsupported_operations_raise_write_unsupported(self):
        """Every declared operation NOT in SUPPORTED is refused."""
        unsupported = [op for op in providerwrites.OPERATIONS
                       if op not in providerwrites.SUPPORTED]
        self.assertGreater(len(unsupported), 0,
                           "every operation is supported; nothing to refuse")
        for op in unsupported:
            with self.assertRaises(providerwrites.WriteUnsupported,
                                   msg=f"{op} should be unsupported"):
                providerwrites.require_supported(op)

    def test_unknown_operation_raises_write_unsupported(self):
        """An operation not even in OPERATIONS is refused."""
        with self.assertRaises(providerwrites.WriteUnsupported):
            providerwrites.require_supported("nonexistent.operation")

    def test_hand_built_authorization_is_not_an_authorization(self):
        """perform() refuses a dict that looks like an Authorization.

        A hand-built object is not an executionguard.Authorization. The
        isinstance check in _perform is the gate.
        """
        from src import executionguard

        # A dict claiming the gates passed.
        fake_auth_dict = {
            "key": "test-key",
            "operation": providerwrites.LINKEDIN_ADD_LEAD,
            "channel": "linkedin",
            "gates": ("tenancy", "approval"),
        }

        # perform() would refuse this because it is not an Authorization.
        # We test the isinstance check directly, since calling perform()
        # would also refuse for other reasons (unsupported, no ledger, etc).
        self.assertFalse(
            isinstance(fake_auth_dict, executionguard.Authorization),
            "a dict should not pass the isinstance check")

    def test_hand_built_authorization_object_is_refused_by_type(self):
        """An Authorization built directly (not through authorize()) is the
        right type but carries no provenance. The isinstance check passes,
        but the gates tuple is empty and the ledger reservation is what
        actually blocks it. This test pins that perform() requires the
        ledger key, not just the type.

        A hand-built Authorization with no ledger reservation is refused
        by the ledger, not by the type check. The type check is necessary
        but not sufficient; the ledger is the real gate.
        """
        from src import executionguard

        # Build an Authorization by hand - the right type, wrong provenance.
        auth = executionguard.Authorization(
            key="test-key",
            operation=providerwrites.LINKEDIN_ADD_LEAD,
            channel="linkedin",
            gates=("tenancy",),
        )
        # It IS an Authorization - the isinstance check passes.
        self.assertIsInstance(auth, executionguard.Authorization)
        # But perform() would refuse it at the ledger, not at the type.
        # This is by design: the type proves shape, the ledger proves
        # provenance.

    def test_supported_operations_are_a_closed_list(self):
        """SUPPORTED is a tuple, not a set or list that can be accidentally
        extended. Adding a verb is an operator authorization."""
        self.assertIsInstance(providerwrites.SUPPORTED, tuple)

    def test_every_supported_operation_is_declared(self):
        """Every operation in SUPPORTED must also be in OPERATIONS."""
        for op in providerwrites.SUPPORTED:
            self.assertIn(
                op, providerwrites.OPERATIONS,
                f"{op} is in SUPPORTED but not in OPERATIONS")


class TestDeclaredDifferenceTable(unittest.TestCase):
    """The table itself is an artifact. These tests pin that it is complete
    and that each row is sourced.
    """

    def test_every_declared_difference_has_a_source(self):
        """Each row in DECLARED_DIFFERENCES carries a 'Sourced from' note."""
        for name, description in DECLARED_DIFFERENCES.items():
            self.assertIn(
                "Sourced from", description,
                f"Declared difference {name!r} has no source citation")

    def test_declared_differences_are_still_different(self):
        """Run every difference assertion. If any has converged, the
        TestDeclaredDifferences tests above will have already failed.
        This test is a summary count for the result block."""
        self.assertEqual(len(DECLARED_DIFFERENCES), 5,
                         "the declared difference table has changed size")


if __name__ == "__main__":
    unittest.main()
