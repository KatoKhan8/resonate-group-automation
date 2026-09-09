#!/usr/bin/env python3
"""A cadence with the complexity a real Resonate sequence has.

Thirty-eight nodes. Not thirty-eight to reach a number - each one is there
because a plausible account-based sequence needs it:

    Anna      email      the primary decision maker's opener and follow-ups
    Petar     LinkedIn   connection, then messages once accepted
    Mark      email      a second human, later, to the secondary DM
    Sara      LinkedIn   a second profile, taking over when Petar stalls

Six phases, eleven branches, two decision makers activated conditionally, a
referral branch, and a re-engagement arm that runs a month after everything
else has gone quiet.

What it demonstrates that a linear list cannot:

  * one contact touched by two email humans and two LinkedIn humans
  * a second LinkedIn profile taking over when the first gets no acceptance
  * a secondary decision maker activated only on a condition
  * a referral branch that activates a third
  * a positive reply stopping the whole thing
  * a re-engagement arm a month later, from a different sender

Nothing here is client copy. The templates are named, not written: a cadence
is a shape, and the words belong to the workspace.
"""
from .. import cadencegraph as cg

# The four humans. Passed in rather than hardcoded so the same shape works
# for any workspace's roster.
DEFAULTS = {"email_sender": "anna", "second_email": "mark",
            "linkedin_sender": "petar", "second_linkedin": "sara_s"}


