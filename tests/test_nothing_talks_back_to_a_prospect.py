#!/usr/bin/env python3
"""This system may read a reply. It may not answer one.

Resonate OS is allowed to detect a reply, classify it, summarise it, and put a
draft in front of a human. It is not allowed to send anything to a prospect in
response, and that boundary is not a policy setting - it is meant to be absent
from the code entirely.

The distinction matters more than it looks. Every other guard here answers
"may this action happen?"; this one answers "does this action exist?". A
killswitch can be turned off and an approval can be granted, but a capability
that was never built cannot be enabled by accident, and the tests below are
about the SHAPE of the system rather than the state of a flag.

WHAT WOULD MAKE THIS FILE FAIL, correctly: somebody adds a provider operation
that sends a message, or an LLM entry point that takes an inbound message and
returns something to send back. Both are reasonable things to build one day.
Neither may arrive quietly.
"""
import inspect
import os
import re
import unittest

from src import inbound, llm, providerwrites, tagsync

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Verbs that name an outbound message rather than a lifecycle change.
#
# Matched as WHOLE WORDS against the operation's verb, not as substrings.
# A first version used substrings and accused `assign_sender` of being a
# send - it binds an identity to a campaign and transmits nothing - which is
# the kind of false positive that gets a safety test deleted rather than
# fixed.
SENDING_VERBS = frozenset((
    "send", "send_message", "message", "reply", "respond", "inmail", "dm",
    "comment", "post", "connect", "invite"))


class TheVocabularyContainsNoSend(unittest.TestCase):
    """The strongest available statement: it cannot be ASKED for.

    `providerwrites.OPERATIONS` is the complete list of things this system
    knows how to want from a provider. If none of them is a message, then no
    amount of authorisation produces one.
    """

    def test_no_declared_operation_sends_a_message(self):
        offenders = [op for op in providerwrites.OPERATIONS
                     if op.split(".")[-1].lower() in SENDING_VERBS]
        self.assertEqual(offenders, [],
                         "an operation that sends a message has been declared")

    def test_the_check_would_notice_one(self):
        """Guard the guard: a set that matches nothing passes everything."""
        for verb in ("heyreach.send_message", "bison.reply",
                     "heyreach.connect"):
            self.assertIn(verb.split(".")[-1], SENDING_VERBS, verb)
        for allowed in ("heyreach.assign_sender", "bison.add_lead",
                        "heyreach.pause"):
            self.assertNotIn(allowed.split(".")[-1], SENDING_VERBS, allowed)

    def test_the_declared_operations_are_lifecycle_and_staging_only(self):
        """Named explicitly, so adding one is a decision rather than a drift."""
        self.assertEqual(
            set(providerwrites.OPERATIONS),
            {"heyreach.add_lead", "heyreach.create_list",
             "heyreach.create_campaign", "heyreach.set_sequence",
             "heyreach.assign_sender", "heyreach.set_limits",
             "heyreach.pause", "heyreach.activate",
             "bison.add_lead", "bison.create_campaign", "bison.set_sequence",
             "bison.assign_sender", "bison.set_limits", "bison.pause",
             "bison.stop_lead", "bison.activate",
             # Added 2026-09-15. It is a LIFECYCLE verb and it belongs in this
             # set for the reason the set exists: starting a campaign that
             # holds ZERO leads changes a campaign's state and sends nothing.
             # The verb that sends is `heyreach.activate`, which is still here
             # and still sealed.
             "heyreach.start_empty_for_staging"})

    def test_and_no_send_verb_is_supported(self):
        """Every declared write stops something or stages something.

        The list grew on 2026-09-13 and the property did not. Each addition
        either reduces what somebody receives or builds a campaign that is
        left `paused` and cannot send:

          heyreach.pause          halts a campaign
          bison.pause             halts a campaign
          bison.stop_lead         halts ONE person's remaining emails
          bison.create_campaign   creates a DRAFT, which cannot send
          bison.set_sequence      writes copy into a campaign that is stopped
          heyreach.set_sequence   writes copy into a campaign with no list,
                                  no leads, and no verb that can start it
          heyreach.start_empty_for_staging
                                  starts a campaign holding NOBODY so it can
                                  be paused and staged into. The provider
                                  refuses leads on a DRAFT campaign and
                                  refuses to pause an inactive one, so this
                                  is the only route to a stageable campaign -
                                  and its condition refuses any campaign the
                                  provider says holds a lead
          heyreach.add_lead       stages a person into a campaign the
                                  provider has just confirmed cannot send -
                                  and is REFUSED against any campaign that
                                  can. This is the first entry whose safety
                                  is a property of the destination rather
                                  than of the verb, which is why it needed
                                  `CONDITIONAL` and not just a place in the
                                  tuple

        Enumerated rather than derived, so adding one stays a decision. The
        assertion that actually guards this file is the loop below.
        """
        from src import providerwrites as pw
        self.assertEqual(
            providerwrites.SUPPORTED,
            (pw.LINKEDIN_PAUSE, pw.EMAIL_PAUSE, pw.EMAIL_STOP_LEAD,
             pw.EMAIL_CREATE_CAMPAIGN, pw.EMAIL_SET_SEQUENCE,
             pw.LINKEDIN_SET_SEQUENCE, pw.LINKEDIN_ADD_LEAD,
             pw.LINKEDIN_START_EMPTY_FOR_STAGING))
        for operation, (_channel, prospect_facing, _why) in                 providerwrites.OPERATIONS.items():
            # NARROWED, TASK-137. This asserted that NOTHING
            # prospect-facing was supported - true of a system that
            # had never written to a prospect, and unable to tell
            # staging a lead into a campaign that cannot send apart
            # from sending somebody a message. The first is how the
            # second becomes possible safely. The property that has
            # to hold now: no prospect-facing verb is enabled without
            # a condition deciding, per write, whether it reaches
            # anyone. `heyreach.add_lead` has one; the activate verbs
            # have none and so can never be admitted.
            if not prospect_facing:
                continue
            if providerwrites.is_supported(operation):
                self.assertTrue(
                    providerwrites.is_conditional(operation),
                    operation)
            else:
                self.assertFalse(
                    providerwrites.is_conditional(operation),
                    operation)


