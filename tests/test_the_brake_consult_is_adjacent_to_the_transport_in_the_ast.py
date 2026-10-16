#!/usr/bin/env python3
"""The brake consult and the transport are adjacent AST nodes in `_perform`.

PROPERTY UNDER TEST (structural, pins the behavioural gap named in 0040):

    The `haltfile.require_released()` consult and the `transport(payload)` call
    must be adjacent statements in `_perform`'s body. A statement inserted
    between them opens a window the behavioural proof cannot see — the brake
    still fires and the transport still fires, but something now runs between
    them, and the behavioural test passes because both things happen.

This is an AST-level assertion with a denominator of 1 (one structural
relationship in one function). It does not test behaviour; it pins the
AST shape so that a refactor cannot silently separate the two calls.

Born-red at HEAD: the test passes — the brake consult and transport ARE
adjacent (indices 7 and 8, gap = 1). The mutant proof (insert one statement
between them) makes this test red.
"""
import ast
import os
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROVIDERWRITES = os.path.join(ROOT, "src", "providerwrites.py")


def _find_function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
    return None


def _contains_haltfile_call(node):
    """True if haltfile.require_released() appears anywhere under node."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) \
                and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr == "require_released":
            if isinstance(sub.func.value, ast.Name) \
                    and sub.func.value.id == "haltfile":
                return True
    return False


def _contains_transport_call(node):
    """True if transport(payload) appears anywhere under node."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) \
                and isinstance(sub.func, ast.Name) \
                and sub.func.id == "transport":
            return True
    return False


def _index_of_brake_consult(body):
    for i, stmt in enumerate(body):
        if _contains_haltfile_call(stmt):
            return i
    return None


def _index_of_transport(body):
    for i, stmt in enumerate(body):
        if _contains_transport_call(stmt):
            return i
    return None


class TheBrakeConsultIsAdjacentToTheTransportInTheAST(unittest.TestCase):

    def test_the_brake_consult_and_transport_are_adjacent_ast_nodes(self):
        with open(PROVIDERWRITES, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=PROVIDERWRITES)
        perf = _find_function(tree, "_perform")
        self.assertIsNotNone(perf, "_perform not found in providerwrites.py")

        body = perf.body
        halt_idx = _index_of_brake_consult(body)
        xport_idx = _index_of_transport(body)

        self.assertIsNotNone(
            halt_idx,
            "haltfile.require_released() not found in _perform body; "
            "the brake consult may have been moved or removed")
        self.assertIsNotNone(
            xport_idx,
            "transport(payload) not found in _perform body; "
            "the transport call may have been moved or removed")

        self.assertEqual(
            xport_idx - halt_idx, 1,
            f"brake consult (index {halt_idx}) and transport (index "
            f"{xport_idx}) are {xport_idx - halt_idx} apart; they must "
            f"be adjacent (gap = 1). A gap > 1 means something runs "
            f"between the brake check and the transport, and the "
            f"behavioural proof does not see it")


if __name__ == "__main__":
    unittest.main()