#!/usr/bin/env python3
"""Break each safety rule on purpose, and check that a test notices.

A green suite is evidence of nothing until you have watched it go red for the
right reason. This removes one guard at a time, runs the tests that should
care, restores the file, and reports anything that got through.

It is not part of the normal run: it executes the suite once per mutation and
takes a few minutes. Run it after changing a safety rule, or before believing
a claim about one.

  py tools/mutation_audit.py
  py tools/mutation_audit.py --only mx

Nothing is committed. Every file is restored in a finally, and the bytecode
caches are dropped on both sides of each mutation - see drop_bytecode().
"""
import argparse
import io
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (name, file, the guard, the removal, the tests that should catch it)
MUTATIONS = [
    # ---------------------------------------------- pilot hardening

    ('contextpack: describe a planned touch as something that happened',
     'src/contextpack.py',
     '    if not row.get("confirmed") or row.get("state") not in touch.CONFIRMED_STATES:',
     '    if False:',
     'tests.test_context_history'),

    ('contextpack: check the flag and not the state',
     'src/contextpack.py',
     '    if not row.get("confirmed") or row.get("state") not in touch.CONFIRMED_STATES:',
     '    if not row.get("confirmed"):',
     'tests.test_context_history'),

    ('contextpack: name the currently assigned sender as the one who wrote',
     'src/contextpack.py',
     '    for row in found["confirmed_touches"]:',
     '    for row in found["touches"]:',
     'tests.test_context_history'),

    ('killswitch: treat a workspace nobody switched on as switched on',
     'src/killswitch.py',
     '    if value is None:\n        return _verdict(WORKSPACE, False,',
     '    if value is None:\n        return _verdict(WORKSPACE, True,',
     'tests.test_killswitch'),

    ('killswitch: let the global refusal permit sending',
     'src/killswitch.py',
     '        GLOBAL, not refuses,',
     '        GLOBAL, True,',
     'tests.test_killswitch'),

    ('killswitch: report only the outermost refusal',
     'src/killswitch.py',
     '    blocking = [row for row in layers if not row["sending"]]',
     '    blocking = [row for row in layers if not row["sending"]][:1]\n    layers = layers[:1]',
     'tests.test_killswitch'),

    ('killswitch: treat a campaign that is merely launch-ready as running',
     'src/killswitch.py',
     '    return _verdict(CAMPAIGN, status == campaigns.RUNNING,',
     '    return _verdict(CAMPAIGN, status in (campaigns.RUNNING,\n                                         campaigns.LAUNCH_READY),',
     'tests.test_killswitch'),

    ('pilotcaps: let a configuration raise a pilot ceiling',
     'src/pilotcaps.py',
     '        elif want <= ceiling:\n            value, source = want, "configured"\n        else:\n            value, source = ceiling, "ceiling"',
     '        else:\n            value, source = want, "configured"',
     'tests.test_pilotcaps'),

    ('pilotcaps: default pilot mode to off',
     'src/pilotcaps.py',
     '    if value is None:\n        return True',
     '    if value is None:\n        return False',
     'tests.test_pilotcaps'),

    ('pilotcaps: trim a plan that exceeds a cap instead of refusing it',
     'src/pilotcaps.py',
     '        if asked is not None and asked > row["limit"]:',
     '        if False:',
     'tests.test_pilotcaps'),

    ('push: send a message without recording which copy it carried',
     'src/push.py',
     '                  variant_id=carried.get("variant_id") or None,',
     '                  variant_id=None,',
     'tests.test_variant_attribution'),

    ('push: label a sent message with the copy the record holds now',
     'src/push.py',
     '    carried = sent if sent is not None else step',
     '    carried = step',
     'tests.test_variant_attribution'),

    ('variants: count a planned touch as an exposure',
     'src/variants.py',
     '    for touch in account.touches(rec, contact_key, confirmed_only=True):',
     '    for touch in account.touches(rec, contact_key):',
     'tests.test_variant_attribution'),

    ('revival: re-read the signal file once per account',
     'src/revival.py',
     '    if signal_index is None:\n        signal_index = signal_module.index(',
     '    if False:\n        signal_index = signal_module.index(',
     'tests.test_signals'),

    # The revival guard is registered once, in the revival section below.
    # It was here as well, byte for byte, so the audit ran it twice and the
    # headline count was one higher than the number of guards checked.

    ('upload: store an unbounded company name from an untrusted file',
     'src/web/upload.py',
     '        company = company[:MAX_CELL]\n',
     '',
     'tests.test_import_contacts'),

    # -------------------------------------------------------- terminal steps

    ('push: send a step the provider already confirmed',
     'src/push.py',
     '    return stepstate.is_terminal(\n        stored_step(rec, contact_key, step_key).get("status"))',
     '    return stored_step(rec, contact_key, step_key).get("status") == "pushed"',
     'tests.test_eligibility'),

    ('push: treat every state that has a name as final',
     'src/push.py',
     '    return stepstate.is_terminal(\n        stored_step(rec, contact_key, step_key).get("status"))',
     '    return bool(stored_step(rec, contact_key, step_key).get("status"))',
     'tests.test_eligibility'),

    ('cadence: let a rebuild move a step the provider confirmed',
     'src/cadence.py',
     '    if stepstate.is_terminal(stored.get("status")):\n        return stored["status"]              # already sent, never sent again',
     '    if stored.get("status") == "pushed":\n        return "pushed"                      # already sent, never sent again',
     'tests.test_eligibility'),

    # ---------------------------------------------------------------- ageing
    #
    # `evidence.make` scores a fact on the day it is found and freezes the
    # answer. These are the guards that stop that frozen number being read
    # months later as though it described today.

    ("evidence: let a fact past the maximum age still be written from",
     "src/evidence.py",
     "    if freshness_bucket == BACKGROUND:\n        return WEAK",
     "    if False and freshness_bucket == BACKGROUND:\n        return WEAK",
     "tests.test_evidence_ageing"),

    ("evidence: read the stored freshness instead of re-deriving it",
     "src/evidence.py",
     "    return [e for e in rank(reaged(items, today, policy))\n"
     '            if e.get("quality") in USABLE]',
     "    return [e for e in rank(items)\n"
     '            if e.get("quality") in USABLE]',
     "tests.test_evidence_ageing"),

    ("personalization: hand back evidence scored on the day it was found",
     "src/personalization.py",
     "        out.append(evidence.recheck(entry, today))",
     "        out.append(entry)",
     "tests.test_evidence_ageing"),

    ("eligibility: send a draft whose evidence has aged out",
     "src/eligibility.py",
     "    return not evidence.usable(rows, today)",
     "    return False",
     "tests.test_evidence_ageing"),

    ("eligibility: hold every fallback draft in the estate",
     "src/eligibility.py",
     "    if not ids:\n        return False",
     "    if not ids:\n        return True",
     "tests.test_evidence_ageing"),

    # --------------------------------------------------------------- refresh

    ("refresh: buy person credits before an ICP verdict exists",
     "src/refresh.py",
     "        blocked = (None if accepted or kind not in PERSON_LEVEL",
     "        blocked = (None if True or accepted or kind not in PERSON_LEVEL",
     "tests.test_refresh"),

    ("refresh: read the ICP verdict one level above where it lives",
     "src/refresh.py",
     '    return verdict.get("icp_status") == icp.QUALIFIED',
     '    return ((rec.get("qualification") or {}).get("verdict")\n'
     "            == icp.QUALIFIED)",
     "tests.test_refresh"),

    ("refresh: spend credits on an account below the priority floor",
     "src/refresh.py",
     '                free = [k for k in row["due"] if not k["credits"]]',
     '                free = list(row["due"])',
     "tests.test_refresh"),

    ("refresh: refuse the free work an account below the floor still needs",
     "src/refresh.py",
     '                free = [k for k in row["due"] if not k["credits"]]',
     "                free = []",
     "tests.test_refresh"),

    ("refresh: describe a sample of the estate as the whole answer",
     "src/refresh.py",
     '"capped_scan": len(due) > len(scanned),',
     '"capped_scan": False,',
     "tests.test_refresh"),

    # --------------------------------------------------------------- revival

    ("revival: re-approach an account that asked us to stop",
     "src/revival.py",
     "    closed = _closing_outcome(rec)\n    if closed:",
     "    closed = _closing_outcome(rec)\n    if False:",
     "tests.test_revival"),

    ("revival: count our own outreach as news from the account",
     "src/revival.py",
     "        if signal_module.SCOPE_OF.get(signal.get(\"type\")) == \\\n"
     "                signal_module.ENGAGEMENT:\n            continue",
     "        if False:\n            continue",
     "tests.test_revival"),

    ("revival: treat a signal we already knew as something new",
     "src/revival.py",
     "        if since and str(at) <= str(since):\n            continue",
     "        if False:\n            continue",
     "tests.test_revival"),

    ("revival: start the cooling clock at a payload that never left",
     "src/revival.py",
     "    confirmed = account.touches(rec, confirmed_only=True)",
     "    confirmed = account.touches(rec)",
     "tests.test_revival"),

    ("revival: revive an account with nothing new to say to it",
     "src/revival.py",
     "    if not cases:\n        return verdict(NOTHING_NEW,",
     "    if False:\n        return verdict(NOTHING_NEW,",
     "tests.test_revival"),

    # ---------------------------------------------------------- observations

    ("observations: state a fact we cannot point at",
     "src/observations.py",
     '    return bool((row.get("source_url") or "").strip())',
     "    return True",
     "tests.test_observations"),

    ("observations: write from evidence that is not good enough",
     "src/observations.py",
     '    usable = [r for r in citable if r.get("quality") in evidence.USABLE]',
     "    usable = list(citable)",
     "tests.test_observations"),

    ("observations: phrase a company fact as a fact about the person",
     "src/observations.py",
     "    subject = SUBJECT_OF[observation_type]",
     "    subject = None",
     "tests.test_observations"),

    ("observations: call an old fact news",
     "src/observations.py",
     '                may_call_it_now=bool(current and best.get("published_at")),',
     "                may_call_it_now=True,",
     "tests.test_observations"),

    ("observations: ignore the campaign switch",
     "src/observations.py",
     "    if not on:\n        return _no(observation_type,",
     "    if False:\n        return _no(observation_type,",
     "tests.test_observations"),

    # ------------------------------------------------------------ web layer

    ("app: tell a forged Slack payload which check refused it",
     "src/web/app.py",
     'raise Handled(HTTPStatus.UNAUTHORIZED, "unauthorised",',
     "raise Handled(HTTPStatus.UNAUTHORIZED, reason,",
     "tests.test_slack_route"),

    ("app: answer a forged Slack payload with 200",
     "src/web/app.py",
     'raise Handled(HTTPStatus.UNAUTHORIZED, "unauthorised",',
     'raise Handled(HTTPStatus.OK, "unauthorised",',
     "tests.test_slack_route"),

    # Deliberately absent: the Slack over-long-body drain
    # (`remaining = min(length, SLACK_DRAIN_LIMIT)` in `_slack_interaction`).
    #
    # The guard is real and `tests.test_slack_route` covers it - the bug it
    # was written for was found by that test and posts four times because
    # the failure was intermittent. It is not in this list because removing
    # it is caught about three runs in five: whether the client sees the
    # 413 or a connection reset depends on socket buffering, and no
    # assertion available here decides it.
    #
    # An entry that reports MISSED on a working guard two runs in five is
    # worse than no entry. It teaches whoever reads this tool to skim past
    # a red line, which is the one thing it cannot afford.

    ("api: let a viewer read what the agency is failing at",
     "src/web/api.py",
     "    repo.require(ws.OPERATIONS_VIEW)\n"
     "    rows = revival_module.candidates(repo.records(), today=today,",
     "    rows = revival_module.candidates(repo.records(), today=today,",
     "tests.test_revival_screen"),

    ("api: aggregate the whole estate into one workspace's refresh plan",
     "src/web/api.py",
     "    return refresh_module.plan(repo.records(), today=today,",
     "    from .. import store as _store\n"
     "    return refresh_module.plan(_store.load(), today=today,",
     "tests.test_tenancy_penetration"),

    ("api: count another tenant's accounts as quiet in this one",
     "src/web/api.py",
     "    rows = revival_module.candidates(repo.records(), today=today,",
     "    from .. import store as _store\n"
     "    rows = revival_module.candidates(_store.load(), today=today,",
     "tests.test_tenancy_penetration"),

    ("api: report a workspace as healthy on another tenant's failures",
     "src/web/api.py",
     "    for row in tagsync.load().values():\n"
     "        if row.get(\"workspace\") != repo.workspace:\n            continue",
     "    for row in tagsync.load().values():\n"
     "        if False:\n            continue",
     "tests.test_request_scale"),

    ("api: say a health screen is clean when it is not",
     "src/web/api.py",
     '"clean": not rows,',
     '"clean": True,',
     "tests.test_request_scale"),

    ("mx: let a blocked gateway through",
     "src/mx.py",
     '    if key in GATEWAYS and key in (policy.get("blocked_providers") or ()):',
     '    if False and key in (policy.get("blocked_providers") or ()):',
     "tests.test_mx tests.test_mx_policy"),

    ("mx: treat Microsoft as a gateway",
     "src/mx.py",
     '    "microsoft": {\n        "name": "Microsoft 365",',
     '    "microsoft_moved": {\n        "name": "Microsoft 365",',
     "tests.test_mx tests.test_mx_policy"),

    ("channels: drop a contact instead of holding it",
     "src/channels.py",
     '        "held": mode == NONE,',
     '        "held": False,',
     "tests.test_channels"),

    ("channels: trust the stored verdict",
     "src/channels.py",
     "    allowed, _ = mx.allows_email(contact, config)",
     "    allowed = contact.get('email_eligible', True)",
     "tests.test_channels"),

    ("waterfall: allow a fallback with no reason",
     "src/waterfall.py",
     '        return False, "a paid fallback needs a reason; this one offered none"',
     '        return True, "allowed"',
     "tests.test_waterfall"),

    ("quality: let a good score rescue no specificity",
     "src/quality.py",
     "    if company <= 0.0:\n        return LOW",
     "    if False:\n        return LOW",
     "tests.test_quality"),

    ("lint: stop linting LinkedIn copy",
     "src/lint.py",
     '    if (step or {}).get("channel") == "linkedin":\n        return check_linkedin(rec, key, step)',
     '    if False:\n        return check_linkedin(rec, key, step)',
     "tests.test_linkedin_lint tests.test_simulator"),

    ("lint: raise the note limit past LinkedIn's own",
     "src/lint.py",
     "NOTE_MAX_CHARS = 300",
     "NOTE_MAX_CHARS = 3000",
     "tests.test_linkedin_lint"),

    ("export: stop guarding formulas",
     "src/export.py",
     "    if is_dangerous(text):\n        return GUARD + text",
     "    if False:\n        return GUARD + text",
     "tests.test_resilience tests.test_simulator"),

    ("simulator: claim it would send something",
     "src/simulator.py",
     '        "would_send": 0,',
     '        "would_send": 1,',
     "tests.test_simulator"),

    ("previewpage: stop masking addresses",
     "src/previewpage.py",
     "    if reveal:\n        return address",
     "    if True:\n        return address",
     "tests.test_simulator tests.test_minimization tests.test_preview_cli"),

    # Suppressing the note entirely rather than rewording it: a mutation that
    # only changes wording tests the test's string matching instead of the
    # behaviour, which is the failure mode this whole file exists to avoid.
    ("previewpage: silently truncate instead of saying so",
     "src/previewpage.py",
     "    omitted = total - shown",
     "    omitted = 0",
     "tests.test_simulator"),

    ("replaysim: claim suppression without observing it",
     "src/replaysim.py",
     '        "suppression_evidence": ("observed" if suppressed',
     '        "suppression_evidence": ("observed" if True',
     "tests.test_replaysim"),

    ("providers: stop redacting free text",
     "src/providers/__init__.py",
     "    return _redact_headers(text)",
     "    return text",
     "tests.test_minimization tests.test_secrets"),

    ("generate: read the stored flag instead of the resolver",
     "src/generate.py",
     '    sendable = [c for c in rec.get("contacts") or [] if lint.sendable(c)]',
     '    sendable = [c for c in rec.get("contacts") or [] if c.get("sendable")]',
     "tests.test_failure_injection"),

    # ------------------------------- the reply policy and what it moves
    #
    # These guard the transition layer wired in when the policy stopped
    # being advisory. Each is a way the engine could quietly get permissive:
    # a suppression that does not reach, uncertainty that narrows, a
    # classifier that lifts a hold.

    # The preceding line is in the anchor because `contacts_of(rec)` is
    # walked twice in this file - here, and in the referral lookup below
    # it. Without it this entry mutated whichever came first in the file,
    # which was the right one by ordering alone.
    ("accountpolicy: let a company-wide do-not-contact miss the contacts",
     "src/accountpolicy.py",
     '    rec["suppression"] = suppression\n'
     "    for contact in account.contacts_of(rec):",
     '    rec["suppression"] = suppression\n'
     "    for contact in []:",
     "tests.test_reply_transitions"),

    ("accountpolicy: let an unclassified reply resolve to carry on",
     "src/accountpolicy.py",
     '            "action": REVIEW,',
     '            "action": CONTINUE,',
     "tests.test_reply_transitions tests.test_account_policy"),

    ("accountpolicy: scope an unclassified reply to the replier only",
     "src/accountpolicy.py",
     '            "scope": ACCOUNT,',
     '            "scope": CONTACT,',
     "tests.test_reply_transitions"),

    ("accountpolicy: let a stopped sequence count as a removal request",
     "src/accountpolicy.py",
     "    if replier == STOP and outcome in REMOVAL_REQUESTS:",
     "    if replier == STOP or True:",
     "tests.test_reply_transitions"),

    ("accountpolicy: let a second reply rewrite an existing suppression",
     "src/accountpolicy.py",
     '    if suppression.get("unsubscribed"):\n        return False',
     "    if False:\n        return False",
     "tests.test_reply_transitions"),

    ("accountpolicy: activate a referred contact nobody authorised",
     "src/accountpolicy.py",
     '    if plan["activate_referred"]:',
     "    if True:",
     "tests.test_reply_transitions"),

    ("eligibility: stop honouring an account suppression",
     "src/eligibility.py",
     '    if (rec.get("suppression") or {}).get("unsubscribed"):\n        return BLOCKED_ACCOUNT_SUPPRESSED',
     "    if False:\n        return BLOCKED_ACCOUNT_SUPPRESSED",
     "tests.test_reply_transitions"),

    ("eligibility: let a suppressed contact through",
     "src/eligibility.py",
     '    if contact.get("unsubscribed") or contact.get("suppressed"):\n        return BLOCKED_UNSUBSCRIBED',
     "    if False:\n        return BLOCKED_UNSUBSCRIBED",
     "tests.test_reply_transitions tests.test_eligibility"),

    # ------------------- new-list hygiene and provider tagging
    #
    # Each is a way a previously engaged person quietly becomes a
    # fresh cold prospect again, or a way our conclusion about one
    # person gets written onto another.

    ('hygiene: let an account suppression stop reaching new contacts',
     'src/hygiene.py',
     '    if entry["account_state"] == ap.SUPPRESS:',
     '    if False:',
     'tests.test_hygiene'),

    ('hygiene: call every prior engagement fresh',
     'src/hygiene.py',
     '    verdict = worst(verdicts) if verdicts else FRESH',
     '    verdict = FRESH',
     'tests.test_hygiene tests.test_hygiene_lifecycle'),

    ('hygiene: let the mildest verdict win, not the most conservative',
     'src/hygiene.py',
     '    return min(found, key=lambda v: order[v]) if found else FRESH',
     '    return max(found, key=lambda v: order[v]) if found else FRESH',
     'tests.test_hygiene'),

    ('agencydnc: store the plaintext identifier instead of a hash',
     'src/agencydnc.py',
     '    return hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()',
     '    return str(value)',
     'tests.test_hygiene'),

    ('tagsync: queue a fresh operation for an unchanged desired state',
     'src/tagsync.py',
     '            continue                    # already queued, unchanged',
     '            pass                        # already queued, unchanged',
     'tests.test_tagsync'),

    ('tagsync: allow a live provider mutation',
     'src/tagsync.py',
     '    raise TagSyncRefused(',
     '    return TagSyncRefused(',
     'tests.test_tagsync'),

    # ---------------------------- copy experiments
    #
    # Each is a way the optimiser could quietly start lying: a
    # rosette on noise, a rewritten history, or four of five
    # variants checked.

    ('variants: declare a winner before the checkpoint',
     'src/variants.py',
     '    if progress is not None and progress < rules["first_checkpoint"]:',
     '    if False:',
     'tests.test_variants'),

    ('variants: declare a winner from a tiny sample',
     'src/variants.py',
     '    if smallest < rules["minimum_per_variant"] or \\',
     '    if False:',
     'tests.test_variants'),

    ('variants: call a leader a winner despite overlapping ranges',
     'src/variants.py',
     '    if leader["low"] > best_other and (',
     '    if True or (',
     'tests.test_variants'),

    ('variants: let a later allocation rewrite a recorded assignment',
     'src/variants.py',
     '    if recorded and recorded in entries:',
     '    if False:',
     'tests.test_variants'),

    ('variants: assign at random instead of deterministically',
     'src/variants.py',
     '    material = f"{campaign_id}|{step_key}|{contact_key}|{version}"',
     '    material = str(id(contact_key))',
     'tests.test_variants'),

    ('variants: give the winner every remaining send',
     'src/variants.py',
     '    winner_share = float(rules["winner_share"])',
     '    winner_share = 1.0',
     'tests.test_variants'),

    ('campaignqa: check only the first variant of a step',
     'src/campaignqa.py',
     '        for entry in entries:',
     '        for entry in entries[:1]:',
     'tests.test_campaign_qa'),

    ('variants: count a planned touch as an exposure',
     'src/variants.py',
     '    for touch in account.touches(rec, contact_key, confirmed_only=True):',
     '    for touch in account.touches(rec, contact_key):',
     'tests.test_variants'),

    # ------------------------- account intelligence
    #
    # Each is a way the intelligence layer could start asserting
    # more than it knows: a signal without evidence, a removal
    # request that fades, or a score that grants permission.

    ('signals: let a signal exist without evidence',
     'src/signals.py',
     '    if not evidence:',
     '    if False:',
     'tests.test_signals'),

    ('signals: let a removal request decay like anything else',
     'src/signals.py',
     '    if life is None:',
     '    if False:',
     'tests.test_signals'),

    ('signals: treat an undated signal as fresh',
     'src/signals.py',
     '    if age is None:',
     '    if False:',
     'tests.test_signals'),

    ('signals: let stale signals keep contributing',
     'src/signals.py',
     '    contributing = [r for r in rows if r["freshness"] != STALE]',
     '    contributing = rows',
     'tests.test_signals'),

    ('signals: store a first-party signal instead of deriving it',
     'src/signals.py',
     '    if entry.get("source") == FIRST_PARTY:',
     '    if False:',
     'tests.test_signals'),

    ('priority: let a suppressed account read as eligible',
     'src/priority.py',
     '    if account_state == ap.SUPPRESS:',
     '    if False:',
     'tests.test_signals'),

    ('priority: read the ICP verdict from the wrong place',
     'src/priority.py',
     '    verdict = ((rec.get("qualification") or {}).get("verdict") or {})',
     '    verdict = (rec.get("icp") or {})',
     'tests.test_signals'),

    # ------------------------- signals a person enters by hand
    #
    # Two doors onto the same rule - engagement is read from the event
    # log, never handwritten - plus the permission that was missing from
    # the upload POST while the GET carried it.

    ("signals: let a person hand-enter an engagement signal",
     "src/signals.py",
     '    if SCOPE_OF.get(entry.get("type")) == ENGAGEMENT:',
     "    if False:",
     "tests.test_signals"),

    ("signals: offer engagement types on the entry form",
     "src/signals.py",
     "    return tuple(t for t in TYPES if SCOPE_OF[t] != ENGAGEMENT)",
     "    return TYPES",
     "tests.test_signals"),

    ("app: let a viewer parse a CSV through the upload POST",
     "src/web/app.py",
     "            security.require(session, workspaces.BATCH_CREATE)\n            data = files.get(\"csv\")",
     '            data = files.get("csv")',
     "tests.test_web_security tests.test_web_invariants"),

    # ------------------------- the campaign brief
    #
    # The pack asserts nothing of its own, so each of these is a way
    # it could start: merging a guess with evidence, reporting a
    # priority without reporting what cannot be worked, or counting
    # our own outreach as something happening at the company.

    ('priority: count our own outreach as something happening at them',
     'src/priority.py',
     '    strength = signal_module.strength(external, now, config)',
     '    strength = signal_module.strength(found, now, config)',
     'tests.test_signals'),

    ('contextpack: merge an unsupported angle into the supported ones',
     'src/contextpack.py',
     '    unsupported_anywhere = [row for row in guessed\n                            if row["pain"] not in supported]',
     '    unsupported_anywhere = []',
     'tests.test_contextpack'),

    ('contextpack: report priority without what cannot be worked',
     'src/contextpack.py',
     '        if not found["eligibility"]["eligible"]:',
     '        if False:',
     'tests.test_contextpack'),

    ('contextpack: list our own touches as things happening at them',
     'src/contextpack.py',
     '    external = [r for r in rows if r["scope"] != signals_module.ENGAGEMENT]',
     '    external = rows',
     'tests.test_contextpack'),

    # ------------------------- gtm decision memory
    #
    # The log is only worth having if it is honest about itself: a
    # decision that looks evidenced because the field was mandatory
    # is worse than one admitting it was a hunch, and a superseded
    # row that can be rewritten is a configuration file with worse
    # ergonomics.

    ('gtm: let a measured decision skip saying what was measured',
     'src/gtm.py',
     '    if basis in CHECKABLE and not (evidence or "").strip():',
     '    if False:',
     'tests.test_gtm'),

    ('gtm: accept a decision with no reason recorded',
     'src/gtm.py',
     '    if len(why) < MINIMUM_WHY:',
     '    if False:',
     'tests.test_gtm'),

    ('gtm: let a superseded decision be superseded again',
     'src/gtm.py',
     '    if found.get("superseded_by"):',
     '    if False:',
     'tests.test_gtm'),

    ("gtm: let one workspace supersede another's decision",
     'src/gtm.py',
     '        if row["id"] == old_id and row.get("workspace") == workspace:',
     '        if row["id"] == old_id:',
     'tests.test_gtm'),

    ('api: let an operator record a GTM decision',
     'src/web/api.py',
     '    repo.require(ws.WORKSPACE_MANAGE)\n\n    if policy_key and policy_key not in ws.POLICY_KEYS:',
     '    if policy_key and policy_key not in ws.POLICY_KEYS:',
     'tests.test_gtm'),

    ("priority: re-read the signal file for every account",
     'src/priority.py',
     '    found += (list((signal_index or {}).get(rec.get("id")) or [])\n              if signal_index is not None\n              else signal_module.for_record(rec.get("id"), workspace))',
     '    found += signal_module.for_record(rec.get("id"), workspace)',
     'tests.test_signals'),

    # ------------------------- playbooks
    #
    # A recommendation whose weak points are hidden is one nobody can
    # disagree with, which makes it an instruction. Each of these is a
    # way it could start hiding them.

    ('playbooks: treat an unknown attribute as a match',
     'src/playbooks.py',
     '        return False, f"{CONDITION_LABEL[condition]} not established", False',
     '        return True, "unknown", True',
     'tests.test_playbooks'),

    ('playbooks: let a stale signal choose an approach',
     'src/playbooks.py',
     '                if s["freshness"] != signal_module.STALE\n                and s["scope"] != signal_module.ENGAGEMENT]',
     '                ]',
     'tests.test_playbooks'),

    ('playbooks: recommend the best match however poorly it fits',
     'src/playbooks.py',
     '    fits = [row for row in scored\n            if row["eligible"] and row["score"] >= CONFIDENCE_FLOOR]',
     '    fits = list(scored)',
     'tests.test_playbooks'),

    ('playbooks: mix the fallback into the ranking',
     'src/playbooks.py',
     '    scored = [evaluate(play, rec, assessment) for play in LIBRARY\n              if play["id"] != "segment_default"]',
     '    scored = [evaluate(play, rec, assessment) for play in LIBRARY]',
     'tests.test_playbooks'),

    # ------------------------- a domain is a company
    #
    # Five people at one company is one account with five contacts,
    # not one account and four discarded rows. Each of these is a way
    # back to the collapse.

    ('upload: discard a colleague as a duplicate row',
     'src/web/upload.py',
     '            if person is None:',
     '            if True:',
     'tests.test_import_contacts'),

    ('upload: treat a name as contact identity',
     'src/web/upload.py',
     '    profile = linkedin.canonical((contact or {}).get("linkedin"))\n    if profile:\n        return f"linkedin:{profile}"\n    return None',
     '    profile = linkedin.canonical((contact or {}).get("linkedin"))\n    if profile:\n        return f"linkedin:{profile}"\n    return ((contact or {}).get("name") or "").strip().lower() or None',
     'tests.test_import_contacts'),

    ('upload: drop the people when committing the batch',
     'src/web/upload.py',
     '        if people:\n            rec["contacts"] = identity.assign_keys(people)',
     '        if False:\n            rec["contacts"] = identity.assign_keys(people)',
     'tests.test_import_contacts'),

    ('upload: let the same mailbox import as two people',
     'src/web/upload.py',
     '            if person in first["identities"]:',
     '            if False:',
     'tests.test_import_contacts'),

    # ------------------------- reading the estate
    #
    # A full parse of a state file inside a loop. Invisible against a
    # 33-account demo, 9.9 seconds against 30,000 records.

    ('api: read the whole queue once per campaign',
     'src/web/api.py',
     '    known = {r["id"]: r for r in repo.records()}\n    out = []\n    for campaign in repo.campaigns():\n        wanted = set(campaign.get("record_ids") or [])\n        recs = [known[rid] for rid in wanted if rid in known]',
     '    out = []\n    for campaign in repo.campaigns():\n        recs = [r for r in repo.records()\n                if r["id"] in (campaign.get("record_ids") or [])]',
     'tests.test_request_scale'),

    ('api: read the whole queue once per batch',
     'src/web/api.py',
     '    grouped = {}\n    for rec in repo.records():\n        key = rec.get("batch") or rec.get("batch_id")\n        grouped.setdefault(key, []).append(rec)\n    out = []\n    for batch, count in repo.batches().items():\n        recs = grouped.get(batch) or []',
     '    out = []\n    for batch, count in repo.batches().items():\n        recs = repo.records(batch=batch)',
     'tests.test_request_scale'),

    # ------------------------- the sidebar
    #
    # Progressive disclosure is the whole point: forty links at once
    # is an index, and an index only helps somebody who already knows
    # the name of what they want.

    ('pages: expand every navigation section at once',
     'src/web/pages.py',
     '        nav += (f\'<details class="navsec"{" open" if here else ""}>\'',
     '        nav += (f\'<details class="navsec" open>\'',
     'tests.test_web_invariants'),

    ('pages: offer a section the role cannot enter',
     'src/web/pages.py',
     '        if not entries:\n',
     '        if False:\n',
     'tests.test_web_invariants'),

    ('pages: offer an action the role cannot perform',
     'src/web/pages.py',
     '        if permission not in can:\n            continue',
     '        if False:\n            continue',
     'tests.test_web_invariants'),

    # ------------------------- discovery and the client's ruling
    #
    # A run that returns companies the client already knows costs
    # their trust the first time they read it. And the review file is
    # the one artefact that leaves the building, is edited by
    # somebody who is not us, and comes back.

    ('discovery: propose a company already in the workspace',
     'src/discovery.py',
     '    if domain in universe["records"]:\n        return KNOWN_RECORD, "already in this workspace"',
     '    if False:\n        return KNOWN_RECORD, "already in this workspace"',
     'tests.test_discovery'),

    ('discovery: forget what an earlier run already proposed',
     'src/discovery.py',
     '    if domain in universe["previous"]:',
     '    if False:',
     'tests.test_discovery'),

    ('discovery: propose a company the client already ruled on',
     'src/discovery.py',
     '    if domain in (decided or {}):',
     '    if False:',
     'tests.test_discovery'),

    ('discovery: accept a candidate with no evidence',
     'src/discovery.py',
     '    if len(evidence) < MINIMUM_EVIDENCE:',
     '    if False:',
     'tests.test_discovery'),

    ('discovery: accept anything shaped like a domain',
     'src/discovery.py',
     '    if not normalised or not ingest.is_hostname(normalised):',
     '    if not normalised:',
     'tests.test_discovery'),

    ('clientreview: accept a canonical column the client edited',
     'src/clientreview.py',
     '            if moved:',
     '            if False:',
     'tests.test_client_review'),

    ('clientreview: accept a candidate id we never sent',
     'src/clientreview.py',
     '        if entry_id not in sent:',
     '        if False:',
     'tests.test_client_review'),

    ('clientreview: accept the same candidate id twice',
     'src/clientreview.py',
     '        if entry_id in seen:',
     '        if False:',
     'tests.test_client_review'),

    ('clientreview: accept a status outside the closed set',
     'src/clientreview.py',
     '        if status not in STATUSES:',
     '        if False:',
     'tests.test_client_review'),

    ('clientreview: let a fit judgement look like an ICP change',
     'src/clientreview.py',
     '    rows = [row for row in parsed["applied"]\n            if row["status"] in FIT_JUDGEMENTS]',
     '    rows = list(parsed["applied"])',
     'tests.test_client_review'),

    # ------------------------- cohort learning
    #
    # The failure this is built against is optimising on four replies
    # against three, and the rule it must never break is that a
    # performance number cannot move the client's ICP.

    ('learning: optimise on a handful of replies',
     'src/learning.py',
     '    if (contacted < policy["minimum_contacted"]\n            or outcomes < policy["minimum_outcomes"]):',
     '    if False:',
     'tests.test_learning'),

    ('learning: call a cohort confident on its raw rate',
     'src/learning.py',
     '    if base["rate"] and low > base["rate"]:',
     '    if base["rate"] and rate > base["rate"]:',
     'tests.test_learning'),

    ('learning: bucket the rows with missing dimensions together',
     'src/learning.py',
     '        if value in (None, "", "unknown", "UNKNOWN", "none"):\n            return None',
     '        if value in (None, "", "unknown", "UNKNOWN", "none"):\n            value = "unknown"',
     'tests.test_learning'),

    ('learning: let a cohort boost grow without a ceiling',
     'src/learning.py',
     '    return round(min(policy["maximum_boost"], lift * 0.05), 4)',
     '    return round(lift * 0.05, 4)',
     'tests.test_learning'),

    ('learning: boost a cohort that is only promising',
     'src/learning.py',
     '    if not cohort or cohort.get("state") != HIGH_CONFIDENCE:',
     '    if not cohort:',
     'tests.test_learning'),

    # ------------------------- long lists
    #
    # A screen showing 100 of 30,000 that does not say so is a
    # screen somebody will read as complete.

    ('api: let a url widen the page size without limit',
     'src/web/api.py',
     '    size = min(size, MAX_PAGE_SIZE)',
     '    size = size',
     'tests.test_request_scale'),

    ('api: clamp a page past the end instead of returning nothing',
     'src/web/api.py',
     '    start = (page - 1) * size\n    window = rows[start:start + size]',
     '    start = min((page - 1) * size, max(0, len(rows) - size))\n    window = rows[start:start + size]',
     'tests.test_request_scale'),

    # ------------------------- segment health
    #
    # `eligible_for_splitting` was computed on every qualification
    # run and read by nothing: a cohort identified as too broad to
    # write one message for, then campaigned as one anyway.

    ('api: discard the oversized segments again',
     'src/web/api.py',
     '        "too_broad": rows_for(found["eligible_for_splitting"]),',
     '        "too_broad": [],',
     'tests.test_request_scale'),

    ('api: reassign segments on a read instead of reading the stored one',
     'src/web/api.py',
     '    found = campaignseg.summarise(assigned, config)',
     '    found = campaignseg.summarise(assigned, config)\n    found = dict(found, eligible_for_splitting={})',
     'tests.test_request_scale'),

    ("eligibility: stop blocking a frozen campaign",
     "src/eligibility.py",
     "    if campaigns.is_frozen(campaign):\n        return BLOCKED_CAMPAIGN_FROZEN",
     "    if False:\n        return BLOCKED_CAMPAIGN_FROZEN",
     "tests.test_production"),

    ("duplicates: stop detecting identical bodies",
     "src/duplicates.py",
     "    return bool(first) and first == second\n\n\ndef same_subject",
     "    return False\n\n\ndef same_subject",
     "tests.test_duplicates tests.test_qa"),

    ("duplicates: compare raw text so whitespace hides a duplicate",
     "src/duplicates.py",
     "        normalised = normalize(block)",
     "        normalised = block",
     "tests.test_duplicates"),

    ("duplicates: treat every paragraph as substantive",
     "src/duplicates.py",
     "MIN_SUBSTANTIVE_WORDS = 8",
     "MIN_SUBSTANTIVE_WORDS = 0",
     "tests.test_duplicates"),

    ("qa: stop blocking on a duplicate body",
     "src/qa.py",
     '        "duplicate_email_body": True,',
     '        "duplicate_email_body": False,',
     "tests.test_duplicates"),

    # The first attempt here was `findings = [] or duplicates.blocking(...)`,
    # which is a no-op: `[] or x` is x. A mutation has to actually remove
    # the guard rather than decorate it, or the audit reports a miss that
    # says more about the mutation than about the tests.
    ("campaigns: let a duplicate body through validation",
     "src/campaigns.py",
     "    if not findings:",
     "    if True:",
     "tests.test_duplicates"),

    ("quality: score an unknown source as trustworthy",
     "src/quality.py",
     "DEFAULT_RELIABILITY = 0.30",
     "DEFAULT_RELIABILITY = 0.95",
     "tests.test_source_reliability"),

    ("quality: let unknown sources corroborate each other",
     "src/quality.py",
     "CORROBORATION_FLOOR = 0.40",
     "CORROBORATION_FLOOR = 0.0",
     "tests.test_source_reliability"),

    ("quality: stop requiring evidence to be attributable",
     "src/quality.py",
     "    if attributable:\n        score += 0.35",
     "    if True:\n        score += 0.35",
     "tests.test_source_reliability"),

    # Two guards were removed from this list rather than left as misses.
    #
    # `icp`'s unknown-vertical check and `explorer`'s filter-name check are
    # both backed by a second guard - the dimension-count gate and `_matches`
    # respectively - so removing either one alone changes no observable
    # behaviour. That is defence in depth working, not a test gap, and a
    # mutation that cannot change an outcome tests the mutation rather than
    # the suite. Removing *both* guards would be caught; removing one is not
    # meant to be.

    ("icp: treat a missing employee count as a positive signal",
     "src/icp.py",
     "        missing.append(\"employee count unknown\")",
     "        total += weights[\"employee_count\"]",
     "tests.test_icp"),

    ("icp: let a decisive rejection be downgraded to unknown",
     "src/icp.py",
     "    decisive = _decisive(negative)\n    if decisive:",
     "    decisive = []\n    if decisive:",
     "tests.test_icp"),

    ("segments: classify on a single weak keyword",
     "src/segments.py",
     "    if not enough:",
     "    if False:",
     "tests.test_icp"),

    ("geo: guess a timezone for a country that spans several",
     "src/geo.py",
     '    "united states": ("US", None, None, None),',
     '    "united states": ("US", US_EAST, "America/New_York", FROM_COUNTRY_SINGLE),',
     "tests.test_icp"),

    ("geo: store an offset instead of an IANA name",
     "src/geo.py",
     '    "germany": ("DE", DACH, "Europe/Berlin", FROM_COUNTRY_SINGLE),',
     '    "germany": ("DE", DACH, "UTC+1", FROM_COUNTRY_SINGLE),',
     "tests.test_icp"),

    ("routing: give every company the same titles",
     "src/routing.py",
     "    name = policy[\"band_strategy\"].get(band, policy[\"fallback_strategy\"])",
     "    name = FOUNDER_LED",
     "tests.test_routing"),

    ("routing: let a review company be enriched anyway",
     "src/routing.py",
     "    if status != icp.QUALIFIED:\n        cap = 0",
     "    if False:\n        cap = 0",
     "tests.test_routing"),

    ("dmplan: enrich without an approved plan",
     "src/dmplan.py",
     "    ok, why = is_current(batch, companies)\n    if not ok:",
     "    ok, why = is_current(batch, companies)\n    if False:",
     "tests.test_routing"),

    ("dmplan: keep an approval current after the verdicts change",
     "src/dmplan.py",
     '    if approval.get("fingerprint") != fingerprint(companies):',
     "    if False:",
     "tests.test_routing"),

    ("dmplan: report the maximum as the expectation",
     "src/dmplan.py",
     '    expected = sum(c["credits"] for c in calls if not c["conditional"])',
     '    expected = sum(c["credits"] for c in calls)',
     "tests.test_routing"),

    ("campaignseg: stop merging small segments",
     "src/campaignseg.py",
     '            if len(members) < policy["min_segment_size"]:',
     "            if False:",
     "tests.test_routing"),

    ("campaignseg: segment rejected companies too",
     "src/campaignseg.py",
     '                if entry["verdict"].get("icp_status") == icp.QUALIFIED',
     "                if True",
     "tests.test_routing"),

    ("strategy: recommend a pain nothing supports",
     "src/strategy.py",
     "    supported = [row for row in scored if row[\"supported\"]]",
     "    supported = list(scored)",
     "tests.test_routing"),

    ("push: enable the sender",
     "src/push.py",
     "        raise LiveSendNotEnabled(",
     "        pass or LiveSendNotEnabled(",
     "tests.test_push tests.test_invariants"),

    # ---------------------------------------------------- added this session

    ("enrich: spend without writing the waterfall ledger",
     "src/enrich.py",
     "        from . import waterfall\n        waterfall.record_step(",
     "        from . import waterfall\n        _ = waterfall and (lambda *a, **k: None)(",
     "tests.test_waterfall"),

    ("waterfall: accept a fallback with no reason at all",
     "src/waterfall.py",
     "    if not reason:\n        return False,",
     "    if False:\n        return False,",
     "tests.test_waterfall"),

    ("approve: latch the record state instead of deriving it",
     "src/approve.py",
     '    rec["state"] = ("approved" if fully_approved(rec, config, campaign)\n'
     '                    else "drafted")',
     '    rec["state"] = ("approved" if rec.get("state") == "approved"\n'
     '                    else rec["state"])',
     "tests.test_approve"),

    ("approve: call a record with nothing approvable fully approved",
     "src/approve.py",
     "    if not pending_steps:\n        return False",
     "    if not pending_steps:\n        return True",
     "tests.test_approve"),

    ("approve: let the sync overwrite a dropped or held record",
     "src/approve.py",
     "    if rec.get(\"state\") not in DERIVED_FROM_STEPS:\n        return rec.get(\"state\")",
     "    if False:\n        return rec.get(\"state\")",
     "tests.test_approve"),

    ("icp: let a contradiction still read as high confidence",
     "src/icp.py",
     '        if components["contradictions"]:\n            band = MEDIUM if band == HIGH else LOW',
     '        if False:\n            band = MEDIUM if band == HIGH else LOW',
     "tests.test_icp"),

    ("icp: stop detecting contradictions at all",
     "src/icp.py",
     "def contradictions(rec, segment):\n    \"\"\"Pairs of facts that cannot both hold. Reported, never resolved.\"\"\"\n    found = []",
     "def contradictions(rec, segment):\n    \"\"\"Pairs of facts that cannot both hold. Reported, never resolved.\"\"\"\n    return []\n    found = []",
     "tests.test_icp"),

    ("segments: accept a band table with a gap in it",
     "src/segments.py",
     '        if i and table[i - 1][2] + 1 != low:',
     '        if False:',
     "tests.test_icp"),

    ("segments: accept a band table that does not end open",
     "src/segments.py",
     '    if table[-1][2] is not None:\n        raise ValueError',
     '    if False:\n        raise ValueError',
     "tests.test_icp"),

    ("schedule: send on a day the client did not configure",
     "src/schedule.py",
     "    while on.isoweekday() not in days:",
     "    while False:",
     "tests.test_schedule"),

    ("schedule: guess a time for a company with no timezone",
     "src/schedule.py",
     '    if not schedulable:\n        return {"timezone": timezone, "schedulable": False,',
     '    if False:\n        return {"timezone": timezone, "schedulable": False,',
     "tests.test_schedule"),

    ("dmplan: drop the segment key from the approval fingerprint",
     "src/dmplan.py",
     '            "segment_key": entry.get("segment_key"),',
     '            "segment_key": None,',
     "tests.test_qualify_resume"),

    ("qualify: throw away the verdicts instead of persisting them",
     "src/qualify.py",
     "        with store.transaction() as recs:\n            result = run(recs,",
     "        recs = []\n        if True:\n            result = run(None,",
     "tests.test_qualify_resume"),

    ("report: report planned decision makers as found ones",
     "src/report.py",
     '    found = sum(len(r.get("contacts") or []) for r in recs)',
     '    found = planned',
     "tests.test_reporting"),

    ("report: report a zero credit spend instead of an unknown one",
     "src/report.py",
     '        # Deliberately None rather than 0 - see the docstring.\n        "actual_credits": None,',
     '        "actual_credits": 0,',
     "tests.test_reporting"),

    # ----------------------------------------- the outreach demo and its gaps

    ("cadence: read the stored sendable flag instead of the verdict",
     "src/cadence.py",
     '    if spec["channel"] == "email" and not lint.sendable(contact):',
     '    if spec["channel"] == "email" and not contact.get("sendable"):',
     "tests.test_cadence"),

    ("cadence: report waiting for a connection nobody can accept",
     "src/cadence.py",
     '    if spec["channel"] == "linkedin" and not contact.get("linkedin"):\n        return "blocked"\n    if spec.get("requires") == ACCEPT_EVENT and not accepted:',
     '    if spec.get("requires") == ACCEPT_EVENT and not accepted:',
     "tests.test_demo_outreach tests.test_cadence"),

    ("push: stop sending our identifiers to EmailBison",
     "src/push.py",
     '            "contact_key": item["contact_key"],\n            "client": rec.get("client", ""),\n            "push_id": item["push_id"],\n        })\n    return rows\n\n\ndef heyreach_rows',
     '            "push_id": item["push_id"],\n        })\n    return rows\n\n\ndef heyreach_rows',
     "tests.test_push tests.test_preproduction"),

    ("heyreach: stop sending our identifiers with the lead",
     "src/providers/heyreach.py",
     '                 for name in ("record_id", "contact_key", "client",',
     '                 for name in (',
     "tests.test_push"),

    ("coherence: stop noticing the same message on two channels",
     "src/coherence.py",
     "            if duplicates.same_body(_text_of(step), _text_of(other)):",
     "            if False:",
     "tests.test_coherence tests.test_demo_outreach"),

    ("coherence: allow a step after the prospect replied",
     "src/coherence.py",
     "        if day is None or day < paused_at:",
     "        if True:",
     "tests.test_coherence"),

    ("coherence: allow a live step on a channel that is closed",
     "src/coherence.py",
     "        if allowed is not False:",
     "        if True:",
     "tests.test_coherence tests.test_demo_outreach"),

    ("coherence: let a blocker be averaged away",
     "src/coherence.py",
     '    if any(f["severity"] == BLOCK for f in findings):',
     "    if False:",
     "tests.test_coherence"),

    ("demo: build the provider payload by hand instead of via the sender",
     "src/demo_outreach.py",
     "    payloads = push.payloads(",
     "    payloads = (lambda *a, **k: {'emailbison': {'endpoint': '', 'method': 'POST', 'body': {'leads': []}, 'count': 0}, 'heyreach': {'endpoint': '', 'method': 'POST', 'body': {'campaignId': None, 'accountLeadPairs': []}, 'count': 0}})(",
     "tests.test_demo_outreach"),

    ("outreachpage: stop masking addresses",
     "src/outreachpage.py",
     "    if reveal:\n        return str(address)",
     "    if True:\n        return str(address)",
     "tests.test_demo_outreach"),

    ("outreachpage: stop escaping untrusted text",
     "src/outreachpage.py",
     '    return html.escape(str(value if value is not None else ""))',
     '    return str(value if value is not None else "")',
     "tests.test_demo_outreach"),

    # ------------------------------------------- mandatory double verification

    ("verification: drop the second-verifier requirement",
     "src/verification.py",
     '    "required_confirmations": 2,',
     '    "required_confirmations": 1,',
     "tests.test_double_verification tests.test_verification"),

    ("verification: stop applying the confirmation rule to the decision",
     "src/verification.py",
     "    if decision[\"sendable\"] and count < required:",
     "    if False:",
     "tests.test_double_verification tests.test_verification"),

    ("verification: count calls instead of independent providers",
     "src/verification.py",
     '            if entry["status"] in CONFIRMING_STATUSES}',
     '            if entry["status"] in CONFIRMING_STATUSES} | {id(e) for e in (evidence or []) if e["status"] in CONFIRMING_STATUSES}',
     "tests.test_double_verification"),

    ("verification: trust the stored state instead of the evidence",
     "src/verification.py",
     "    return decide(all_evidence(contact), policy)[\"sendable\"] is True",
     '    stored = (contact.get("verification") or {}).get("state")\n    if stored:\n        return stored in SENDABLE_STATES\n    return decide(all_evidence(contact), policy)["sendable"] is True',
     "tests.test_double_verification tests.test_verification"),

    ("verification: let an accept_all count as a confirmation",
     "src/verification.py",
     "CONFIRMING_STATUSES = (S_VALID,)",
     "CONFIRMING_STATUSES = (S_VALID, S_ACCEPT_ALL)",
     "tests.test_double_verification"),

    # `push.verify_before_payload`'s confirmation re-check is deliberately not
    # mutated here, and it is worth saying why rather than leaving it as a
    # miss. It is defence in depth: `eligibility.decide` runs first in the same
    # function and already refuses an under-confirmed address, so removing the
    # second check changes no observable behaviour and no test can see it go.
    # It stays in the code because a payload is the last cheap place to stop
    # and the guard costs nothing; it stays out of this list because a
    # mutation that cannot change an outcome tests the mutation rather than the
    # suite. Removing *both* checks is caught - see the eligibility mutations.

    ("enrich: spend verifier credits on an MX-blocked domain",
     "src/enrich.py",
     "        if c.get(\"key\") in mx_blocked:",
     "        if False:",
     "tests.test_enrich"),

    ("channels: report a gateway block as a verification failure",
     "src/channels.py",
     "    allowed, _ = mx.allows_email(contact, config)\n    if not allowed:\n        # Re-derived from the hostnames",
     "    allowed = True\n    if not allowed:\n        # Re-derived from the hostnames",
     "tests.test_channels tests.test_demo_outreach"),

    ("approve: let a held record block its LinkedIn steps too",
     "src/approve.py",
     'REFUSED_STATES = ("dropped", "pushed")',
     'REFUSED_STATES = ("dropped", "pushed", "held")',
     "tests.test_approve tests.test_invariants"),

    ("campaigns: drop the double-verification launch check",
     "src/campaigns.py",
     '    ("double verification", check_double_verification),',
     "",
     "tests.test_double_verification"),

    # ---------------------------------------------------------- the web layer
    #
    # The web application added a second way to reach every rule above: a URL.
    # These break the web-specific guards - tenancy, permission, session,
    # secret handling, client-supplied verdicts, budget - and check that the
    # web suite goes red rather than the CLI one.

    ("repo: let a repository read another tenant's record",
     "src/repo.py",
     '        return self.client is None or (rec or {}).get("client") == self.client',
     '        return True',
     "tests.test_repo tests.test_web_security"),

    ("repo: let a write touch a record this repo does not own",
     "src/repo.py",
     '        for rec in records:\n            if not self._mine(rec):\n                raise CrossClientAccess(',
     '        for rec in records:\n            if False:\n                raise CrossClientAccess(',
     "tests.test_tenancy_write_guard"),

    ("workspaces: let a non-member into a workspace",
     "src/workspaces.py",
     '    found = membership_of(email, workspace_slug, rows)\n    if found is None:\n        raise NotAMember',
     '    found = membership_of(email, workspace_slug, rows) or {\n        "kind": "membership", "email": email, "workspace": workspace_slug,\n        "role": OPERATOR, "via": "membership"}\n    if False:\n        raise NotAMember',
     "tests.test_repo tests.test_workspaces tests.test_web_security"),

    ("workspaces: grant a permission the role does not carry",
     "src/workspaces.py",
     '    return permission in GRANTS.get(role, set())',
     '    return True',
     "tests.test_workspaces tests.test_web_security"),

    ("workspaces: give a viewer the operator's reach",
     "src/workspaces.py",
     '_VIEWER = {WORKSPACE_VIEW, REPORTING_VIEW}',
     '_VIEWER = {WORKSPACE_VIEW, REPORTING_VIEW, CONTACTS_VIEW, OPERATIONS_VIEW}',
     "tests.test_workspaces tests.test_web_security"),

    ("workspaces: let a super admin membership look like an ordinary one",
     "src/workspaces.py",
     '"role": SUPER_ADMIN,\n                "via": "super_admin"}',
     '"role": SUPER_ADMIN,\n                "via": "membership"}',
     "tests.test_workspaces"),

    ("security: cache the role in the session instead of resolving it",
     "src/web/security.py",
     '    return workspaces.membership_of(session["email"], session["workspace"])',
     '    return session.setdefault("_cached", workspaces.membership_of(\n        session["email"], session["workspace"]))',
     "tests.test_web_security"),

    ("security: accept a verdict supplied by the browser",
     "src/web/security.py",
     '        if field in (payload or {}):',
     '        if False:',
     "tests.test_web_security"),

    ("security: skip the CSRF comparison",
     "src/web/security.py",
     '    if not hmac.compare_digest(str(expected), str(supplied)):',
     '    if False:',
     "tests.test_web_security"),

    ("security: report the credential value instead of its presence",
     "src/web/security.py",
     '    return {name: configured(name) for name in SECRET_ENV}',
     '    return {name: os.environ.get(name) for name in SECRET_ENV}',
     "tests.test_web_security"),

    ("security: stop escaping untrusted text",
     "src/web/security.py",
     '    return html.escape(str(value if value is not None else ""), quote=True)\n\n\ndef attr(value):',
     '    return str(value if value is not None else "")\n\n\ndef attr(value):',
     "tests.test_web_security"),

    ("app: stop checking the permission before the handler runs",
     "src/web/app.py",
     '        needed = permission_for(path)\n        if needed:',
     '        needed = permission_for(path)\n        if False:',
     "tests.test_web_security tests.test_web_app"),

    ("app: let anybody into the super-admin console",
     "src/web/app.py",
     '        if not person.get("super_admin"):',
     '        if False:',
     "tests.test_web_security"),

    ("app: show a client the operator's dashboard",
     "src/web/app.py",
     '            simple = not security.may(session, workspaces.OPERATIONS_VIEW)\n            return self._page(\n                pages.dashboard(api.dashboard(repo), simple,',
     '            simple = False\n            return self._page(\n                pages.dashboard(api.dashboard(repo), simple,',
     "tests.test_web_app"),

    ("app: let a client-facing role reach the vendor dimensions",
     "src/web/app.py",
     '        if security.may(session, workspaces.OPERATIONS_VIEW):\n            return api.DIMENSIONS\n        return api.CLIENT_DIMENSIONS',
     '        return api.DIMENSIONS',
     "tests.test_vendor_dimensions_are_not_client_facing"),

    ("upload: accept a cell that would execute as a formula",
     "src/web/upload.py",
     '        if looks_like_formula(untouched.get("domain", "")):',
     '        if False:',
     "tests.test_web_app"),

    ("upload: strip before looking for a leading control character",
     "src/web/upload.py",
     '    if text.startswith(CONTROL_PREFIXES):',
     '    if text.lstrip().startswith(CONTROL_PREFIXES):',
     "tests.test_web_app"),

    ("export: build the browser download with its own CSV writer",
     "src/export.py",
     '    writer.writerow(safe_row(header))\n    writer.writerows(safe_rows(rows))\n    return buf.getvalue()',
     '    writer.writerow(header)\n    writer.writerows(rows)\n    return buf.getvalue()',
     "tests.test_web_security"),

    ("jobs: spend without a budget",
     "src/jobs.py",
     '    if job.get("spends") and budget is None:',
     '    if False:',
     "tests.test_jobs"),

    ("jobs: ignore the budget once the run has started",
     "src/jobs.py",
     '        if job.get("spends") and (job.get("spent") or 0) >= int(budget):',
     '        if False:',
     "tests.test_jobs"),

    ("jobs: resume by position instead of identity",
     "src/jobs.py",
     '    if job.get("cursor") is not None and job["cursor"] in ids:\n        start = ids.index(job["cursor"]) + 1',
     '    if job.get("cursor") is not None and job["cursor"] in ids:\n        start = int(job.get("processed") or 0)',
     "tests.test_jobs"),

    ("jobs: keep going through a batch that is failing throughout",
     "src/jobs.py",
     '        if should_abort(job):',
     '        if False:',
     "tests.test_jobs"),

    ("workspaces: create a membership for a user who does not exist",
     "src/workspaces.py",
     '    if user(email) is None:\n        raise NoSuchUser',
     '    if False:\n        raise NoSuchUser',
     "tests.test_membership_needs_a_user"),

    ("api: hand the whole user directory to a workspace admin",
     "src/web/api.py",
     '        "roles": list(ws.assignable_roles()),',
     '        "all_users": sorted(ws.users(rows), key=lambda u: u["email"]),\n'
     '        "roles": list(ws.assignable_roles()),',
     "tests.test_web_security"),

    ("pages: show the provider mapping to a role without the permission",
     "src/web/pages.py",
     '  ]) if can_see_providers else',
     '  ]) if True else',
     "tests.test_web_app"),

    ("demodata: write the demo client files into the real config directory",
     "src/web/demodata.py",
     '    if os.path.abspath(directory) == os.path.abspath(clients.CLIENTS):',
     '    if False:',
     "tests.test_demo_mode"),

    ("demodata: install a demo over real records",
     "src/web/demodata.py",
     '    existing = [r for r in store.load() if not r.get("demo")]\n    if existing:',
     '    existing = [r for r in store.load() if not r.get("demo")]\n    if False:',
     "tests.test_demo_mode"),

    # ---- the human ICP decision, and what it is not allowed to do

    ("qualify: let a review outlive the facts it was given on",
     "src/qualify.py",
     '    if review.get("inputs_fingerprint") != qualification.get(\n            "inputs_fingerprint"):\n        return None\n    return review\n\n\ndef stale_review_of',
     '    return review\n\n\ndef stale_review_of',
     "tests.test_icp_review tests.test_web_icp_review"),

    ("dmplan: let the spend gate honour a stale review",
     "src/dmplan.py",
     '    if review.get("inputs_fingerprint") != qualification.get(\n            "inputs_fingerprint"):\n        return None\n    return review',
     '    return review',
     "tests.test_icp_review"),

    ("dmplan: let one reviewer widen what the client agreed to spend",
     "src/dmplan.py",
     '        if not policy["allow_review_enrichment"]:\n            if review:',
     '        if False:\n            if review:',
     "tests.test_icp_review tests.test_web_icp_review"),

    ("dmplan: ignore a human rejection",
     "src/dmplan.py",
     '    if review and review.get("decision") == "reject":',
     '    if False:',
     "tests.test_icp_review tests.test_web_icp_review"),

    ("api: apply an ICP decision to a verdict that has since changed",
     "src/web/api.py",
     '    if fingerprint and current and fingerprint != current:',
     '    if False:',
     "tests.test_web_icp_review"),

    # ---- batch processing, and the four steps it must not run

    ("api: let the web layer run a job type that spends",
     "src/web/api.py",
     '    if job_type in jobs.SPENDING_TYPES:',
     '    if False:',
     "tests.test_web_jobs"),

    ("api: run any job type the caller names",
     "src/web/api.py",
     '    if job_type not in RUNNABLE_JOBS:',
     '    if False:',
     "tests.test_web_jobs"),

    # ---- the campaign builder

    ("api: let one company sit in two campaigns",
     "src/web/api.py",
     '        if rec["id"] in taken:\n            continue\n        record_ids.append(rec["id"])',
     '        record_ids.append(rec["id"])',
     "tests.test_web_campaign_builder"),

    ("api: accept any string as a campaign id",
     "src/web/api.py",
     '    if not repo_module.valid_slug(campaign_id):',
     '    if False:',
     "tests.test_web_campaign_builder"),

    # ---- workspace policy

    ("workspaces: let a form set a config key that is not on the allowlist",
     "src/workspaces.py",
     '    if spec is None:\n        raise NotOverridable(',
     '    if False:\n        raise NotOverridable(',
     "tests.test_web_settings"),

    ("workspaces: clamp a policy value instead of refusing it",
     "src/workspaces.py",
     '        if value < spec["min"] or value > spec["max"]:',
     '        if False:',
     "tests.test_web_settings"),

    # The merge moved out of `repo.config` and into `clients.load`,
    # which is the whole point of the change: it used to be the web
    # layer's answer while the command line's answer was different.
    ("clients: stop merging a workspace override onto its config",
     "src/clients.py",
     '    settings = (workspaces.policy(workspace, rows) if workspace\n'
     '                else overrides_for(client, rows))\n'
     '    return workspaces.apply_policy(config, settings)',
     '    return config',
     "tests.test_client_settings tests.test_web_settings"),

    ("clients: pick one of two workspaces claiming the same client",
     "src/clients.py",
     '    if len(matches) > 1:',
     '    if False:',
     "tests.test_client_settings"),

    ("workspaces: let a second workspace claim a client already in use",
     "src/workspaces.py",
     '        if taken:\n            raise ClientTaken(',
     '        if False:\n            raise ClientTaken(',
     "tests.test_client_settings"),

    # ---- pausing, replies and the client-facing cut

    ("api: let a campaign resume without re-running its checks",
     "src/web/api.py",
     '        orchestrator.resume(campaign, by=by, role=roles.ADMIN, recs=recs,\n                            config=repo.config())',
     '        campaign["pause"] = None',
     "tests.test_web_pause_replies"),

    ("pages: show a client the operator's verification block",
     "src/web/pages.py",
     '{client_verification}\n<p class="note">No address is used on the strength of a single provider. Where',
     '{verification}\n<p class="note">No address is used on the strength of a single provider. Where',
     "tests.test_web_acceptance"),

    # ---- the refusal trail

    ("app: stop writing down that a request was refused",
     "src/web/app.py",
     '            workspaces.record(\n                (session or {}).get("email") or "anonymous",',
     '            (lambda *a, **k: None)(\n                (session or {}).get("email") or "anonymous",',
     "tests.test_web_admin"),

    ('touch: treat a built payload as a send',
     'src/touch.py',
     'CONFIRMING_EVENTS = {\n    events.PUSH_MARKED: SENT,',
     'CONFIRMING_EVENTS = {\n    events.PUSH_PREPARED: SENT,\n    events.PUSH_MARKED: SENT,',
     'tests.test_cross_channel tests.test_cross_channel_copy'),

    ('touch: reference a touch whose sender nobody recorded',
     'src/touch.py',
     'if not last.get("sender_id"):',
     'if False:',
     'tests.test_cross_channel'),

    ('touch: let a step reference a touch that has not happened yet',
     'src/touch.py',
     'if before_day is not None and (step["day"] or 0) >= before_day:\n            continue',
     'if False:\n            continue',
     'tests.test_cross_channel tests.test_cross_channel_copy'),

    ('touch: reference the same touch in every later step',
     'src/touch.py',
     'if already_referenced and _touch_key(last) in already_referenced:',
     'if False:',
     'tests.test_cross_channel_copy'),

    ('senderidentity: call two senders colleagues without permission',
     'src/senderidentity.py',
     'if not workspace_allows:',
     'if False:',
     'tests.test_sender_identity tests.test_cross_channel'),

    ('senderidentity: ignore a sender who opted out of colleague language',
     'src/senderidentity.py',
     'if opted_out:',
     'if False:',
     'tests.test_cross_channel'),

    ("senderidentity: hand back another workspace's sender",
     'src/senderidentity.py',
     'raise CrossWorkspaceSender(\n                f"sender {sender_id!r} belongs to another workspace")',
     'return row',
     'tests.test_sender_identity tests.test_web_senders'),

    ('senderidentity: resolve a provider account id across workspaces',
     'src/senderidentity.py',
     '    for row in accounts_for(workspace, channel, rows):\n        if str(row.get("provider_account_id") or "") == str(provider_account_id):',
     '    for row in (load() if rows is None else rows):\n        if str(row.get("provider_account_id") or "") == str(provider_account_id):',
     'tests.test_sender_identity'),

    ('assignment: recompute the sender instead of reading the stored one',
     'src/assignment.py',
     'if block.get(channel):\n            continue',
     'if False:\n            continue',
     'tests.test_sender_identity'),

    ('assignment: reassign without a reason',
     'src/assignment.py',
     'if not (reason or "").strip():',
     'if False:',
     'tests.test_sender_identity tests.test_web_senders'),

    ('cadence: accept a cross-channel mention with no licence',
     'src/cadence.py',
     '        if not licensed:',
     '        if False:',
     'tests.test_cross_channel_copy'),

    ('cadence: accept a licensed mention that names the wrong person',
     'src/cadence.py',
     '        if named and named not in text:',
     '        if False:',
     'tests.test_cross_channel_copy'),

    # Retargeted after the audit showed the outer `workspaces_for`
    # filter to be redundant: `workspace_card` drops an unauthorised
    # workspace anyway, so removing the filter was unobservable. This
    # breaks the check that actually holds the boundary.
    ('api: build a workspace card for a workspace nobody is a member of',
     'src/web/api.py',
     '    try:\n        repo = repo_module.Repo.for_user(email, slug)\n    except (ws.NotAMember, repo_module.UnknownClient):\n        return None',
     '    repo = repo_module.Repo(ws.workspace(slug).get("client") or slug)\n    repo.workspace = slug',
     'tests.test_web_senders'),

    ("offline: let the harness reach a real hostname",
     "tests/offline.py",
     "        if not is_loopback(host):\n            refuse(host)\n        return real_getaddrinfo(host, *args, **kwargs)",
     "        return real_getaddrinfo(host, *args, **kwargs)",
     "tests.test_offline_harness"),

    ("offline: call anything starting 127. loopback, prefix and all",
     "tests/offline.py",
     '    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255\n                               for p in parts):\n        return parts[0] == "127"',
     '    if host.startswith("127."):\n        return True\n    if parts and False:\n        return False',
     "tests.test_offline_harness"),

    ("app: approve without writing it into the audit trail",
     "src/web/app.py",
     '        repo.audit(\n            "campaign.approval_stale" if status == "stale"',
     '        None and repo.audit(\n            "campaign.approval_stale" if status == "stale"',
     "tests.test_web_approval_audit"),

    ("app: drop a blank form field on the way in",
     "src/web/app.py",
     '        parsed = urllib.parse.parse_qs(raw.decode("utf-8", "replace"),\n                                       keep_blank_values=True)',
     '        parsed = urllib.parse.parse_qs(raw.decode("utf-8", "replace"))',
     "tests.test_web_settings"),

    # ------------------------------------------------------------- Slack
    #
    # The five properties the whole notification architecture rests on. Each
    # of these mutations is a plausible refactor, and each one puts one
    # client's alert somewhere it must never go.

    ("notify: fall back to the operations channel when a workspace has none",
     "src/notify.py",
     '    policy = ws.policy(slug, rows)\n    return (policy.get(WORKSPACE_CHANNEL_KEY) or "").strip() or None',
     '    policy = ws.policy(slug, rows)\n    return ((policy.get(WORKSPACE_CHANNEL_KEY) or "").strip()\n            or ops_channel())',
     "tests.test_notify tests.test_notify_pipeline"),

    ("notify: resolve an ambiguous client to the first workspace",
     "src/notify.py",
     '    return matches[0] if len(matches) == 1 else None',
     '    return matches[0] if matches else None',
     "tests.test_notify tests.test_notify_pipeline"),

    ("notify: let a neutral reply into the client channel",
     "src/notify.py",
     '    NEUTRAL_REPLY: (NOWHERE, INFO),',
     '    NEUTRAL_REPLY: (WORKSPACE, INFO),',
     "tests.test_notify tests.test_notify_pipeline"),

    ("notify: send the whole payload to the client channel unscrubbed",
     "src/notify.py",
     '    payload = (_workspace_payload(fields)\n               if decision["destination"] == WORKSPACE\n               else _global_payload(fields))',
     '    payload = _global_payload(fields)',
     "tests.test_notify tests.test_notify_pipeline"),

    ("notify: let a duplicate notification through",
     "src/notify.py",
     '        "last_error": None,\n    }\n    with transaction() as current:\n        if any(r.get("id") == identifier for r in current):\n            return get(identifier)\n        current.append(row)',
     '        "last_error": None,\n    }\n    with transaction() as current:\n        if False:\n            return get(identifier)\n        current.append(row)',
     "tests.test_notify tests.test_notify_wiring tests.test_notify_concurrency"),

    ("slack: let the client config override the workspace channel",
     "src/providers/slack.py",
     '    if channel is not UNSET:\n        return channel or None',
     '    if channel is not UNSET and channel:\n        return channel',
     "tests.test_notify_wiring"),

    # -------------------------------------------- account-based outreach
    #
    # The claim ladder is the part of this system that decides what a
    # stranger is told about outreach they cannot verify. Each of these
    # mutations is a plausible simplification that would put an unsupported
    # sentence in front of a prospect.

    ("account: treat a planned touch as a confirmed one",
     "src/account.py",
     '        if confirmed_only and state not in CONFIRMED:\n            continue',
     '        if confirmed_only and False:\n            continue',
     "tests.test_account_outreach"),

    ("account: read a referral out of a reply with no target",
     "src/account.py",
     '        if not entry.get("contact") or not entry.get("referred_to"):\n            continue',
     '        if not entry.get("contact"):\n            continue',
     "tests.test_account_outreach"),

    ("account: say a prospect heard from whoever is assigned now",
     "src/account.py",
     '            "sender_names": sorted({names.get(t["sender_id"], t["sender_id"])\n                                    for t in confirmed if t.get("sender_id")}),',
     '            "sender_names": sorted({names.get(s.get("sender_id"), s.get("sender_id"))\n                                    for s in senders.values() if s.get("sender_id")}),',
     "tests.test_account_outreach"),

    ("outreachclaims: allow a third-party claim by default",
     "src/outreachclaims.py",
     '    OTHER_DM_PRIOR_TOUCH: ("outreach.claim_other_dm", False),',
     '    OTHER_DM_PRIOR_TOUCH: ("outreach.claim_other_dm", True),',
     "tests.test_account_outreach"),

    ("outreachclaims: call a reply a conversation",
     "src/outreachclaims.py",
     '    if not after:\n        return _no(ACTIVE_CONVERSATION,',
     '    if False:\n        return _no(ACTIVE_CONVERSATION,',
     "tests.test_account_outreach"),

    ("outreachclaims: let a referral from anybody license this one",
     "src/outreachclaims.py",
     '    if about_contact and edge["from_contact"] != about_contact:\n        return _no(REFERRAL,',
     '    if False:\n        return _no(REFERRAL,',
     "tests.test_account_outreach"),

    ("outreachclaims: skip the campaign policy and go straight to evidence",
     "src/outreachclaims.py",
     '    on, why = allowed_by_policy(claim_type, config)\n    if not on:',
     '    on, why = allowed_by_policy(claim_type, config)\n    if False:',
     "tests.test_account_outreach"),

    ("fatigue: stop counting touches by other senders",
     "src/fatigue.py",
     '    confirmed = account.touches(rec, contact_key, confirmed_only=True)',
     '    confirmed = [t for t in account.touches(rec, contact_key, confirmed_only=True) if not t.get("sender_id")]',
     "tests.test_account_outreach"),

    ("fatigue: let a company be opened at every contact at once",
     "src/fatigue.py",
     '    if would_be > maximum:',
     '    if False:',
     "tests.test_account_outreach"),

    ("cadencegraph: run a node whose provider capability is unvalidated",
     "src/cadencegraph.py",
     '        if kind in UNVALIDATED:',
     '        if False:',
     "tests.test_account_outreach"),

    ("cadencegraph: let a sender outside the team into a cadence",
     "src/cadencegraph.py",
     '            if sender and sender not in allowed:',
     '            if False:',
     "tests.test_account_outreach"),

    ("cadencegraph: accept a cadence that loops forever",
     "src/cadencegraph.py",
     '    if _has_cycle(graph_):',
     '    if False:',
     "tests.test_account_outreach"),

    ("senderteam: let an empty team authorise everybody",
     "src/senderteam.py",
     '    if not email_senders and not linkedin_senders:',
     '    if False:',
     "tests.test_account_outreach"),

    # ---------------------------------------------------- the report editor

    ("reportdraft: let an edit write a field that is not narrative",
     "src/reportdraft.py",
     '                if key not in NARRATIVE_KEYS:',
     '                if False:',
     "tests.test_report_editor"),

    ("reportdraft: overwrite a version instead of appending one",
     "src/reportdraft.py",
     '            updated["history"] = list(row.get("history") or []) + [snapshot]',
     '            updated["history"] = list(row.get("history") or [])',
     "tests.test_report_editor"),

    ("reportdraft: let a final report be edited",
     "src/reportdraft.py",
     '            if row.get("status") == FINAL:',
     '            if False:',
     "tests.test_report_editor"),

    ("reportdraft: accept markup as a custom section kind",
     "src/reportdraft.py",
     '    if kind not in ("text", "note", "recommendation"):',
     '    if False:',
     "tests.test_report_editor"),

    ("api: let a draft from another workspace be edited",
     "src/web/api.py",
     '    draft = reportdraft.get(draft_id)\n    if draft is None or draft.get("workspace") != repo.workspace:\n        return None\n    updated = reportdraft.edit(',
     '    draft = reportdraft.get(draft_id)\n    if draft is None:\n        return None\n    updated = reportdraft.edit(',
     "tests.test_report_editor"),

    # ------------------------------------------------------ client reports
    #
    # The report is the one artefact that leaves the building. Each of these
    # is a plausible simplification that would put an operator's view of the
    # machine into a document a client opens.

    ("clientreport: let a request name a section its template does not offer",
     "src/clientreport.py",
     '    wanted = {str(s).strip() for s in requested if str(s).strip()}\n    if not wanted:\n        return list(allowed)\n    return [key for key in allowed if key in wanted]',
     '    wanted = {str(s).strip() for s in requested if str(s).strip()}\n    if not wanted:\n        return list(allowed)\n    return [key for key in wanted]',
     "tests.test_client_reports"),

    ("clientreport: print the supplier-naming appendix to a client",
     "src/clientreport.py",
     '    if template != INTERNAL:\n        entries = {k: v for k, v in entries.items()\n                   if k in CLIENT_SAFE_UNAVAILABLE}',
     '    if False:\n        entries = {k: v for k, v in entries.items()\n                   if k in CLIENT_SAFE_UNAVAILABLE}',
     "tests.test_client_reports"),

    ("api: let a client-facing role render the internal operations report",
     "src/web/api.py",
     '    if requested == clientreport.INTERNAL and not repo.may(ws.OPERATIONS_VIEW):\n        return clientreport.EXECUTIVE',
     '    if requested == clientreport.INTERNAL and False:\n        return clientreport.EXECUTIVE',
     "tests.test_client_reports"),

    ("api: let a report id from another workspace be downloaded",
     "src/web/api.py",
     '    if row is None or row.get("workspace") != repo.workspace:\n        return None',
     '    if row is None:\n        return None',
     "tests.test_client_reports tests.test_tenancy_penetration"),

    # ----------------------------------------------------------- the rest

    ("config: let production start without what it needs",
     "src/config.py",
     '    if current != PRODUCTION or present:\n        return False',
     '    if True:\n        return False',
     "tests.test_config"),

    ("api: let search read every workspace rather than the caller's",
     "src/web/api.py",
     '    mine = ws.workspaces_for(email)\n    if workspace:',
     '    mine = ws.workspaces()\n    if workspace:',
     "tests.test_tenancy_penetration"),

    ("store: leave a state file behind when the rest move",
     "src/store.py",
     '    for override in STATE_OVERRIDES:\n        os.environ.pop(override, None)',
     '    for override in STATE_OVERRIDES[:2]:\n        os.environ.pop(override, None)',
     "tests.test_invariants"),

    ("app: collapse a repeated form field to its first value",
     "src/web/app.py",
     '        for key, values in parsed.items():\n            if len(values) > 1:\n                fields[key + LIST_SUFFIX] = values',
     '        for key, values in parsed.items():\n            if False:\n                fields[key + LIST_SUFFIX] = values',
     "tests.test_client_reports"),

    ("app: let a workspace operator read every workspace's notifications",
     "src/web/app.py",
     '            everything = (query.get("scope") == "all"\n                          and bool(person.get("super_admin")))\n            return self._page(\n                pages.slack_notifications(',
     '            everything = query.get("scope") == "all"\n            return self._page(\n                pages.slack_notifications(',
     "tests.test_web_slack"),
    # ------------------------------- cadence experimentation
    #
    # The campaign reaching the send path, the copy variant
    # reaching the drafting path, and the five modules that
    # measure what a cadence earned and cost. Each of these was
    # verified by hand when it was written; this is where they
    # keep protecting anything.

    ('campaign wiring: campaigns.py: the index forgets a stopped campaign',
     'src/campaigns.py',
     'if campaign.get("status") == COMPLETED:\n            continue',
     'if campaign.get("status") in TERMINAL_STATUSES:\n            continue',
     'tests.test_a_campaign_intent_creates_one_campaign'),

    ('campaign wiring: campaigns.py: ambiguity picks the first campaign instead of nothing',
     'src/campaigns.py',
     'index[rid] = campaign if rid not in index else AMBIGUOUS',
     'index[rid] = index.get(rid) or campaign',
     'tests.test_campaign_cadence_wiring'),

    ('campaign wiring: campaigns.py: ambiguity picks the last campaign instead of nothing',
     'src/campaigns.py',
     'index[rid] = campaign if rid not in index else AMBIGUOUS',
     'index[rid] = campaign',
     'tests.test_campaign_cadence_wiring'),

    ('campaign wiring: campaigns.py: the approval material stops covering the cadence',
     'src/campaigns.py',
     'timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set,\n                                 campaign=campaign)\n        contacts, steps = [], []',
     'timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set)\n        contacts, steps = [], []',
     'tests.test_campaign_cadence_wiring'),

    ('campaign wiring: push.py: collect stops resolving the campaign',
     'src/push.py',
     'of_record = campaigns.by_record(campaign_rows)',
     'of_record = {}',
     'tests.test_campaign_cadence_wiring'),

    ('campaign wiring: push.py: the item stops carrying its campaign',
     'src/push.py',
     '"campaign": of_record.get(rec["id"]),',
     '"campaign": None,',
     'tests.test_campaign_cadence_wiring'),

    ("campaign wiring: push.py: the last gate ignores the item's campaign",
     'src/push.py',
     'campaign=campaign if campaign is not None else item.get("campaign"),',
     'campaign=campaign,',
     'tests.test_campaign_cadence_wiring'),

    ('campaign wiring: eligibility.py: the campaign check judges a one-record world again',
     'src/eligibility.py',
     'campaign_reason = _campaign(campaign, given_recs, config, approval_current)',
     'campaign_reason = _campaign(campaign, recs, config, approval_current)',
     'tests.test_campaign_cadence_wiring'),

    ('campaign sweep: approve: what a human is asked to approve reverts to the constant',
     'src/approve.py',
     '    timeline = cadence.build(rec, config, campaign=campaign)\n    out = []',
     '    timeline = cadence.build(rec, config)\n    out = []',
     'tests.test_campaign_cadence_sweep'),

    ('campaign sweep: approve: fully_approved judges against the constant',
     'src/approve.py',
     '    pending_steps = approvable_steps(rec, config, campaign)',
     '    pending_steps = approvable_steps(rec, config)',
     'tests.test_campaign_cadence_sweep'),

    ('campaign sweep: approve: sync_state stops passing the campaign on',
     'src/approve.py',
     '    rec["state"] = ("approved" if fully_approved(rec, config, campaign)\n                    else "drafted")',
     '    rec["state"] = ("approved" if fully_approved(rec, config)\n                    else "drafted")',
     'tests.test_campaign_cadence_sweep'),

    ("campaign sweep: approve: approve_record builds the constant's timeline",
     'src/approve.py',
     '    timeline = cadence.build(rec, config, campaign=campaign)\n    done, refused = [], []',
     '    timeline = cadence.build(rec, config)\n    done, refused = [], []',
     'tests.test_campaign_cadence_sweep'),

    ("campaign sweep: approve: pending stops resolving each record's campaign",
     'src/approve.py',
     'of_record = campaigns.by_record(campaign_rows)',
     'of_record = {}',
     'tests.test_campaign_cadence_sweep'),

    ('campaign sweep: touch: the history fallback reverts to the constant',
     'src/touch.py',
     'built = cadence.build(rec, config, campaign=campaign)',
     'built = cadence.build(rec, config)',
     'tests.test_campaign_cadence_sweep'),

    ('campaign sweep: duplicates: the batch scan drops the campaign',
     'src/duplicates.py',
     '        out.extend(for_record(rec, config, recs=recs,\n                              paused_set=paused_set, campaign=campaign))',
     '        out.extend(for_record(rec, config, recs=recs,\n                              paused_set=paused_set))',
     'tests.test_campaign_cadence_sweep'),

    ('campaign sweep: coherence: the fallback timeline drops the campaign',
     'src/coherence.py',
     '        timeline = cadence.build(rec, config, campaign=campaign)\n    steps = (timeline.get("contacts") or {}).get(contact_key) or {}',
     '        timeline = cadence.build(rec, config)\n    steps = (timeline.get("contacts") or {}).get(contact_key) or {}',
     'tests.test_campaign_cadence_sweep'),

    ('variant wire: nothing is ever assigned',
     'src/cadence.py',
     '    if not (spec or {}).get(VARIANTS_KEY):\n        return None',
     '    if True:\n        return None',
     'tests.test_variant_cadence_end_to_end'),

    ('variant wire: the recorded assignment is ignored, so traffic shifts rewrite history',
     'src/cadence.py',
     '    return variants.resolve(variant_node(spec), campaign_id, contact_key,\n                            recorded=recorded, config=config)',
     '    return variants.resolve(variant_node(spec), campaign_id, contact_key,\n                            recorded=None, config=config)',
     'tests.test_variant_cadence_end_to_end'),

    ('variant wire: a sequence with no campaign assigns anyway, unreportably',
     'src/cadence.py',
     '    campaign_id = (campaign or {}).get("campaign_id")\n    if not campaign_id:\n        return None',
     '    campaign_id = (campaign or {}).get("campaign_id") or ""',
     'tests.test_variant_cadence_end_to_end'),

    ('variant wire: the copy is resolved and never applied',
     'src/cadence.py',
     '    if entry is not None:\n        from . import variants\n\n        step = variants.apply_to_step(step, entry)',
     '    if entry is not None:\n        pass',
     'tests.test_variant_cadence_end_to_end'),

    ('variant wire: a generated step may carry variants after all',
     'src/cadence.py',
     '            if step.get("generated"):\n                raise BadCadence(\n                    f"step {key!r} is generated and carries variants. A "',
     '            if False:\n                raise BadCadence(\n                    f"step {key!r} is generated and carries variants. A "',
     'tests.test_variant_cadence_end_to_end'),

    ('variant wire: a blocking finding no longer blocks',
     'src/cadence.py',
     '            blocking = [f for f in variants.validate(variant_node(step))\n                        if f["level"] == "block"]',
     '            blocking = []',
     'tests.test_variant_cadence_end_to_end'),

    ('variant wire: the step is not passed its campaign, so nothing resolves',
     'src/cadence.py',
     '            step = expand_step(rec, contact, spec, config, accepted=accepted,\n                               context=context, campaign=campaign)',
     '            step = expand_step(rec, contact, spec, config, accepted=accepted,\n                               context=context)',
     'tests.test_variant_cadence_end_to_end'),

    ('variant wire: the node type is dropped, so results group under nothing',
     'src/cadence.py',
     '    return dict(spec, type=(spec.get("node_type")\n                            or NODE_TYPE_FOR_CHANNEL.get(spec.get("channel"))))',
     '    return dict(spec, type=None)',
     'tests.test_variant_cadence_end_to_end'),

    ('cadence replies: the last touch overall is credited, not the last before the reply',
     'src/cadencereplies.py',
     '    before = [row for row in steps if _at(row.get("at")) <= when]',
     '    before = list(steps)',
     'tests.test_cadence_replies'),

    ('cadence replies: a reply that followed nothing is credited to step one',
     'src/cadencereplies.py',
     '    if not before or not when:\n        return None',
     '    if not before or not when:\n        return steps[0] if steps else None',
     'tests.test_cadence_replies'),

    ('cadence replies: the boundary flips, so a reply at the same instant loses its step',
     'src/cadencereplies.py',
     '    before = [row for row in steps if _at(row.get("at")) <= when]',
     '    before = [row for row in steps if _at(row.get("at")) < when]',
     'tests.test_cadence_replies'),

    ('cadence replies: the denominator becomes everybody assigned',
     'src/cadencereplies.py',
     '        exposed = [row for row in mine if row["started"]]',
     '        exposed = list(mine)',
     'tests.test_cadence_replies'),

    ('cadence replies: messages are counted instead of people',
     'src/cadencereplies.py',
     '        counted = list(first.values())',
     '        counted = list(theirs)',
     'tests.test_cadence_replies'),

    ('cadence replies: the last reply is counted instead of the first',
     'src/cadencereplies.py',
     '        for row in sorted(theirs, key=lambda r: _at(r["at"])):\n            first.setdefault((row["record_id"], row["contact_key"]), row)',
     '        for row in sorted(theirs, key=lambda r: _at(r["at"])):\n            first[(row["record_id"], row["contact_key"])] = row',
     'tests.test_cadence_replies'),

    ('cadence replies: steps seen becomes what was planned rather than what was reached',
     'src/cadencereplies.py',
     '            "steps_seen": order.get(key) or 0,',
     '            "steps_seen": exposure["planned"],',
     'tests.test_cadence_replies'),

    ('cadence replies: positive-only stops filtering',
     'src/cadencereplies.py',
     '                  and (row["positive"] if positive_only else True)]',
     '                  and True]',
     'tests.test_cadence_replies'),

    ('cadence value: the denominator becomes everybody in the arm',
     'src/cadencevalue.py',
     '        reached = [row for row in rows if row["reached"] >= index]',
     '        reached = list(rows)',
     'tests.test_cadence_value'),

    ('cadence value: the denominator becomes only those who finished',
     'src/cadencevalue.py',
     '        reached = [row for row in rows if row["reached"] >= index]',
     '        reached = [row for row in rows if row["reached"] >= len(planned)]',
     'tests.test_cadence_value'),

    ('cadence value: an empty column becomes evidence that the step earns nothing',
     'src/cadencevalue.py',
     '    if reached >= minimum:\n        return NO_EVIDENCE\n    return TOO_FEW',
     '    return NO_EVIDENCE',
     'tests.test_cadence_value'),

    ('cadence value: an arm with no replies at all reports settling after step zero',
     'src/cadencevalue.py',
     '            if index == 0:\n                return None, ("nothing arrived after any step; this is not a "\n                              "settling point, it is an arm with no replies")',
     '            if False:\n                return None, ("nothing arrived after any step; this is not a "\n                              "settling point, it is an arm with no replies")',
     'tests.test_cadence_value'),

    ('cadence value: the settling point is the first dead step rather than the last live one',
     'src/cadencevalue.py',
     '            settled = steps[index - 1]',
     '            settled = steps[index]',
     'tests.test_cadence_value'),

    ('cadence value: messages are counted instead of people',
     'src/cadencevalue.py',
     '    counted = list(first.values())',
     '    counted = list(answers)',
     'tests.test_cadence_value'),

    ('cadence value: the cumulative rate uses the same shrinking denominator',
     'src/cadencevalue.py',
     '            "cumulative_rate": (running / len(exposed)) if exposed else None,',
     '            "cumulative_rate": (running / len(reached)) if reached else None,',
     'tests.test_cadence_value'),

    ('cadence value: positive-only stops filtering',
     'src/cadencevalue.py',
     '               and (row["positive"] if positive_only else True)]',
     '               and True]',
     'tests.test_cadence_value'),

    ('cadence safety: a bounce becomes harm',
     'src/cadencesafety.py',
     'HARM = (UNSUBSCRIBED, STOPPED, ACCOUNT_SUPPRESSED, NEGATIVE_REPLY)',
     'HARM = (UNSUBSCRIBED, STOPPED, ACCOUNT_SUPPRESSED, NEGATIVE_REPLY,\n        BOUNCED, HELD, DROPPED)',
     'tests.test_cadence_safety'),

    ('cadence safety: events are counted instead of people',
     'src/cadencesafety.py',
     '        harmed = {(row["record_id"], row["contact_key"])\n                  for row in theirs if row["harm"]}',
     '        harmed = [row for row in theirs if row["harm"]]',
     'tests.test_cadence_safety'),

    ('cadence safety: the denominator becomes everybody assigned',
     'src/cadencesafety.py',
     '        exposed = [row for row in mine if row["started"]]',
     '        exposed = list(mine)',
     'tests.test_cadence_safety'),

    ('cadence safety: an outcome is placed after the last step overall',
     'src/cadencesafety.py',
     '        after = cadencereplies.attribute_to_step(entry.get("at"), steps)',
     '        after = steps[-1] if steps else None',
     'tests.test_cadence_safety'),

    ('cadence safety: a record-level suppression stops counting',
     'src/cadencesafety.py',
     '        who = entry.get("contact")\n        if who and who != contact_key:\n            continue',
     '        who = entry.get("contact")\n        if who != contact_key:\n            continue',
     'tests.test_cadence_safety'),

    ('cadence safety: the comparison names a winner on overlapping intervals',
     'src/cadencesafety.py',
     '        clear = [row for row in rest if row["low"] > best["high"]]',
     '        clear = [row for row in rest if row["rate"] > best["rate"]]',
     'tests.test_cadence_safety'),

    ('cadence safety: an arm nobody started joins the comparison',
     'src/cadencesafety.py',
     '    measured = {k: v for k, v in arms.items() if v["exposed"]}',
     '    measured = dict(arms)',
     'tests.test_cadence_safety'),

    ('cadence safety: a negative reply stops counting as harm',
     'src/cadencesafety.py',
     '        if reply.get("classification") in ("negative", "unsubscribe"):',
     '        if False:',
     'tests.test_cadence_safety'),

    ('cadence report: maturity stops gating the verdict',
     'src/cadencereport.py',
     '    if not maturity["comparable"]:\n        refusals.append({\n            "code": IMMATURE, "label": REFUSAL_LABEL[IMMATURE],',
     '    if False:\n        refusals.append({\n            "code": IMMATURE, "label": REFUSAL_LABEL[IMMATURE],',
     'tests.test_cadence_report'),

    ('cadence report: a leader is named even when something refused',
     'src/cadencereport.py',
     '        "leader": leader if actionable else None,',
     '        "leader": leader,',
     'tests.test_cadence_report'),

    ('cadence report: anything short of a winner counts as one',
     'src/cadencereport.py',
     '    if evaluation["state"] != variants.WINNER:',
     '    if evaluation["state"] == variants.PAUSED:',
     'tests.test_cadence_report'),

    ('cadence report: the safety veto is dropped',
     'src/cadencereport.py',
     '    if leader and leader in (safety.get("costs_more") or []):',
     '    if False:',
     'tests.test_cadence_report'),

    ('cadence report: actionable no longer depends on the refusals',
     'src/cadencereport.py',
     '    actionable = not refusals',
     '    actionable = evaluation["state"] == variants.WINNER',
     'tests.test_cadence_report'),

    ('cadence report: the cadence threshold override is ignored',
     'src/cadencereport.py',
     '    override = ((config or {}).get("cadence_experiments") or {})\n    if not override:\n        return config',
     '    override = {}\n    if not override:\n        return config',
     'tests.test_cadence_report'),

    ('cadence report: the override discards the rest of the config',
     'src/cadencereport.py',
     '    merged = dict(config or {})\n    merged["experiments"] = {**((config or {}).get("experiments") or {}),\n                             **override}',
     '    merged = {}\n    merged["experiments"] = dict(override)',
     'tests.test_cadence_report'),

    ('cadence report: the headline leads with the verdict whatever refused',
     'src/cadencereport.py',
     '    if actionable:\n        return f"{evaluation[\'why\']}."',
     '    if True:\n        return f"{evaluation[\'why\']}."',
     'tests.test_cadence_report'),

    ('cadence report: the arms are evaluated on assigned rather than exposed',
     'src/cadencereport.py',
     '    return {arm_id: {"exposures": row["exposed"], objective: row["replies"]}',
     '    return {arm_id: {"exposures": row["assigned"], objective: row["replies"]}',
     'tests.test_cadence_report'),

    # ----------------------------- cadence experimentation, owed
    #
    # The sequence, the arms, exposure and maturity. Each was
    # verified by hand when it was written and never recorded,
    # which meant none of them protected anything the next day.

    ("cadence sequence: the campaign's own sequence is ignored",
     'src/cadence.py',
     '        steps = (campaign or {}).get(CADENCE_KEY)',
     '        steps = None',
     'tests.test_cadence_sequence'),

    ('cadence sequence: the assigned arm is ignored',
     'src/cadence.py',
     '        steps = cadencearms.steps_for(campaign, rec, contact, config)',
     '        steps = None',
     'tests.test_cadence_arms'),

    ('cadence sequence: a resolved sequence is returned unvalidated',
     'src/cadence.py',
     '    return validate_steps(steps)',
     '    return tuple(steps)',
     'tests.test_cadence_sequence'),

    ('cadence sequence: two steps may share a key',
     'src/cadence.py',
     '        if key in seen:\n            raise BadCadence(',
     '        if False:\n            raise BadCadence(',
     'tests.test_cadence_sequence'),

    ('cadence sequence: the days need not ascend',
     'src/cadence.py',
     '        if last_day is not None and day < last_day:',
     '        if False:',
     'tests.test_cadence_sequence'),

    ('cadence sequence: a step may be on a channel this build cannot send',
     'src/cadence.py',
     '        if step["channel"] not in ("email", "linkedin"):',
     '        if False:',
     'tests.test_cadence_sequence'),

    ('cadence sequence: an empty sequence is accepted rather than refused',
     'src/cadence.py',
     '    if not isinstance(steps, (list, tuple)) or not steps:',
     '    if not isinstance(steps, (list, tuple)):',
     'tests.test_cadence_sequence'),

    ('cadence arms: a recorded assignment stops outranking the split',
     'src/cadencearms.py',
     '    already = recorded(exp, rec, contact)\n    if already and already.get("arm_id"):',
     '    already = None\n    if already and already.get("arm_id"):',
     'tests.test_cadence_arms'),

    ('cadence arms: shares are not renormalised across eligible arms',
     'src/cadencearms.py',
     '        running += shares.get(entry["arm_id"], 0.0) / total',
     '        running += shares.get(entry["arm_id"], 0.0)',
     'tests.test_cadence_arms'),

    ('cadence arms: an ineligible arm is offered anyway',
     'src/cadencearms.py',
     '    open_arms = eligible_arms(exp, contact) if contact is not None \\\n        else arms_of(exp)',
     '    open_arms = arms_of(exp)',
     'tests.test_cadence_arms'),

    ('cadence arms: a strict arm is assigned to a contact missing its channel',
     'src/cadencearms.py',
     '    if entry.get("mode") != ADAPTIVE:',
     '    if False:',
     'tests.test_cadence_arms'),

    ('cadence arms: the bucket forgets which allocation produced it',
     'src/cadencearms.py',
     '    material = f"{experiment_id}|{unit_key}|{version}"',
     '    material = f"{experiment_id}|{unit_key}"',
     'tests.test_cadence_arms'),

    ('cadence arms: the bucket forgets the experiment, correlating unrelated tests',
     'src/cadencearms.py',
     '    material = f"{experiment_id}|{unit_key}|{version}"',
     '    material = f"{unit_key}|{version}"',
     'tests.test_cadence_arms'),

    ('cadence arms: arm_by_id returns the first arm rather than the named one',
     'src/cadencearms.py',
     '        if entry.get("arm_id") == arm_id:\n            return entry',
     '        return entry',
     'tests.test_cadence_arms'),

    ('cadence arms: steps_for creates an assignment instead of reading one',
     'src/cadencearms.py',
     '    already = recorded(exp, rec, contact)\n    if not already:\n        return None',
     '    already = recorded(exp, rec, contact) or assign(exp, rec, contact)\n    if not already:\n        return None',
     'tests.test_cadence_arms'),

    ('cadence arms: an arm whose id is unknown resolves to some other arm',
     'src/cadencearms.py',
     '    entry = arm_by_id(exp, already.get("arm_id"))\n    if entry is None:\n        return None',
     '    entry = arm_by_id(exp, already.get("arm_id")) or arms_of(exp)[0]\n    if entry is None:\n        return None',
     'tests.test_cadence_arms'),

    ('cadence exposure: the same step counts twice',
     'src/cadenceexposure.py',
     '        if not key or key in seen:\n            continue',
     '        if not key:\n            continue',
     'tests.test_cadence_exposure'),

    ("cadence exposure: another sequence's confirmed steps are borrowed",
     'src/cadenceexposure.py',
     '    mine = [row for row in confirmed if row.get("step") in set(keys)]',
     '    mine = list(confirmed)',
     'tests.test_cadence_exposure'),

    ('cadence exposure: a contact who received nothing has started',
     'src/cadenceexposure.py',
     '        "started": reached > 0,',
     '        "started": True,',
     'tests.test_cadence_exposure'),

    ('cadence exposure: a partial run is reported as completed',
     'src/cadenceexposure.py',
     '    elif reached >= len(planned):',
     '    elif reached >= 1:',
     'tests.test_cadence_exposure'),

    ('cadence exposure: a sequence stopped early is reported as still running',
     'src/cadenceexposure.py',
     '    elif stopped:\n        state = STOPPED_EARLY',
     '    elif False:\n        state = STOPPED_EARLY',
     'tests.test_cadence_exposure'),

    ('cadence exposure: a finished run is marked censored, biasing every rate',
     'src/cadenceexposure.py',
     '        "censored": bool(stopped) and reached < len(planned),',
     '        "censored": bool(stopped),',
     'tests.test_cadence_exposure'),

    ('cadence exposure: a safety stop is reported as an outcome',
     'src/cadenceexposure.py',
     '        "censored_by": ("outcome" if stopped in OUTCOMES\n                        else "safety" if stopped in SAFETY else None),',
     '        "censored_by": ("outcome" if stopped else None),',
     'tests.test_cadence_exposure'),

    ('cadence exposure: a removal request is reported as the reply that preceded it',
     'src/cadenceexposure.py',
     '    if rec.get("state") == "dropped":\n        return DROPPED',
     '    if replies:\n        return REPLIED\n    if rec.get("state") == "dropped":\n        return DROPPED',
     'tests.test_cadence_exposure'),

    ('cadence maturity: the experiment is as mature as its fastest arm',
     'src/cadencematurity.py',
     '    level = min((row["level"] for row in arms), key=lambda x: RANK[x]) \\\n        if arms else IMMATURE',
     '    level = max((row["level"] for row in arms), key=lambda x: RANK[x]) \\\n        if arms else IMMATURE',
     'tests.test_cadence_maturity'),

    ('cadence maturity: every arm is given the same span',
     'src/cadencematurity.py',
     '    days = [int(step.get("day") or 0) for step in (arm or {}).get("steps") or []]\n    return max(days) if days else 0',
     '    return 12',
     'tests.test_cadence_maturity'),

    ('cadence maturity: a sequence that ended is still waiting for its last step',
     'src/cadencematurity.py',
     '        "had_full_chance": bool(ended or (age is not None and age >= span)),',
     '        "had_full_chance": bool(age is not None and age >= span),',
     'tests.test_cadence_maturity'),

    ('cadence maturity: an arm nobody is in is vacuously mature',
     'src/cadencematurity.py',
     '    if not total:\n        level = IMMATURE',
     '    if not total:\n        level = MATURE',
     'tests.test_cadence_maturity'),

    ('cadence maturity: one finished contact out of thirty makes a cohort readable',
     'src/cadencematurity.py',
     '    elif share >= float(policy["partial_at"]):',
     '    elif share >= 0.0:',
     'tests.test_cadence_maturity'),

    ('cadence maturity: the settling period is dropped',
     'src/cadencematurity.py',
     '    span = arm_span(arm) + int(policy["settling_days"])',
     '    span = arm_span(arm)',
     'tests.test_cadence_maturity'),

    ('cadence maturity: an immature experiment is comparable anyway',
     'src/cadencematurity.py',
     '        "comparable": level == MATURE,',
     '        "comparable": True,',
     'tests.test_cadence_maturity'),

    ('cadence maturity: an unassigned contact holds every arm immature',
     'src/cadencematurity.py',
     '    if exposure is None:\n        return None',
     '    if exposure is None:\n        exposure = {}',
     'tests.test_cadence_maturity'),

    ('cadence exposure: both halves of the confirmation guard go, so a plan becomes a touch',
     'src/cadenceexposure.py',
     '    for row in account.touches(rec, contact_key, confirmed_only=True):\n        key = row.get("step")\n        if not key or key in seen:\n            continue\n        # Said twice, on purpose, exactly as `push.verify_before_payload`\n        # says its verification rule twice. `confirmed_only=True` above\n        # already filters this, so neither check can fire while the other\n        # holds - and removing either one alone changes nothing, which a\n        # mutation run confirms.\n        #\n        # It is here because this is where the invariant lives: a step\n        # that did not reach somebody is not exposure. A future caller\n        # that assembled rows by hand, or a refactor that loosened\n        # `touches`, would still meet it. A guard that exists once is a\n        # guard one refactor away from gone.\n        if row.get("state") not in touch.CONFIRMED_STATES:\n            continue\n',
     '    for row in account.touches(rec, contact_key):\n        key = row.get("step")\n        if not key or key in seen:\n            continue\n',
     'tests.test_cadence_exposure'),

    ('cadence exposure: an unassigned contact is put in the first arm rather than left out',
     'src/cadenceexposure.py',
     '    assignment = cadencearms.recorded(exp, rec, contact)\n    if not assignment:\n        return None',
     "    assignment = cadencearms.recorded(exp, rec, contact)\n    if not assignment:\n        assignment = {'arm_id': cadencearms.arms_of(exp)[0]['arm_id']}",
     'tests.test_cadence_exposure'),

    # ------------------------- cadence experimentation, authoring
    #
    # The first link. Eight modules read the experiment off a
    # campaign and nothing wrote it, so none of them could run.

    ('cadence authoring: a malformed experiment is stored without validation',
     'src/orchestrator.py',
     '    cadencearms.require(experiment)',
     '    pass',
     'tests.test_cadence_experiment_authoring'),

    ('cadence authoring: a launched campaign may have its arms changed under people',
     'src/orchestrator.py',
     '    if (campaign.get("launch") or {}).get("state") == "launched":',
     '    if False:',
     'tests.test_cadence_experiment_authoring'),

    ('cadence authoring: an arm somebody is in may be removed',
     'src/orchestrator.py',
     '    orphaned = _orphaned_arms(campaign, experiment, recs)\n    if orphaned:',
     '    orphaned = []\n    if orphaned:',
     'tests.test_cadence_experiment_authoring'),

    ('cadence authoring: the experiment may be cleared out from under an assignment',
     'src/orchestrator.py',
     '    assigned = _assigned_arms(campaign, existing, recs)\n    if assigned:',
     '    assigned = set()\n    if assigned:',
     'tests.test_cadence_experiment_authoring'),

    ('cadence authoring: a viewer may set an experiment',
     'src/orchestrator.py',
     '    roles.require(role, roles.CHANGE_MAPPING, by)\n    cadencearms.require(experiment)',
     '    cadencearms.require(experiment)',
     'tests.test_cadence_experiment_authoring'),

    ('cadence authoring: preparing no longer puts anybody in an arm',
     'src/orchestrator.py',
     '    assigned = assign_cadence_arms(campaign, recs)',
     '    assigned = 0',
     'tests.test_cadence_experiment_authoring'),

    ('cadence authoring: assignment reaches records outside the campaign',
     'src/orchestrator.py',
     '        if rec.get("id") not in ids:\n            continue\n        before = cadencearms.recorded(exp, rec)',
     '        if False:\n            continue\n        before = cadencearms.recorded(exp, rec)',
     'tests.test_cadence_experiment_authoring'),

    ('cadence authoring: a second prepare rewrites an existing assignment',
     'src/orchestrator.py',
     '        before = cadencearms.recorded(exp, rec)\n        cadencearms.assign(exp, rec)',
     '        before = cadencearms.recorded(exp, rec)\n        rec.pop(cadencearms.ASSIGNMENT_KEY, None)\n        cadencearms.assign(exp, rec)',
     'tests.test_cadence_experiment_authoring'),

    # ------------------------------ cadence experimentation, tenancy
    #
    # These modules are pure over the records their caller hands
    # them, which is what makes a tenant-scoped caller's scope the
    # only scope. One store.load() inside any of them would widen
    # every caller to the whole estate and no call site would look
    # any different.

    ('cadence tenancy: exposure reads the estate instead of its argument',
     'src/cadenceexposure.py',
     'def exposures(exp, recs, campaign=None):',
     'def exposures(exp, recs, campaign=None):\n    from . import store\n    recs = store.load() or recs',
     'tests.test_cadence_tenancy'),

    ('cadence tenancy: safety reads the estate instead of its argument',
     'src/cadencesafety.py',
     'def outcomes_for(exp, recs, campaign=None):',
     'def outcomes_for(exp, recs, campaign=None):\n    from . import store\n    recs = store.load() or recs',
     'tests.test_cadence_tenancy'),

    # -------------------------------------------- what the process refuses
    #
    # Sign-in on this build is picking an email out of a list. Two things
    # refuse on the strength of that one fact, and the fact itself is
    # mutated first: if `sign_in_proves_identity()` can quietly become
    # True, both refusals lift at once and nothing else here would notice.

    ('startup: signing in suddenly proves who somebody is',
     'src/web/security.py',
     'def sign_in_proves_identity():',
     'def sign_in_proves_identity():\n    return True',
     'tests.test_startup_refusals tests.test_deployment_config'),

    ('startup: the empty host is treated as loopback',
     'src/web/app.py',
     'LOOPBACK = ("127.0.0.1", "::1", "localhost")',
     'LOOPBACK = ("127.0.0.1", "::1", "localhost", "")',
     'tests.test_startup_refusals'),

    ('startup: serve stops checking where it is about to answer',
     'src/web/app.py',
     '    check_configuration(host, demo)\n    STATE["demo"] = bool(demo)',
     '    STATE["demo"] = bool(demo)',
     'tests.test_startup_refusals tests.test_deployment_config'),

    ('startup: the environment check nothing was calling stops being called',
     'src/web/app.py',
     '    app_config.verify()\n\n    if security.sign_in_proves_identity():',
     '    if security.sign_in_proves_identity():',
     'tests.test_startup_refusals'),

    ('demo separation: planted experiment totals answer a real workspace',
     'src/web/api.py',
     '    if graph is None and not demo:',
     '    if False:',
     'tests.test_demo_mode'),

    # ------------------------------------------- who this person actually is
    #
    # Authentication answers "who is this" and the membership table answers
    # "what may they do". The mutations below attack both halves and the
    # seam between them, because the interesting failure is not a broken
    # token check - it is a token check that passes and then hands the
    # answer to something that does not look it up.

    ('auth: an unknown AUTH_PROVIDER quietly falls back to demo sign-in',
     'src/web/security.py',
     '    if provider != OIDC_SIGN_IN:\n        raise AuthNotConfigured(',
     '    if False:\n        raise AuthNotConfigured(',
     'tests.test_startup_refusals tests.test_production_auth'),

    ('auth: a half-configured identity provider is accepted',
     'src/web/security.py',
     '    missing = [name for name in OIDC_SETTINGS if not configured(name)]',
     '    missing = []',
     'tests.test_startup_refusals'),

    ('auth: the sign-in state is not consumed, so a callback can be replayed',
     'src/web/security.py',
     '        found = self._by_state.pop(str(state or ""), None)',
     '        found = self._by_state.get(str(state or ""), None)',
     'tests.test_production_auth'),

    ('auth: a sign-in that sat open too long is still accepted',
     'src/web/security.py',
     '        if now - found["started_at"] > self._window():\n            return None',
     '        if False:\n            return None',
     'tests.test_production_auth'),

    ('auth: abandoned sign-ins are never pruned',
     'src/web/security.py',
     '        self._prune(now)\n        self._by_state[flow["state"]]',
     '        self._by_state[flow["state"]]',
     'tests.test_production_auth'),

    ('auth: the authorization code is written to the access log',
     'src/web/app.py',
     '    if "?" not in line:\n        return line',
     '    if True:\n        return line',
     'tests.test_production_auth'),

    ('auth: the session cookie goes back to SameSite=Strict',
     'src/web/security.py',
     'flags = "Path=/; HttpOnly; SameSite=Lax"',
     'flags = "Path=/; HttpOnly; SameSite=Strict"',
     'tests.test_production_auth'),

    ('auth: the session cookie loses its Secure flag',
     'src/web/security.py',
     '    if secure:\n        flags += "; Secure"',
     '    if False:\n        flags += "; Secure"',
     'tests.test_startup_refusals'),

    ('auth: a token answering a different sign-in is accepted (nonce)',
     'src/web/oidc.py',
     '    if not hmac.compare_digest(str(found.get("nonce") or ""),\n'
     '                               str(flow.get("nonce") or "")):',
     '    if False:',
     'tests.test_production_auth'),

    ('auth: a token minted for another client is accepted (audience)',
     'src/web/oidc.py',
     '    if client_id not in audience:',
     '    if False:',
     'tests.test_production_auth'),

    ('auth: a token from another issuer is accepted',
     'src/web/oidc.py',
     '    if issuer and found.get("iss") != issuer:',
     '    if False:',
     'tests.test_production_auth'),

    ('auth: an expired id_token is accepted',
     'src/web/oidc.py',
     '    if float(expiry) <= now:',
     '    if False:',
     'tests.test_production_auth'),

    ('auth: an address the provider never verified is accepted',
     'src/web/oidc.py',
     '    if found.get("email_verified") is not True:',
     '    if False:',
     'tests.test_production_auth'),

    ('auth: a domain outside AUTH_ALLOWED_DOMAINS is accepted',
     'src/web/oidc.py',
     '        if domain not in {d.strip().lower() for d in allowed_domains if d.strip()}:',
     '        if False:',
     'tests.test_production_auth'),

    # The id_token's signature is deliberately not verified, and TLS from
    # the issuer is the entire reason that is sound. These two are the
    # precondition, so the argument cannot quietly stop holding.

    ('auth: a plaintext channel is accepted, so the id_token is trusted over http',
     'src/web/oidc.py',
     '    raise AuthError(\n        f"{what} must be https',
     '    return url\n    raise AuthError(\n        f"{what} must be https',
     'tests.test_production_auth'),

    ('auth: any hostname containing "localhost" counts as loopback',
     'src/web/oidc.py',
     '    return host in ("127.0.0.1", "localhost", "::1")',
     '    return "localhost" in host or host == "127.0.0.1"',
     'tests.test_production_auth'),

    # Authentication is not authorisation. A provider that is perfectly
    # happy about somebody says nothing about whether they work here.

    ('auth: a proved address is given a session without consulting the roster',
     'src/web/app.py',
     '        person = workspaces.user(email)\n'
     '        if person is None:\n'
     '            raise NoSuchIdentity("no such user: " + (email or "none"), 400)\n'
     '        mine = workspaces.workspaces_for(email)\n'
     '        if not mine:\n'
     '            raise NoSuchIdentity(email + " is not a member of any workspace",\n'
     '                                 403)',
     '        mine = workspaces.workspaces_for(email) or [{"slug": "productive"}]',
     'tests.test_production_auth'),

    ('auth: the demo sign-in form answers while a provider is configured',
     'src/web/app.py',
     '            if mode == security.OIDC_SIGN_IN:\n                if method == "POST":',
     '            if False:\n                if method == "POST":',
     'tests.test_production_auth'),

    ('auth: the refusal page names which check failed',
     'src/web/app.py',
     '        raise Handled(401, pages.provider_login_page(\n'
     '            error="Sign-in could not be completed. Please try again."))',
     '        raise Handled(401, pages.provider_login_page(error=str(error)))',
     'tests.test_production_auth'),

    ('auth: the token URL is built from the issuer instead of discovered',
     'src/web/oidc.py',
     '    endpoint = require_tls(document["token_endpoint"], "the token endpoint")',
     '    endpoint = require_tls(document["issuer"] + "/token", "the token endpoint")',
     'tests.test_production_auth'),

    ('auth: the consent screen asks for a scope nothing reads',
     'src/web/oidc.py',
     'SCOPE = "openid email"',
     'SCOPE = "openid email profile"',
     'tests.test_production_auth'),

    ('import: the title column is dropped again',
     'src/web/upload.py',
     'CONTACT_COLUMNS = ("email", "linkedin", "name", "first_name", "last_name",\n                   "title")',
     'CONTACT_COLUMNS = ("email", "linkedin", "name", "first_name", "last_name")',
     'tests.test_import_title'),

    # ------------------------------------------------------- invitations
    #
    # An invitation grants nothing until an identity provider proves the
    # exact address it names. Every mutation here is an attempt to make it
    # grant something sooner, to somebody else, or somewhere else.

    ('invite: the demo form can consume an invitation',
     'src/web/app.py',
     '        if proved:\n            workspaces.consume_invitations(email, subject=subject)',
     '        if True:\n            workspaces.consume_invitations(email, subject=subject)',
     'tests.test_invitations tests.test_production_auth tests.test_web_security'),

    ('invite: consumption stops matching on the exact address',
     'src/workspaces.py',
     '    pending = [i for i in invitations(email=email, status=PENDING, rows=rows)]',
     '    pending = [i for i in invitations(status=PENDING, rows=rows)]',
     'tests.test_invitations tests.test_production_auth'),

    ('invite: a revoked invitation is consumed anyway',
     'src/workspaces.py',
     '    pending = [i for i in invitations(email=email, status=PENDING, rows=rows)]',
     '    pending = [i for i in invitations(email=email, rows=rows)]',
     'tests.test_invitations'),

    ('invite: super_admin becomes assignable from a workspace',
     'src/workspaces.py',
     '    return tuple(r for r in ROLES if r != SUPER_ADMIN)',
     '    return tuple(ROLES)',
     'tests.test_invitations'),

    ('invite: the role is no longer checked against the assignable set',
     'src/workspaces.py',
     '    if role not in assignable_roles():',
     '    if False:',
     'tests.test_invitations'),

    ('invite: an invited user is created as a super admin',
     'src/workspaces.py',
     '        add_user(email, email, super_admin=False, actor="invitation")',
     '        add_user(email, email, super_admin=True, actor="invitation")',
     'tests.test_invitations'),

    ('invite: consumption activates a workspace the invitation did not name',
     'src/workspaces.py',
     '        assign(email, entry["workspace"], entry["role"],',
     '        assign(email, "productive", entry["role"],',
     'tests.test_invitations'),

    ('invite: the invitation is never marked consumed',
     'src/workspaces.py',
     '                entry["status"] = ACCEPTED',
     '                entry["status"] = PENDING',
     'tests.test_invitations'),

    ('invite: email normalisation stops lowering case',
     'src/workspaces.py',
     '    return str(value or "").strip().lower()',
     '    return str(value or "")',
     'tests.test_invitations'),

    ('invite: the endpoint stops requiring users.manage',
     'src/web/app.py',
     '        if path == "/users/add":\n            security.require(session, workspaces.USERS_MANAGE)',
     '        if path == "/users/add":',
     'tests.test_production_auth'),

    ('invite: a workspace named in the form decides the target',
     'src/web/app.py',
     '                result = workspaces.invite(email, repo.workspace, role,',
     '                result = workspaces.invite(email, fields.get("workspace") or repo.workspace, role,',
     'tests.test_production_auth'),

    # ------------------------------------------- the first administrator
    #
    # The one path in this system that grants SUPER_ADMIN. It trusts the
    # audit log rather than its own argument, and every mutation here is an
    # attempt to make it trust the argument instead.

    ('bootstrap: an address that never signed in can become super admin',
     'src/workspaces.py',
     '    if email not in proved:',
     '    if False:',
     'tests.test_bootstrap'),

    ('bootstrap: it runs again once an administrator exists',
     'src/workspaces.py',
     '    existing = users()\n    if existing:\n        return None',
     '    existing = users()',
     'tests.test_bootstrap'),

    ('bootstrap: a failed sign-in counts as a proved identity',
     'src/workspaces.py',
     '        if row.get("action") != IDENTITY_PROVED:',
     '        if False:',
     'tests.test_bootstrap'),

    ('bootstrap: the workspace requirement is dropped',
     'src/workspaces.py',
     '    if not workspace_slug:',
     '    if False:',
     'tests.test_bootstrap'),

    ('bootstrap: a workspace with no client config is created anyway',
     'src/workspaces.py',
     '        raise BootstrapRefused(\n'
     '            f"workspace {workspace_slug!r} needs config/clients/{client}.yaml "',
     '        pass\n'
     '    if False:\n'
     '        raise BootstrapRefused(\n'
     '            f"workspace {workspace_slug!r} needs config/clients/{client}.yaml "',
     'tests.test_bootstrap'),

    ('auth: a proved identity is written to the audit log as a refusal',
     'src/web/app.py',
     '            self._auth_note(workspaces.IDENTITY_PROVED, proved["email"],',
     '            self._auth_note(workspaces.IDENTITY_REFUSED, proved["email"],',
     'tests.test_production_auth'),

    ('persistence: production no longer requires somewhere durable to write',
     'src/config.py',
     '    ("QUEUE", PRODUCTION_ONLY, "state",',
     '    ("QUEUE", OPTIONAL, "state",',
     'tests.test_config tests.test_startup_refusals'),

    ('auth: the sign-in page enumerates every known user again',
     'src/web/app.py',
     '                raise Handled(200, pages.provider_login_page())',
     '                raise Handled(200, pages.login_page(workspaces.users()))',
     'tests.test_production_auth'),

    # ---------------------------------------------- reading one reply

    ('replies: a hand-off phrase pointing at nobody is a referral',
     'src/replies.py',
     '    found = referral.evidence(body)\n    return bool(found["names"] or found["emails"] or found["profiles"])',
     '    found = referral.evidence(body)\n    return True',
     'tests.test_referral'),

    ('replies: a referral outranks the readings that stop a cadence',
     'src/replies.py',
     'RULES = (\n    (ACCOUNT_DNC, ACCOUNT_DNC_PATTERNS, 0.95),',
     'RULES = (\n    (REFERRAL, REFERRAL_PATTERNS, 0.8),\n    (ACCOUNT_DNC, ACCOUNT_DNC_PATTERNS, 0.95),',
     'tests.test_referral'),

    ('replies: a removal request records a mention naming a colleague',
     'src/replies.py',
     '    if (verdict["classification"] not in (UNSUBSCRIBE, ACCOUNT_DNC)\n            and mentions_referral(text)):',
     '    if mentions_referral(text):',
     'tests.test_referral'),

    ('referral: a name becomes an identity',
     'src/referral.py',
     '        if (address and address in emails) or (profile and profile in profiles):',
     '        if ((address and address in emails)\n                or (profile and profile in profiles)\n                or (contact.get("name") in found["names"])):',
     'tests.test_referral'),

    ("referral: the referrer's own signature refers to themselves",
     'src/referral.py',
     '    emails = [e for e in found["emails"] if e and e != own_email]\n    profiles = [p for p in found["profiles"] if p and p != own_profile]',
     '    emails = [e for e in found["emails"] if e]\n    profiles = [p for p in found["profiles"] if p]',
     'tests.test_referral'),

    ('tasks: a referral nobody can resolve stops being work',
     'src/tasks.py',
     '            if not entry.get("needs_a_person"):\n                continue',
     '            if False:\n                continue',
     'tests.test_referral'),

    # ---------------------------------------------- the digest schedule

    ('digestwatch: anchor the window to the clock instead of the period',
     'src/digestwatch.py',
     '        built = digest.build(workspace, since=period["since"],\n                             until=period["until"], config=config)',
     '        built = digest.build(workspace, since=period["since"],\n                             config=config)',
     'tests.test_digestwatch'),

    ('digestwatch: deliver a period that has already been delivered',
     'src/digestwatch.py',
     '    already = delivered(workspace, until.isoformat())\n    if already is not None:',
     '    already = delivered(workspace, until.isoformat())\n    if False:',
     'tests.test_digestwatch'),

    ('digestwatch: an unreadable hour quietly becomes the default',
     'src/digestwatch.py',
     '        if not 0 <= hour <= 23:',
     '        if False:',
     'tests.test_digestwatch'),

    ('digestwatch: two processes deliver the same period at once',
     'src/digestwatch.py',
     '        with store.lock(for_path=lock_file(), timeout=LOCK_WAIT):\n            done = [_one(slug, until, config["schedule"]) for slug in slugs]',
     '        done = [_one(slug, until, config["schedule"]) for slug in slugs]',
     'tests.test_digestwatch'),

    ('digestwatch: stop at planned and never attempt delivery',
     'src/digestwatch.py',
     '        attempted = notify.deliver(row["id"])',
     '        attempted = None',
     'tests.test_digestwatch'),

    ('replywatch: a failing second job stops the whole tick',
     'src/replywatch.py',
     '            try:\n                job()\n            except Exception as exc:                          # noqa: BLE001\n                self._record_failure(name, exc)',
     '            job()',
     'tests.test_digestwatch'),

    # ------------------------------------------ one person, two channels

    ('conversation: a planned step counts as one that went out',
     'src/conversation.py',
     '        after = bool(earlier) and item["confirmed"]',
     '        after = bool(earlier)',
     'tests.test_conversation'),

    ('conversation: a naive timestamp is read as UTC',
     'src/conversation.py',
     '    return parsed if parsed.tzinfo else None',
     '    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)',
     'tests.test_conversation'),

    ("conversation: another workspace's record joins the thread",
     'src/conversation.py',
     '        if other.get("client") != rec.get("client"):\n            continue',
     '        if False:\n            continue',
     'tests.test_conversation'),

    # ---------------------------------------- what a list arrives with

    ('upload: screen only the first person at each company',
     'src/web/upload.py',
     '            verdict = screen(domain, first["company"], contact)\n            if verdict is not None:',
     '            verdict = None\n            if verdict is not None:',
     'tests.test_import_hardening'),

    ('upload: read every file as comma-delimited',
     'src/web/upload.py',
     '    delimiter = sniff(text)',
     '    delimiter = ","',
     'tests.test_import_hardening'),

    ('upload: drop the cells past the last header in silence',
     'src/web/upload.py',
     '        if raw.pop(RAGGED, None) is not None:',
     '        if False:',
     'tests.test_import_hardening'),

    # ------------------------------------ stating who a client sells to

    ('workspaces: a market list is trimmed to fit instead of refused',
     'src/workspaces.py',
     '        if len(items) > spec["max_items"]:',
     '        if False:',
     'tests.test_icp_settings'),

    ('workspaces: an out-of-market answer is stored as a word, not a bool',
     'src/workspaces.py',
     '        return text == spec["choices"][0]',
     '        return text',
     'tests.test_icp_settings'),

    ('workspaces: one absurd entry is dropped rather than refusing the list',
     'src/workspaces.py',
     '            if len(part) > spec["max_length"]:',
     '            if False:',
     'tests.test_icp_settings'),

    ('workspaces: a persona with no titles is accepted',
     'src/workspaces.py',
     '        if not titles:\n            raise NotOverridable(',
     '        if False:\n            raise NotOverridable(',
     'tests.test_personas_settings'),

    ('workspaces: a persona name is taken as typed',
     'src/workspaces.py',
     '        if not PERSONA_NAME.match(key):',
     '        if False:',
     'tests.test_personas_settings'),

    ('workspaces: the per-company cap is unbounded',
     'src/workspaces.py',
     '        if not 1 <= cap <= MAX_CAP:',
     '        if False:',
     'tests.test_personas_settings'),

    ('api: editing a persona wipes the ones in the client file',
     'src/web/api.py',
     '    current = _deep(repo.config().get("personas") or {})\n    key = str(name or "").strip().lower()',
     '    current = {}\n    key = str(name or "").strip().lower()',
     'tests.test_personas_settings'),

    ('workspaces: an empty persona set is stored instead of removing it',
     'src/workspaces.py',
     '    if not raw:\n        return None',
     '    if False:\n        return None',
     'tests.test_personas_settings'),

    # ------------------------------- a referral becomes a contact

    ('referral: a name with no address can be added as a contact',
     'src/referral.py',
     '    if not emails and not profiles:',
     '    if False:',
     'tests.test_referral_promotion'),

    ('referral: somebody already on the account is added a second time',
     'src/referral.py',
     '            return {"status": ALREADY_HERE,',
     '            return {"status": READY,',
     'tests.test_referral_promotion'),

    ('referral: a suppressed person is added because a colleague named them',
     'src/referral.py',
     '        if verdict["action"] == hygiene.SUPPRESS:',
     '        if False:',
     'tests.test_referral_promotion'),

    ('api: a referred contact arrives already selected',
     'src/web/api.py',
     '        "selected": False,',
     '        "selected": True,',
     'tests.test_referral_promotion'),

    ('api: two referrals from one reply collapse into one edge',
     'src/web/api.py',
     '                       provider_event_id=f"{event_id}:added",\n',
     '',
     'tests.test_referral_promotion'),

    ('api: the promotion decision is not re-checked before writing',
     'src/web/api.py',
     '    if answer["status"] != referral.READY:\n        raise ActionRefused(answer["why"])',
     '    if False:\n        raise ActionRefused(answer["why"])',
     'tests.test_referral_promotion'),

    # ------------------------- what a list would cost to verify

    ('upload: an address we cannot send to counts as cleared',
     'src/web/upload.py',
     '        elif any(f.get("sendable") for f in seen):',
     '        elif True:',
     'tests.test_import_hardening'),

    ('upload: a person with no address counts as one needing verification',
     'src/web/upload.py',
     '        if not address:\n            counts["no_address"] += 1\n            continue',
     '        if not address:\n            counts["new"] += 1\n            continue',
     'tests.test_import_hardening'),

    ('upload: the preview claims a verification state with no history',
     'src/web/upload.py',
     '            history, policy) if history is not None else None),',
     '            history, policy)),',
     'tests.test_import_hardening'),

    ("hygiene: a contact's sendability is read from a stored flag",
     'src/hygiene.py',
     '    return bool(contact.get("email")) and lint.sendable(contact)',
     '    return bool((contact.get("verification") or {}).get("state"))',
     'tests.test_import_hardening'),

    # ------------------- a reply on one channel stops the other

    ("eligibility: the reply scan only counts the step's own channel",
     'src/eligibility.py',
     '        if events.is_reply(entry) and entry.get("contact") == key:',
     '        if (events.is_reply(entry) and entry.get("contact") == key\n                and entry.get("channel") == "email"):',
     'tests.test_lifecycle_attacks'),

    ('eligibility: the account hold stops nobody',
     'src/eligibility.py',
     '    if cadence.pause_state(rec, config):\n        return BLOCKED_COMPANY_PAUSED',
     '    if False:\n        return BLOCKED_COMPANY_PAUSED',
     'tests.test_lifecycle_attacks'),

    # ------------------- what a reply carries, not what it was read as

    ('api: the referral filter falls back to the classification',
     'src/web/api.py',
     '    if carries == CARRIES_REFERRAL:\n        shown = [r for r in shown if r.get("referral")]',
     '    if carries == CARRIES_REFERRAL:\n        shown = [r for r in shown if r["classification"] == "referral"]',
     'tests.test_inbox'),

    ('api: an unrecognised filter value empties the list',
     'src/web/api.py',
     '    if carries == CARRIES_REFERRAL:',
     '    if carries:',
     'tests.test_inbox'),

    ('api: the referral count is narrowed by the filter that uses it',
     'src/web/api.py',
     '        "referrals": len([r for r in everything if r.get("referral")]),',
     '        "referrals": len([r for r in shown if r.get("referral")]),',
     'tests.test_inbox'),

    # ------------------ one idea of a domain, one home for a column

    ('ingest: import identity keeps its own idea of a domain',
     'src/ingest.py',
     '    return dedupe.normalise_domain(d) or ""',
     '    return re.sub(r"^www\\\\.", "", d)',
     'tests.test_import_hardening tests.test_ingest'),

    ('api: the columns an import kept are dropped from the export',
     'src/web/api.py',
     '    extra = sorted({key for row in rows for key in (row.get("source") or {})})',
     '    extra = []',
     'tests.test_import_hardening'),

    ('api: a capped export drops the rest without saying so',
     'src/web/api.py',
     '    if dropped:',
     '    if False:',
     'tests.test_import_hardening'),

    # ------------------------ how old a verification actually is

    ('verification: a legacy verdict is stamped with the moment it was read',
     'src/verification.py',
     '    return [dict(entry, at=None) for entry in out]',
     '    return out',
     'tests.test_verification_age'),

    ('verification: a naive evidence timestamp is read as UTC',
     'src/verification.py',
     '    return parsed if parsed.tzinfo else None\n\n\ndef all_evidence',
     '    import datetime as _dt\n    return (parsed if parsed.tzinfo\n            else parsed.replace(tzinfo=_dt.timezone.utc))\n\n\ndef all_evidence',
     'tests.test_verification_age'),

    ('api: an undated verification exports as zero days old',
     'src/web/api.py',
     '                "oldest_evidence_days": (\n                    verification.age_of(contact)["oldest_days"]\n                    if contact.get("email") else None),',
     '                "oldest_evidence_days": (\n                    verification.age_of(contact)["oldest_days"] or 0\n                    if contact.get("email") else None),',
     'tests.test_verification_age'),

    # ----------------- a number that meant something else

    ('api: double verified counts providers asked, not confirmations',
     'src/web/api.py',
     '            if confirmed >= required:',
     '            if len(decision.get("confirmed_by") or []) or decision.get("state"):',
     'tests.test_reporting_honesty'),

    ('api: the invalid tile reads a key nothing writes',
     'src/web/api.py',
     '            if decision["state"] == verification.INVALID:\n                counts["invalid"] += 1',
     '            if (contact.get("verification") or {}).get("status") == "invalid":\n                counts["invalid"] += 1',
     'tests.test_reporting_honesty'),

    ('api: the verification tiles read the stored verdict again',
     'src/web/api.py',
     '            counts["addresses"] += 1\n            decision = verification.resolve(contact, policy)',
     '            counts["addresses"] += 1\n            decision = contact.get("verification") or {}',
     'tests.test_reporting_honesty'),

    ('report: the funnel reads the stored sendable flag again',
     'src/report.py',
     '        "verified": sum(1 for c in contacts if lint.sendable(c)),',
     '        "verified": sum(1 for c in contacts if c.get("sendable")),',
     'tests.test_reporting_honesty'),

    ('api: the sender report counts one reply twice',
     'src/web/api.py',
     '            if entry.get("type") == event_model.REPLY_RECEIVED:\n                replies_by_contact[key] = replies_by_contact.get(key, 0) + 1',
     '            if entry.get("type") in (event_model.REPLY_RECEIVED,\n                                     event_model.REPLY_CLASSIFIED):\n                replies_by_contact[key] = replies_by_contact.get(key, 0) + 1',
     'tests.test_reporting_honesty'),

    ('pages: a meeting count nothing observes prints as zero',
     'src/web/pages.py',
     '    if not value:\n        return unavailable("not tracked")',
     '    if False:\n        return unavailable("not tracked")',
     'tests.test_reporting_honesty'),

    ('pages: the pass rate loses its denominator again',
     'src/web/pages.py',
     '        row("Pass rate", _rate((conf["double_confirmed"],\n                                conf["contacts_with_an_address"])), raw=True),',
     '        row("Pass rate", conf["pass_rate"]),',
     'tests.test_reporting_honesty'),

    # ------------- five sections that were rendered and never wired

    ('api: a LinkedIn request and a message are counted together',
     'src/web/api.py',
     '            if item.get("step") == LINKEDIN_REQUEST_STEP:',
     '            if False:',
     'tests.test_report_sections'),

    ('api: a LinkedIn message is treated as proof of acceptance',
     'src/web/api.py',
     '            if event_model.is_acceptance(entry):',
     '            if (event_model.is_acceptance(entry)\n                    or (entry.get("type") == event_model.PUSH_MARKED\n                        and entry.get("channel") == "linkedin")):',
     'tests.test_report_sections'),

    ('api: an undated event is filed under the current month',
     'src/web/api.py',
     '        stamp = str(at or "")[:7]\n        if len(stamp) != 7 or stamp[4] != "-":\n            return None',
     '        stamp = str(at or "")[:7]\n        if len(stamp) != 7 or stamp[4] != "-":\n            stamp = store.now()[:7]',
     'tests.test_report_sections'),

    ('api: one company with one person worked counts as multi-contact',
     'src/web/api.py',
     '        if len(worked) > 1:\n            counts["multi_dm"] += 1',
     '        if worked:\n            counts["multi_dm"] += 1',
     'tests.test_report_sections'),

    ('api: the pipeline guesses a sender nobody assigned',
     'src/web/api.py',
     '                "sender": named,',
     '                "sender": named or "a sender",',
     'tests.test_report_sections'),

    ('api: a month counts one person once per touch',
     'src/web/api.py',
     '            found["contacted"].add((rec.get("id"), item.get("contact_key")))',
     '            found["contacted"].add((rec.get("id"),\n                                    item.get("contact_key"),\n                                    item.get("at")))',
     'tests.test_report_sections'),

    # ---------------- a number that could not be told from another

    ('report: nothing sent and nothing delivered read the same',
     'src/report.py',
     '    if not counts[events.PUSH_MARKED]:\n        return None\n    return counts[events.EMAIL_DELIVERED]',
     '    return counts[events.EMAIL_DELIVERED] or None',
     'tests.test_reporting_honesty'),

    ('clientreport: the held count includes contacts with no address',
     'src/clientreport.py',
     '    held = max(0, (with_address if with_address is not None\n                   else data.get("contacts_found") or 0) - reachable)',
     '    held = (data.get("contacts_found") or 0) - reachable',
     'tests.test_client_reports'),

    # ------------------ the file a client actually works in

    ('xlsx: a declared XML entity is parsed rather than refused',
     'src/web/xlsx.py',
     '    if DOCTYPE.search(raw):',
     '    if False:',
     'tests.test_xlsx_import'),

    ('xlsx: a zip bomb is decompressed before it is judged',
     'src/web/xlsx.py',
     '        if declared > MAX_UNPACKED:',
     '        if False:',
     'tests.test_xlsx_import'),

    ('xlsx: a zip with any number of members is walked',
     'src/web/xlsx.py',
     '        if len(names) > MAX_ENTRIES:',
     '        if False:',
     'tests.test_xlsx_import'),

    ('xlsx: anything is treated as a workbook',
     'src/web/xlsx.py',
     '    if not looks_like_xlsx(data):',
     '    if False:',
     'tests.test_xlsx_import'),

    ('upload: a workbook is joined into CSV without quoting',
     'src/web/upload.py',
     '    csv.writer(out, lineterminator="\\n").writerows(grid)',
     '    out.write("\\n".join(",".join(str(c) for c in row) for row in grid))',
     'tests.test_xlsx_import'),

    # ------------- what a reply means, and what a verifier said

    ('deliverable: a verdict is matched on a substring again',
     'src/providers/deliverable.py',
     '    if _says(label, VALID_WORDS):\n        return "unknown" if negated else "valid"',
     '    if any(w in label for w in VALID_WORDS):\n        return "valid"',
     'tests.test_deliverable'),

    ('deliverable: a negated label is read as valid',
     'src/providers/deliverable.py',
     '    negated = bool(words_of(label) & set(NEGATIONS))',
     '    negated = False',
     'tests.test_deliverable'),

    ("events: a second unclassified reply inherits the first one's verdict",
     'src/events.py',
     '        rec, contact_key, accountpolicy.UNKNOWN, config=None,',
     '        rec, contact_key, config=None,',
     'tests.test_reply_escalation'),

    ('accountpolicy: the recorded outcome is ignored on the way back out',
     'src/accountpolicy.py',
     '            recorded = str(entry.get("outcome") or "").strip().lower()',
     '            recorded = ""',
     'tests.test_reply_escalation'),

    ('accountpolicy: a classifier word is checked against policy words',
     'src/accountpolicy.py',
     '            latest = CLASSIFIER_OUTCOME.get(\n'
     '                value, value if value in OUTCOMES else UNKNOWN)',
     '            latest = value if value in OUTCOMES else UNKNOWN',
     'tests.test_reply_escalation'),

    ('replies: the policy outcome is not recorded on the classification',
     'src/replies.py',
     '        outcome=outcome,\n        confidence=verdict.get("confidence"),',
     '        confidence=verdict.get("confidence"),',
     'tests.test_reply_escalation'),

    # ------------------ the second half of an import, and its log

    ('upload: the preview offers no way to commit',
     'src/web/pages.py',
     '        if result["rows"]:\n            commit = (\n                \'<form method="post" action="/upload/commit">\'',
     '        if False:\n            commit = (\n                \'<form method="post" action="/upload/commit">\'',
     'tests.test_import_commit'),

    ('upload: the button offers a count it will not commit',
     'src/web/pages.py',
     '                f\'{esc(len(result["rows"]))} companies and \'',
     '                f\'{esc(result["uploaded"])} companies and \'',
     'tests.test_import_commit'),

    ('upload: a committed import is not audited',
     'src/web/upload.py',
     '    repo.audit("batch.committed", "batch", parsed.get("batch"),',
     '    if False:\n     repo.audit("batch.committed", "batch", parsed.get("batch"),',
     'tests.test_import_commit'),

    ('upload: the audit entry does not say how much was imported',
     'src/web/upload.py',
     '               after={"companies": len(records),\n                      "contacts": sum(len(r.get("contacts") or [])\n                                      for r in records)},',
     '               after=None,',
     'tests.test_import_commit'),

    # ------------- what a reply meant, what a run cost, who decided

    ('accountpolicy: a policy word is checked against classifier words only',
     'src/accountpolicy.py',
     '            latest = CLASSIFIER_OUTCOME.get(\n                value, value if value in OUTCOMES else UNKNOWN)',
     '            latest = CLASSIFIER_OUTCOME.get(value, UNKNOWN)',
     'tests.test_signals'),

    ('research: an actor run skips the spend ledger',
     'src/research.py',
     '    if not spend("apify-research", proposal["reason"], provider="apify",\n                 reason_code=PUBLIC_EVIDENCE_REQUIRED):\n        return []',
     '    pass',
     'tests.test_research_spend'),

    ('research: a live run with no ledger runs anyway',
     'src/research.py',
     '    if spend is None:',
     '    if False:',
     'tests.test_research_spend'),

    ("enrich: one record's failure discards the whole batch",
     'src/enrich.py',
     '            try:\n                if scrape_budget.cap is None:\n                    scrape_budget.cap = apify.settings(\n                        config)["max_runs_per_batch"]\n                done = enrich_record(rec, budget, live=True, log=notes,\n                                     config=config,\n                                     scrape_budget=scrape_budget,\n                                     mx_cache=mx_cache)\n            except Exception as e:',
     '            if scrape_budget.cap is None:\n                scrape_budget.cap = apify.settings(\n                    config)["max_runs_per_batch"]\n            done = enrich_record(rec, budget, live=True, log=notes,\n                                 config=config,\n                                 scrape_budget=scrape_budget,\n                                 mx_cache=mx_cache)\n            if False:\n              e = None\n              raise',
     'tests.test_enrich_batch'),

    ('enrich: a contained failure is not reported',
     'src/enrich.py',
     '                               "cost": 0, "failed": why})',
     '                               "cost": 0})',
     'tests.test_enrich_batch'),

    ('providers: a body of the wrong type is read as an empty one',
     'src/providers/__init__.py',
     '    raise ProviderError(\n        f"{what}: expected an object, got {type(data).__name__}")',
     '    return {}',
     'tests.test_provider_body'),

    ('contactout: a list body crashes instead of failing',
     'src/providers/contactout.py',
     '        rows = mapping(data, "contactout people").get(name)',
     '        rows = (data or {}).get(name)',
     'tests.test_provider_body'),

    ('heyreach: a list conversation crashes instead of failing',
     'src/providers/heyreach.py',
     '    conversation = mapping(conversation, "heyreach conversation")',
     '    conversation = conversation or {}',
     'tests.test_provider_body'),

    ('approvals: the page offers no way to reject',
     'src/web/pages.py',
     '        offered = [a for a in ("approve", "reject") if a != decided]',
     '        offered = [a for a in ("approve",) if a != decided]',
     'tests.test_web_reject'),

    ('approvals: a decided campaign is offered the decision it already has',
     'src/web/pages.py',
     '        decided = "" if c["stale"] else state',
     '        decided = ""',
     'tests.test_web_reject'),

    ('approvals: a rejection is counted as a stale approval',
     'src/web/api.py',
     '            "stale": ((campaign.get("approval") or {}).get("action")\n                      == "approve" and not current),',
     '            "stale": bool(campaign.get("approval")) and not current,',
     'tests.test_web_reject'),

    # --------------- what a vendor refused, and what an import kept

    ('deliverable: a transport acknowledgement is a positive verdict',
     'src/providers/deliverable.py',
     'VALID_WORDS = ("valid", "deliverable", "safe", "verified")',
     'VALID_WORDS = ("valid", "deliverable", "ok", "safe", "good", "verified")',
     'tests.test_deliverable'),

    ('verification: an explicit refusal is not counted as a negative',
     'src/verification.py',
     '    negatives |= {p for p, e in by_provider.items()\n                  if e.get("safe_to_send") is False and p in usable}\n    negatives |= {p for p, e in by_provider.items()\n                  if e.get("deliverable") is False and p in usable}',
     '    pass',
     'tests.test_verification_refusal'),

    ('verification: only safe_to_send is read, not deliverable',
     'src/verification.py',
     '    negatives |= {p for p, e in by_provider.items()\n                  if e.get("deliverable") is False and p in usable}',
     '    pass',
     'tests.test_verification_refusal'),

    ('upload: a committed record id may collide with one already in the queue',
     'src/web/upload.py',
     '        rid = base = ingest.slug(f"{row[\'domain\']}")\n        suffix = 2\n        while rid in taken:',
     '        rid = base = ingest.slug(f"{row[\'domain\']}")\n        suffix = 2\n        while False:',
     'tests.test_import_preserves_history'),

    ('upload: an account that already exists is rebuilt rather than merged',
     'src/web/upload.py',
     '        held = mine.get(str(row["domain"]).lower())\n        if held is not None:',
     '        held = mine.get(str(row["domain"]).lower())\n        if False:',
     'tests.test_import_preserves_history'),

    ('upload: an identity column is truncated instead of refused',
     'src/web/upload.py',
     '                if column in IDENTITY_COLUMNS and len(value) > MAX_CELL:',
     '                if False:',
     'tests.test_import_hardening'),

    ('upload: a new person at a known company is dropped with the company',
     'src/web/upload.py',
     '        if domain in existing and fresh and not entry["contacts"]:',
     '        if domain in existing and fresh:',
     'tests.test_import_hardening'),

    ('app: a cross-tenant refusal tells the caller the record exists',
     'src/web/app.py',
     '            self._page(pages.empty("Not found", ""), session, path,\n                       status=404)',
     '            self._page(pages.empty("Not found", str(e)), session, path,\n                       status=404)',
     'tests.test_tenancy_disclosure'),

    # ------------------------------- the two ways to stop it

    ('eligibility: a paused campaign is not stopped at the gate',
     'src/eligibility.py',
     '    if campaign.get("status") in (campaigns.PAUSED, campaigns.COMPLETED,\n                                  campaigns.FAILED):\n        return BLOCKED_CAMPAIGN_STOPPED',
     '    pass',
     'tests.test_stop_buttons'),

    ('accountpolicy: an unattributable removal request is dropped',
     'src/accountpolicy.py',
     '    elif outcome in REMOVAL_REQUESTS:',
     '    elif False:',
     'tests.test_stop_buttons'),

    ('accountpolicy: a named removal request widens to the whole account',
     'src/accountpolicy.py',
     '    if replier is not None:',
     '    if False:',
     'tests.test_stop_buttons'),

    # ------------------------- what a role may see, not only whose

    ('search: contact hits ignore whether the role may see contacts',
     'src/web/api.py',
     '        for rec in (repo.records() if may_contacts else []):',
     '        for rec in repo.records():',
     'tests.test_search_permissions'),

    ('search: campaign hits ignore whether the role may see operations',
     'src/web/api.py',
     '        for campaign in (repo.campaigns() if may_operations else []):',
     '        for campaign in repo.campaigns():',
     'tests.test_search_permissions'),

    # ------------------- proving a token, and the trap that hid it

    ('slack: the free read is gated behind the switch that arms posting',
     'src/providers/slack.py',
     '    # Deliberately not gated on `live()`.',
     '    if not live():\n        return {"provider": "Slack", "ok": None, "status": None,\n                "skipped": True, "note": "off"}\n    # Deliberately not gated on `live()`.',
     'tests.test_slack'),

    ('check: slack is left out of the provider health sweep',
     'src/check.py',
     '        slack.check(),               # auth.test, free and read-only',
     '        # slack.check(),',
     'tests.test_check'),

    ('api: a created campaign is never prepared',
     'src/web/api.py',
     '        orchestrator.prepare(campaign, mine, repo.config())',
     '        pass',
     'tests.test_campaign_reaches_the_queue'),

    ('oidc: a templated issuer is accepted and fails at sign-in instead',
     'src/web/oidc.py',
     '    if "{" in claimed and "}" in claimed:',
     '    if False:',
     'tests.test_production_auth'),

    ('poller: heyreach stops early on a page that is not descending',
     'src/poller.py',
     '            if len(fresh) < len(items) and _descending(items):',
     '            if len(fresh) < len(items):',
     'tests.test_poller_highwater'),

    ('poller: heyreach never stops early, so it reads one per cent',
     'src/poller.py',
     '            if len(fresh) < len(items) and _descending(items):',
     '            if False:',
     'tests.test_poller_highwater'),

    # ----------------- screens that reported health by not looking

    ('assignment: a paused or blocked inbox is still allocated prospects',
     'src/assignment.py',
     '                    if a.get("active") and usable_health(a)]',
     '                    if a.get("active")]',
     'tests.test_health_is_not_silence'),

    ('notify: failures are looked for inside a window of every status',
     'src/web/api.py',
     '    for row in notify.history(repo.workspace, status=notify.FAILED,\n                              limit=500):',
     '    for row in notify.history(repo.workspace, limit=500):',
     'tests.test_health_is_not_silence'),

    ('workspaces: the audit action filter runs after the limit',
     'src/workspaces.py',
     '    if action:\n        rows = [r for r in rows if r.get("action") == action]\n    return list(reversed(rows))[:limit]',
     '    return list(reversed(rows))[:limit]',
     'tests.test_health_is_not_silence'),

    ('killswitch: a frozen campaign is reported as one that would send',
     'src/killswitch.py',
     '    if campaigns.is_frozen(campaign):',
     '    if False:',
     'tests.test_health_is_not_silence'),

    ('api: the slack flag explains a state it does not have',
     'src/web/api.py',
     '         "why": ("SLACK_LIVE is set, so a post with a token reaches Slack"\n                 if os.environ.get("SLACK_LIVE")\n                 else "SLACK_LIVE is unset, so posts are planned and printed"),',
     '         "why": "SLACK_LIVE is unset, so posts are planned and printed",',
     'tests.test_health_is_not_silence'),

    ('pages: the audit page prints its page size as the total',
     'src/web/pages.py',
     '    if total is not None and total > len(entries):',
     '    if False:',
     'tests.test_health_is_not_silence'),

    # ------------- what arrived, what it cost, and what it started

    # Both guards, because either alone catches the other's mutation -
    # Both guards at once. Either alone catches the other's removal - the
    # length check refuses before reading, the short-read check refuses
    # after - and that redundancy is deliberate, so a mutation that takes
    # one is correctly not caught. This takes the protection, not a line.
    ('app: an oversized upload is truncated instead of refused',
     'src/web/app.py',
     '        if length > upload.MAX_BYTES + 4096:\n            raise PayloadTooLarge(\n                f"this request is {length // (1024 * 1024)}MB, over the "\n                f"{upload.MAX_BYTES // (1024 * 1024)}MB limit. Nothing was "\n                "read: a request that cannot arrive whole is refused rather "\n                "than truncated, because a short read looks exactly like a "\n                "smaller file")\n        raw = self.rfile.read(min(length, upload.MAX_BYTES + 4096))\n        if len(raw) < length:\n            raise PayloadTooLarge(\n                f"only {len(raw)} of {length} announced bytes arrived. "\n                "Refused rather than imported short")',
     '        raw = self.rfile.read(min(length, upload.MAX_BYTES + 4096))',
     'tests.test_upload_is_never_truncated'),

    ('enrich: the free count is skipped whenever any fact exists',
     'src/enrich.py',
     '    if "headcount_signal" not in (rec.get("company_facts") or {}):',
     '    if not rec.get("company_facts"):',
     'tests.test_enrich'),

    ('research: an actor run id is never written down',
     'src/research.py',
     '        events.record(rec, events.SCRAPE_STARTED, provider="apify",\n                      operation=proposal["actor"], reason=proposal["reason"],\n                      run_id=started.get("id"))',
     '        pass',
     'tests.test_research_spend'),

]