class NoModelIsAskedWhatToSayBack(unittest.TestCase):
    """An LLM may summarise an inbound message. It may not answer it."""

    def test_no_llm_entry_point_takes_an_inbound_message(self):
        suspects = []
        for name, fn in vars(llm).items():
            if not callable(fn) or not hasattr(fn, "__code__"):
                continue
            args = inspect.signature(fn).parameters
            takes_inbound = any(a in args for a in
                                ("inbound", "incoming", "their_message",
                                 "reply", "reply_text", "conversation"))
            returns_a_send = any(w in name.lower() for w in
                                 ("reply", "respond", "answer"))
            if takes_inbound or returns_a_send:
                suspects.append(name)
        self.assertEqual(suspects, [],
                         "an LLM entry point looks like it drafts a response "
                         "to a prospect")

    def test_classification_is_the_only_thing_done_to_a_reply(self):
        """`replies` classifies. It must not compose."""
        from src import replies
        composers = [n for n, f in vars(replies).items()
                     if callable(f) and hasattr(f, "__code__")
                     and any(w in n.lower() for w in
                             ("draft", "compose", "write", "respond", "send"))]
        self.assertEqual(composers, [])


class TheInboundPathWritesStateAndNothingElse(unittest.TestCase):

    def test_ingest_returns_no_text_to_send(self):
        """Whatever `handle` produces, it is not a message.

        Asserted on the RETURN of the real function rather than on its source,
        so a rewrite that started composing would fail here.
        """
        rec = {"id": "acme", "client": "productive", "domain": "acme.test",
               "contacts": [{"key": "dana", "email": "dana@acme.test"}],
               "events": [], "log": []}
        event = {"type": "reply_received", "email": "dana@acme.test",
                 "at": "2026-09-10T12:00:00+00:00", "text": "not interested"}
        out = inbound.handle(event, [rec])
        blob = repr(out).lower()
        for word in ("dear", "hi ", "thanks for", "best regards", "reply:"):
            self.assertNotIn(word, blob)

    def test_the_tag_outbox_refuses_to_send_at_all(self):
        """`tagsync` is the one thing that talks to a provider on this path,
        and it changes labels rather than saying anything."""
        with self.assertRaises(Exception):
            tagsync.send({"kind": "tag"}, live=True)


class NoSourceFileComposesAResponse(unittest.TestCase):
    """A source scan, for the case the structural tests cannot reach.

    Deliberately last and deliberately narrow: it looks for a FUNCTION whose
    name says it answers a prospect, not for the word "reply", which appears
    hundreds of times in code that correctly reads them.
    """

    PATTERN = re.compile(
        r"^\s*def\s+(\w*(?:send|write|compose|draft)_?reply\w*"
        r"|\w*reply_?(?:text|body|message|draft)\w*"
        r"|auto_?respond\w*)\s*\(", re.MULTILINE)

    def test_no_function_answers_a_prospect(self):
        found = []
        for base, dirs, names in os.walk(os.path.join(ROOT, "src")):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(base, name)
                text = open(path, encoding="utf-8").read()
                for match in self.PATTERN.finditer(text):
                    found.append(f"{name}:{match.group(1)}")
        self.assertEqual(found, [],
                         "a function that composes a reply to a prospect now "
                         "exists; it needs its own authorisation, not this "
                         "test relaxed")


if __name__ == "__main__":
    unittest.main()
