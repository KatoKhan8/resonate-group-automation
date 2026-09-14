"""The model was never told what Productive is, and one rung's job was to say.

Measured 2026-09-14 by rendering the real `linkedin_note` prompt for
`ogpartner-dk`: the string "Productive" occurred ZERO times in it, and so did
"time tracking", "budgeting", "resourcing" and "invoicing". Everything the
model had to argue from was `angle_wording` - two phrases for that persona -
so every rung reached for the same one. The sequence it produced asked about
profitability four times in four different ways and never named the product.

The ladder took the blame for that. The ladder was right: `step.purpose`
reaches the prompt correctly and each rung names a different job. The input
was missing, which is a different defect with a different fix.

These tests pin the chain rather than the wording: the config states a
product, `clients.product` reads it, `generate.context_for` puts it in the
context, and it survives into the rendered prompt for BOTH channels. Each
link is asserted separately, because a block that is assembled and not
rendered is exactly the shape of defect this repository keeps finding.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import cadencelibrary, clients, generate, store
from tests.base import FIXTURES, pin_client_config


class ProductTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-product-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = pin_client_config(self)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid="meridian"):
        return store.get(rid)

    def contact(self, key="ivana-saric"):
        return next(c for c in self.rec()["contacts"] if c["key"] == key)


class TestTheConfigStatesAProduct(ProductTest):
    def test_the_client_says_what_it_sells(self):
        product = clients.product(self.config)
        self.assertTrue(product.get("name"))
        self.assertTrue(product.get("what_it_is"))
        self.assertTrue(product.get("capabilities"))

    def test_a_client_who_has_not_said_gets_nothing_invented(self):
        # `{}`, never a default. A guessed product description is the one
        # sentence no downstream gate can catch: `lint` and `claims` check
        # what is asserted about the RECORD, and a false statement about our
        # own software is grounded in nothing either of them reads.
        self.assertEqual(clients.product({}), {})
        self.assertEqual(clients.product(None), {})
        self.assertEqual(clients.product({"product": "a string, not a block"}), {})

    def test_a_capability_with_no_words_is_not_a_capability(self):
        config = {"product": {"name": "Thing", "what_it_is": "  ",
                              "capabilities": {"real": "words here",
                                               "empty": "  ", "none": None}}}
        product = clients.product(config)
        self.assertEqual(product.get("name"), "Thing")
        self.assertNotIn("what_it_is", product)
        self.assertEqual(sorted(product["capabilities"]), ["real"])


class TestItReachesBothPrompts(ProductTest):
    def context(self, step, step_key):
        return generate.context_for(step, self.rec(), self.contact(),
                                    self.config, step_key)

    def rendered(self, step, step_key):
        return generate.render_prompt(step, self.rec(), self.contact(),
                                      self.config, step_key)

    def test_the_linkedin_context_carries_it(self):
        self.assertTrue(self.context("linkedin_note", "day3").get("product"))

    def test_the_email_context_carries_it(self):
        self.assertTrue(self.context("draft", "day1").get("product"))

    def test_it_survives_into_the_rendered_linkedin_prompt(self):
        # ASSEMBLED IS NOT DELIVERED. `context_for` returning a block proves
        # only that a dict was built; the model reads the rendered string.
        name = clients.product(self.config)["name"]
        self.assertIn(name, self.rendered("linkedin_note", "day3"))

    def test_it_survives_into_the_rendered_email_prompt(self):
        name = clients.product(self.config)["name"]
        self.assertIn(name, self.rendered("draft", "day1"))

    def test_the_capabilities_travel_with_it(self):
        caps = clients.product(self.config)["capabilities"]
        rendered = self.rendered("draft", "day1")
        for words in caps.values():
            self.assertIn(words, rendered)

    def test_a_client_with_no_product_renders_no_product(self):
        # The absent case reaches the prompt as an empty block rather than as
        # a missing key with an invented substitute somewhere downstream.
        config = dict(self.config)
        config.pop("product", None)
        block = generate.context_for("draft", self.rec(), self.contact(),
                                     config, "day1")
        self.assertEqual(block.get("product"), {})


class TestTheLaddersCannotDriftAgain(unittest.TestCase):
    """The texts existed twice and production used the registry's copy.

    A `generate.EMAIL_LADDER` edit changed the fallback nobody resolves to,
    while `productive_li_heavy_v1` - which names `email_five` - carried on
    with the old rung. The LinkedIn edit beside it DID take effect, because
    that sequence names no LinkedIn ladder. Same edit, two outcomes, no error
    anywhere.

    Identity, not equality: two tuples that happen to match today are what
    the old arrangement had.
    """

    def test_the_email_ladder_is_the_registry_entry(self):
        self.assertIs(generate.EMAIL_LADDER,
                      cadencelibrary.LADDER_REGISTRY["email_five"])

    def test_the_linkedin_ladder_is_the_registry_entry(self):
        self.assertIs(generate.LINKEDIN_LADDER,
                      cadencelibrary.LADDER_REGISTRY["linkedin_default"])

    def test_the_channel_defaults_resolve_to_those(self):
        self.assertIs(generate.LADDERS["email"], generate.EMAIL_LADDER)
        self.assertIs(generate.LADDERS["linkedin"], generate.LINKEDIN_LADDER)


class TestARungAsksForTheProduct(unittest.TestCase):
    """One rung per channel has to be the one that says what it is.

    Asserted on the resolved purpose a prompt would receive, not by reading
    the constant: `purpose_for` is what `step_block` calls and a rung that
    the resolver never reaches is a rung nobody is written to.
    """

    def purposes(self, sequence_name, channel):
        seq = cadencelibrary.named(sequence_name)
        steps = [s for s in seq if s.get("channel") == channel]
        return [generate.purpose_for(channel, n, sequence=seq)
                for n in range(1, len(steps) + 1)]

    def test_the_five_step_email_ladder_has_a_product_rung(self):
        named = [p for p in self.purposes("productive_li_heavy_v1", "email")
                 if p and "product" in p.lower()]
        self.assertTrue(named, "no email rung asks for the product")

    def test_the_linkedin_ladder_has_a_product_rung(self):
        named = [p for p in self.purposes("productive_li_heavy_v1", "linkedin")
                 if p and "product" in p.lower()]
        self.assertTrue(named, "no linkedin rung asks for the product")

    def test_the_email_breakup_rung_is_untouched(self):
        # EmailBison 481 holds nine real leads carrying approved
        # subject_5/body_5 generated against this rung. Rungs 1 and 3 changed
        # on 2026-09-14 and this one deliberately did not.
        purposes = self.purposes("productive_li_heavy_v1", "email")
        self.assertEqual(
            purposes[4],
            "Close the loop. Give them an easy no, make no new pitch, ask "
            "for nothing beyond permission to stop.")


if __name__ == "__main__":
    unittest.main()
