"""A provider body that is not an object crashed the run instead of failing.

`(data or {}).get(...)` is safe against `None` and safe against `{}`, and
every provider module read bodies that way. It is not safe against a truthy
non-mapping: a JSON array, a string, a number. A list body raised
`AttributeError: 'list' object has no attribute 'get'`, which is not a
`ProviderError` - so it went straight past every `except ProviderError`
written to contain exactly this, out of `enrich.run`, and past the
`store.save` at the end of the loop.

A list body is not exotic. It is what an endpoint returns when a proxy
answers instead of the API, when a paginated collection is served
unwrapped, and when a version bump moves the envelope.

The classification matters as much as the containment. Reading a list as
"no results" would report an unavailable provider as an empty one, and this
repository's recurring defect is exactly that: a thing that looks healthy
because nothing looked. So `mapping` raises, and an empty body - which is
genuinely nothing - still returns `{}`.
"""
import unittest

from src import providers
from src.providers import aiark, apify, contactout, heyreach

# Resolved at call time, never bound at import.
#
# `tests/test_audit.py` reloads `src.providers` to prove no module reads a
# credential at import, and a reload builds a *fresh* `ProviderError` class.
# A name bound here at import time would still be the old class, so
# `assertRaises` would not match the exception the reloaded module raises -
# passing alone and erroring under `discover`, which is exactly what this
# file did. The module object survives the reload; the class on it does
# not, so go through the module every time.


def raises(self):
    return self.assertRaises(providers.ProviderError)


class TheHelper(unittest.TestCase):

    def test_an_object_is_itself(self):
        self.assertEqual(providers.mapping({"a": 1}), {"a": 1})

    def test_nothing_is_an_empty_object(self):
        for empty in (None, {}, "", [], 0):
            with self.subTest(empty=empty):
                self.assertEqual(providers.mapping(empty), {})

    def test_a_body_of_the_wrong_type_is_a_provider_error(self):
        for wrong in ([{"a": 1}], "ok", 7, True):
            with self.subTest(wrong=wrong):
                with raises(self):
                    providers.mapping(wrong)

    def test_it_is_a_provider_error_and_not_something_else(self):
        """The whole point. `AttributeError` escapes every handler that
        exists to catch a provider going wrong; `ProviderError` is caught."""
        with raises(self):
            providers.mapping([1])

    def test_it_says_what_it_got_and_where(self):
        try:
            providers.mapping([1], "contactout people")
        except providers.ProviderError as e:
            self.assertIn("contactout people", str(e))
            self.assertIn("list", str(e))
        else:
            self.fail("no error")


class TheProviders(unittest.TestCase):
    """Each parser, against the body that used to crash it."""

    def test_contactout_people(self):
        with raises(self):
            contactout._people([{"full_name": "A"}])

    def test_contactout_still_reads_a_real_body(self):
        people = contactout._people({"profiles": [{"full_name": "Ada"}]})
        self.assertEqual([p["name"] for p in people], ["Ada"])

    def test_contactout_still_reads_an_empty_body(self):
        self.assertEqual(contactout._people(None), [])
        self.assertEqual(contactout._people({}), [])

    def test_aiark_content_part(self):
        """`_content` guards its own argument already; the unguarded read
        was one level in, over the parts of `content`."""
        with raises(self):
            aiark._content({"content": [["text", "hi"]]})

    def test_aiark_still_reads_a_real_body(self):
        self.assertEqual(
            aiark._content({"content": [{"text": '{"a": 1}'}]}), {"a": 1})

    def test_heyreach_conversation(self):
        with raises(self):
            heyreach.inbound_messages(["a message"])

    def test_heyreach_still_reads_a_real_body(self):
        self.assertTrue(isinstance(
            heyreach.inbound_messages({"messages": []}), list))

    def test_heyreach_direction_on_a_wrong_body(self):
        with raises(self):
            heyreach.is_from_correspondent(["them"])

    def test_apify_run_status(self):
        real = apify.request
        try:
            apify.request = lambda *a, **kw: (200, [{"id": "r"}])
            with raises(self):
                apify.run_status("r")
        finally:
            apify.request = real


if __name__ == "__main__":
    unittest.main()