def build(email_sender=None, second_email=None, linkedin_sender=None,
          second_linkedin=None):
    """The graph. Every node named for what it does, not for its number."""
    anna = email_sender or DEFAULTS["email_sender"]
    mark = second_email or DEFAULTS["second_email"]
    petar = linkedin_sender or DEFAULTS["linkedin_sender"]
    sara = second_linkedin or DEFAULTS["second_linkedin"]
    P = cg.PRIMARY_ROLE
    S = cg.SECONDARY_ROLE
    R = cg.REFERRAL_ROLE

    n = cg.node
    nodes = [
        # --- Initial outreach: Anna opens on email.
        n("open", "email", day=1, sender_id=anna, contact_role=P,
          template="opener", phase=cg.OPENING),
        n("w1", "wait", wait_days=2, phase=cg.OPENING),
        n("replied1", "branch", condition="replied", phase=cg.OPENING),
        n("stop_early", "stop", label="They answered", phase=cg.OPENING),

        # --- LinkedIn connection: Petar requests, then we check.
        n("connect", "connection_request", day=3, sender_id=petar,
          contact_role=P, phase=cg.CONNECTING),
        n("w2", "wait", wait_days=3, phase=cg.CONNECTING),
        n("check1", "connection_check", day=6, sender_id=petar,
          contact_role=P, phase=cg.CONNECTING),
        n("accepted1", "branch", condition="connection_accepted",
          phase=cg.CONNECTING),
        n("li_intro", "linkedin_message", day=6, sender_id=petar,
          contact_role=P, template="linkedin_intro", phase=cg.CONNECTING),

        # --- Multichannel follow-up: Anna again, then Petar again.
        n("email2", "email", day=8, sender_id=anna, contact_role=P,
          template="persona_pain", phase=cg.FOLLOW_UP),
        n("w3", "wait", wait_days=3, phase=cg.FOLLOW_UP),
        n("replied2", "branch", condition="replied", phase=cg.FOLLOW_UP),
        n("stop2", "stop", label="They answered", phase=cg.FOLLOW_UP),
        n("li_follow", "linkedin_followup", day=11, sender_id=petar,
          contact_role=P, template="linkedin_followup", phase=cg.FOLLOW_UP),
        n("w4", "wait", wait_days=4, phase=cg.FOLLOW_UP),
        n("email3", "email", day=15, sender_id=anna, contact_role=P,
          template="comparable_proof", phase=cg.FOLLOW_UP),

        # --- Second sender: Sara's profile takes over where Petar stalled.
        n("w5", "wait", wait_days=3, phase=cg.SECOND_SENDER),
        n("accepted2", "branch", condition="connection_pending",
          phase=cg.SECOND_SENDER),
        n("sara_connect", "connection_request", day=18, sender_id=sara,
          contact_role=P, phase=cg.SECOND_SENDER),
        n("w6", "wait", wait_days=3, phase=cg.SECOND_SENDER),
        n("sara_msg", "linkedin_message", day=21, sender_id=sara,
          contact_role=P, template="linkedin_intro",
          phase=cg.SECOND_SENDER),
        n("handoff", "handoff", label="Carry the email thread across",
          phase=cg.SECOND_SENDER),

        # --- Secondary DM: Mark opens on the CEO, but only if the COO has
        #     gone quiet. Approaching both at once is the thing account
        #     pacing exists to stop.
        n("quiet", "branch", condition="no_reply", phase=cg.SECONDARY_DM),
        n("sec_open", "email", day=20, sender_id=mark, contact_role=S,
          template="opener", phase=cg.SECONDARY_DM),
        n("w7", "wait", wait_days=3, phase=cg.SECONDARY_DM),
        n("sec_connect", "connection_request", day=23, sender_id=sara,
          contact_role=S, phase=cg.SECONDARY_DM),
        n("sec_replied", "branch", condition="replied",
          phase=cg.SECONDARY_DM),
        n("sec_stop", "stop", label="Secondary answered",
          phase=cg.SECONDARY_DM),
        n("sec_follow", "email", day=27, sender_id=mark, contact_role=S,
          template="persona_pain", phase=cg.SECONDARY_DM),

        # --- Referral: somebody named somebody else. Activate them.
        n("referred", "branch", condition="referral_received",
          phase=cg.SECONDARY_DM),
        n("ref_activate", "dm_handoff", label="Activate the referred contact",
          phase=cg.SECONDARY_DM),
        n("ref_open", "email", day=25, sender_id=anna, contact_role=R,
          template="opener", phase=cg.SECONDARY_DM),

        # --- Re-engagement: a month of silence, then one more from Mark.
        n("w8", "wait", wait_days=30, phase=cg.REENGAGEMENT),
        n("still_quiet", "branch", condition="no_reply",
          phase=cg.REENGAGEMENT),
        n("reengage", "reengage", label="Restart from a different sender",
          phase=cg.REENGAGEMENT),
        n("re_email", "email", day=60, sender_id=mark, contact_role=P,
          template="opener", phase=cg.REENGAGEMENT),
        n("w9", "wait", wait_days=7, phase=cg.REENGAGEMENT),
        n("breakup", "email", day=67, sender_id=mark, contact_role=P,
          template="breakup", phase=cg.CLOSING),
        n("done", "stop", label="Sequence complete", phase=cg.CLOSING),
    ]

    g = cg.graph("Account-based multichannel, two humans per channel", nodes,
                 "open")
    edge = cg.connect
    edge(g, "open", "w1")
    edge(g, "w1", "replied1")
    edge(g, "replied1", "stop_early", cg.TRUE_BRANCH)
    edge(g, "replied1", "connect", cg.FALSE_BRANCH)
    edge(g, "connect", "w2")
    edge(g, "w2", "check1")
    edge(g, "check1", "accepted1")
    edge(g, "accepted1", "li_intro", cg.TRUE_BRANCH)
    edge(g, "accepted1", "email2", cg.FALSE_BRANCH)
    edge(g, "li_intro", "email2")
    edge(g, "email2", "w3")
    edge(g, "w3", "replied2")
    edge(g, "replied2", "stop2", cg.TRUE_BRANCH)
    edge(g, "replied2", "li_follow", cg.FALSE_BRANCH)
    edge(g, "li_follow", "w4")
    edge(g, "w4", "email3")
    edge(g, "email3", "w5")
    edge(g, "w5", "accepted2")
    edge(g, "accepted2", "sara_connect", cg.TRUE_BRANCH)
    edge(g, "accepted2", "quiet", cg.FALSE_BRANCH)
    edge(g, "sara_connect", "w6")
    edge(g, "w6", "sara_msg")
    edge(g, "sara_msg", "handoff")
    edge(g, "handoff", "quiet")
    edge(g, "quiet", "sec_open", cg.TRUE_BRANCH)
    edge(g, "quiet", "w8", cg.FALSE_BRANCH)
    edge(g, "sec_open", "w7")
    edge(g, "w7", "sec_connect")
    edge(g, "sec_connect", "sec_replied")
    edge(g, "sec_replied", "sec_stop", cg.TRUE_BRANCH)
    edge(g, "sec_replied", "sec_follow", cg.FALSE_BRANCH)
    edge(g, "sec_follow", "referred")
    edge(g, "referred", "ref_activate", cg.TRUE_BRANCH)
    edge(g, "referred", "w8", cg.FALSE_BRANCH)
    edge(g, "ref_activate", "ref_open")
    edge(g, "ref_open", "w8")
    edge(g, "w8", "still_quiet")
    edge(g, "still_quiet", "reengage", cg.TRUE_BRANCH)
    edge(g, "still_quiet", "done", cg.FALSE_BRANCH)
    edge(g, "reengage", "re_email")
    edge(g, "re_email", "w9")
    edge(g, "w9", "breakup")
    edge(g, "breakup", "done")
    return g