def drop_bytecode():
    """Delete every __pycache__ under src/ and tests/.

    Python decides a .pyc is fresh from the source's mtime and size. A
    mutation that replaces a line with one of exactly the same length, written
    inside the same second, produces a file the interpreter believes it has
    already compiled - so the *restored* source runs the *mutated* bytecode,
    and every later test in that process is quietly testing the wrong code.

    This bit once and it was convincing: eight tests failed on a file git
    reported as unmodified. Dropping the caches on both sides of a mutation is
    the fix; hoping the lengths differ is not.
    """
    for root in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tests")):
        for path, dirs, _ in os.walk(root):
            for name in list(dirs):
                if name == "__pycache__":
                    shutil.rmtree(os.path.join(path, name), ignore_errors=True)
                    dirs.remove(name)


def run(tests):
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "-q"] + tests.split(),
        capture_output=True, text=True, cwd=ROOT)
    return result.returncode == 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only", help="run only mutations whose name contains this")
    a = p.parse_args(argv)

    chosen = [m for m in MUTATIONS if not a.only or a.only in m[0]]
    caught, missed = [], []

    for name, relative, old, new, tests in chosen:
        path = os.path.join(ROOT, relative)
        original = io.open(path, encoding="utf-8").read()
        if old not in original:
            missed.append((name, "the mutation did not apply: the code moved"))
            continue
        try:
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                original.replace(old, new, 1))
            drop_bytecode()
            passed = run(tests)
        finally:
            io.open(path, "w", encoding="utf-8", newline="\n").write(original)
            drop_bytecode()
        (missed.append((name, f"not caught by {tests}")) if passed
         else caught.append(name))

    print(f"\n{len(caught)}/{len(chosen)} mutations caught\n")
    for name in caught:
        print(f"  caught   {name}")
    for name, why in missed:
        print(f"  MISSED   {name}  ({why})")
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
