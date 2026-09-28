#!/usr/bin/env python3
"""Render `TASK-425`'s run into the audit artifact the operator reads.

SEPARATE FROM THE RUN ON PURPOSE. The run measures; this renders. Mixing them
is how a report comes to state something the run did not measure - and this
artifact's whole value is that every line in it is traceable to a value the run
recorded.

THE ONE RULE THIS FILE ENFORCES BY CONSTRUCTION: a key that is ABSENT renders as
ABSENT, never as a pass. `report["sequencegate"]` is absent for a zero-lead
campaign in both modes, so `report.get("sequencegate", {}).get("passed")` is
`None` - and `None` is not `True`. Every verdict below reads a
`*_present` flag the run set by asking `in`, and says NOT PRESENT when it is
false. An artifact that rendered absence as a pass would make criterion 3
decorative while looking satisfied.
"""
import json


def verdict(present, passed, leads_checked=None):
    """PASSED / FAILED / NOT PRESENT / VACUOUS. Four states, never two.

    VACUOUS is the state the brief's trap 1 has a deeper form of. The key can be
    PRESENT with `passed: True` and `leads: []`, because
    `bisonfactory._refuse_sequence_gate` writes `{"passed": not refused,
    "leads": checked}` and `checked` is empty when no lead carried approved copy
    - `refused` is empty too, so `not refused` is True. A gate asked about
    nobody reports exactly what a gate that passed everybody reports.
    """
    if not present:
        return "NOT PRESENT (the key was absent, which is not a pass)"
    if passed is True and leads_checked == 0:
        return ("VACUOUS (passed=True with ZERO leads checked: the gate was "
                "asked about nobody, which is not a pass)")
    if passed is not True:
        return "FAILED (passed=%r)" % (passed,)
    return "PASSED (%s lead(s) checked)" % leads_checked


def fence(text, lang=""):
    return "```%s\n%s\n```" % (lang, str(text or "").rstrip())


def jfence(value):
    return fence(json.dumps(value, indent=1, default=str), "json")


def _table(rows, headers):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|")
                                     for c in row) + " |")
    return "\n".join(out)


def _copy_block(outcome, contact_key):
    steps = (outcome.get("cadence") or {}).get(contact_key) or {}
    out = []
    for key in sorted(steps):
        step = steps[key]
        if not isinstance(step, dict):
            continue
        words = step.get("body") or step.get("note") or ""
        out.append("**%s** (%s)  subject: %r\n\n%s"
                   % (key, step.get("channel"), step.get("subject"),
                      fence(words)))
    return "\n\n".join(out) or "_no copy stored for this contact_"


def claims_in(words, admitted):
    """What this step CLAIMS about the prospect, and what licenses each claim.

    THROUGH `copylint`'S OWN MACHINERY, not an approximation of it. An earlier
    version of this function decided "licensed" by counting words longer than
    four characters shared between a fact and a step, which is a rule that exists
    nowhere in the system: the artifact would then have reported a licence the
    gate does not grant, and criterion 4's whole value is that the claim it names
    is the claim the gate licensed.

    `copylint.COMPANY_CLAIM` decides which sentences are claims ABOUT THEM,
    `specifics_in` extracts what is checkable in one, and `_traces` decides
    whether a pack sentence containing it shares at least two content words with
    the draft sentence - `TASK-330`'s rule. Returns `(licensed, unlicensed)`.
    """
    from src import copylint
    import re as _re

    pack = {"facts": [{"snippet": fact.get("snippet")} for fact in admitted]}
    sentences = _re.split(r"(?<=[.!?])\s+", str(words or ""))
    pack_sentences = copylint._pack_sentences(pack)
    licensed, unlicensed = [], []
    for sentence in sentences:
        if not copylint.COMPANY_CLAIM.search(sentence):
            continue
        for value in copylint.specifics_in(sentence):
            entry = {"specific": value, "sentence": sentence.strip()}
            if copylint._traces(value, pack_sentences, sentence):
                # WHICH fact licensed it, decided by asking `_traces` again
                # against each fact ALONE. A substring search over the whole pack
                # picks the wrong one: `_norm("2")` is inside `_norm("...2016...")`
                # so the specific `2` from "2 week cycles" was attributed to the
                # about page's founding year. The gate's own predicate, narrowed
                # to one fact at a time, attributes it correctly.
                found = None
                for fact in admitted:
                    one = copylint._pack_sentences(
                        {"facts": [{"snippet": fact.get("snippet")}]})
                    if copylint._traces(value, one, sentence):
                        found = fact
                        break
                entry["licensed_by"] = (found or {}).get("snippet") \
                    or "(a pack sentence, attribution ambiguous)"
                entry["source"] = (found or {}).get("source_url")
                # WOULD IT STILL TRACE IF THE MATCH WERE TOKEN-EXACT?
                #
                # `_traces` tests `token in pack_sentence` on the NORMALISED
                # string, so a short numeric traces to any longer number that
                # happens to contain it. Reproduced 2026-09-28: with only "2016"
                # in the pack, the invented figures 2, 20 and 16 all trace and
                # only 99 is refused. `src/claims.py` was corrected for exactly
                # this once - "a founding year licensed its own digits and a
                # headcount BAND licensed its endpoints" - and this function was
                # not.
                #
                # So every licensed specific carries whether its licence
                # survives a token-exact reading. A claim that does NOT is a
                # claim this artifact is reporting as licensed on the strength of
                # a defect, and criterion 4 has to say so rather than print the
                # word "licensed" and move on.
                token = copylint._norm(value)
                entry["token_exact"] = any(
                    token in one.split()
                    for one in copylint._pack_sentences(
                        {"facts": [{"snippet": (found or {}).get("snippet")}]}))
                licensed.append(entry)
            else:
                unlicensed.append(entry)
    return licensed, unlicensed


def _audit_per_message(result, outcome, contact_key):
    """Criterion 4's per-message block, every line labelled.

    Each field names where its value came from, because "selected offer" read
    off a different run's report than "exact claim licensed" is how an audit
    artifact comes to describe a campaign that never existed.
    """
    offer_id = (outcome.get("selected_offers") or [None])[0]
    offer = outcome.get("offer") or {}
    objectives = outcome.get("step_objectives") or {}
    ai_names = outcome.get("ai_capabilities") or []
    admitted = outcome.get("admitted_facts") or []
    steps = (outcome.get("cadence") or {}).get(contact_key) or {}
    email = result.get("email") or {}
    gate_leads = ((email.get("sequencegate") or {}).get("leads") or [])
    gate = next((entry for entry in gate_leads
                 if str(entry.get("lead", "")).endswith(contact_key)), {})

    out = []
    for key in sorted(steps):
        step = steps[key]
        if not isinstance(step, dict):
            continue
        words = str(step.get("body") or step.get("note") or "")
        rung = key[-1] if key[:2] in ("em", "li") and key[-1].isdigit() else None
        named = sorted(n for n in ai_names if n.lower() in words.lower())
        mechanism_rung = bool(rung and any(
            n.lower() in str(objectives.get(rung, "")).lower()
            for n in ai_names))
        licensed, unlicensed = claims_in(words, admitted)
        out.append("\n".join([
            "#### %s" % key,
            "",
            "    PRIMARY PROBLEM              %s" % (
                offer.get("business_problem") or "(no offer selected)"),
            "    SELECTED OFFER               %s" % offer_id,
            "    WHY THIS OFFER               persona %r selects it: "
            "`generate_campaign._select_offers`" % outcome.get("persona"),
            "    SELECTED CORE CAPABILITIES   %s" % ", ".join(
                (outcome.get("capabilities") or {}).get("capability_order")
                or ["(none resolved)"]),
            "    STEP OBJECTIVE (rung %s)      %s" % (
                rung, objectives.get(rung, "(no rung for this step key)")),
            "    AI CAPABILITY USED           %s" % ("yes" if named else "no"),
            "    IF YES, WHICH ONE            %s" % (", ".join(named) or "n/a"),
            "    IF YES, WHY RELEVANT         %s" % (
                ("this rung's own objective names it, so it is the MECHANISM "
                 "step and the capability supports the angle rather than "
                 "leading it" if mechanism_rung else
                 "NOT JUSTIFIED: this rung's objective names no AI capability, "
                 "which `sequencegate.ai_is_supporting` refuses")
                if named else
                "n/a. `ai_required: false` - a message with no AI capability "
                "is valid and is not penalised"),
            "    SOURCE / PROVENANCE          %s" % (
                "; ".join("%s  <- %s" % (f.get("licensed_by") or "?",
                                         f.get("source") or "(pack)")
                          for f in licensed)
                or "ADMITTED RESEARCH, %d fact(s), each read off the account's "
                   "own site. This step makes no checkable assertion about the "
                   "prospect, so nothing had to be licensed." % len(admitted)),
            "    EXACT CLAIM LICENSED         %s" % (
                "; ".join(
                    "%r%s" % (f["specific"],
                              "" if f.get("token_exact") else
                              "  [LICENSED ONLY BY SUBSTRING, see ISSUE-055]")
                    for f in licensed)
                or "(none: this step asserts no specific about them)"),
            "    WHERE IT APPEARED IN COPY    %s" % (
                " | ".join(f["sentence"] for f in licensed)
                or "(nowhere: no claim made)"),
            "    UNLICENSED SPECIFICS         %s" % (
                "; ".join("%r in %r" % (f["specific"], f["sentence"])
                          for f in unlicensed)
                or "none - `copylint.untraceable` licensed every specific in a "
                   "sentence about them"),
            "",
        ]))
    out.append("**`sequencegate` verdict for this lead**\n\n%s" % jfence(gate))
    return "\n".join(out)


def matrix_verdicts(result):
    """PASSED or BLOCKED per matrix run, DERIVED from what the run recorded.

    Every verdict here is computed from a value the run measured, so the artifact
    cannot claim a pass the measurements do not support. The rule the operator
    set is that an unexpected change, or NO change where one was expected, is a
    BLOCK - so each run names the specific thing that had to move.
    """
    out = {}
    comparisons = result.get("comparisons") or {}
    runs = result.get("runs") or {}

    # A RUN THAT DID NOT HAPPEN IS NOT A PASS, and the A2 control is where that
    # would have bitten: its verdict is "no prompt moved", and no prompt moves in
    # a comparison that does not exist. An absent run is NOT RUN.
    missing = [run for run in ("A2", "B", "C", "D")
               if run not in comparisons]

    control = comparisons.get("A2") or {}
    moved = control.get("deterministic_stages_changed") or []
    noise = control.get("model_dependent_stages_changed") or []
    out["A2"] = {
        "verdict": "PASSED" if not moved else "BLOCKED",
        "why": ("identical inputs produced BYTE-IDENTICAL prompts at every "
                "deterministic stage (strategy, icp, extract), so a "
                "deterministic prompt that moves in B, C or D moved because of "
                "that run's variable. The model-dependent stages that did move "
                "are the measured noise floor: %s - `hypothesis` is rendered "
                "from the extract's answer, `match` from the hypothesis and the "
                "writer from all three, so identical inputs do NOT produce "
                "identical prompts there and asserting otherwise would be "
                "asserting the model is deterministic" % (noise or "none"))
        if not moved else
        ("identical inputs produced DIFFERENT prompts at a DETERMINISTIC stage, "
         "%s, so no prompt diff below is attributable to its variable" % moved),
    }

    b = comparisons.get("B") or {}
    b_prompts = bool(b.get("deterministic_stages_changed"))
    b_copy = not b.get("copy_identical")
    b_held = bool(b.get("held_after")) and not bool(b.get("held_before"))
    out["B"] = {
        "verdict": "PASSED" if (b_prompts and (b_copy or b_held))
        else "BLOCKED",
        "why": ("the changed fact moved the DETERMINISTIC prompts at %s and the "
                "copy at %s"
                % (b.get("deterministic_stages_changed"),
                   b.get("steps_whose_copy_changed"))
                if (b_prompts and b_copy) else
                "the changed fact moved the DETERMINISTIC prompts at %s and the "
                "lead HELD instead of producing copy: %s"
                % (b.get("deterministic_stages_changed"), b.get("held_after"))
                if (b_prompts and b_held) else
                "deterministic prompts moved: %s. copy identical: %s. Both had "
                "to change."
                % (b.get("deterministic_stages_changed"),
                   b.get("copy_identical"))),
    }

    c = comparisons.get("C") or {}
    offer_moved = (c.get("selected_offers_before")
                   != c.get("selected_offers_after"))
    caps_moved = (c.get("capabilities_before") != c.get("capabilities_after"))
    ladder_moved = (c.get("step_objectives_before")
                    != c.get("step_objectives_after"))
    out["C"] = {
        "verdict": "PASSED" if (offer_moved and caps_moved and ladder_moved)
        else "BLOCKED",
        "why": ("the offer moved %s -> %s, the capabilities moved, and the "
                "enforced ladder moved with them"
                % (c.get("selected_offers_before"),
                   c.get("selected_offers_after"))
                if (offer_moved and caps_moved and ladder_moved) else
                "offer moved: %s. capabilities moved: %s. ladder moved: %s. "
                "All three had to change."
                % (offer_moved, caps_moved, ladder_moved)),
    }

    d = comparisons.get("D") or {}
    before = (d.get("claim_before") or {}).get("present_in_copy")
    after = (d.get("claim_after") or {}).get("present_in_copy")
    d_held = bool(d.get("held_after"))
    gone = bool(before) and not after
    out["D"] = {
        "verdict": "PASSED" if (gone or d_held) else "BLOCKED",
        "why": ("the claim %r was in run A's copy and is absent from run D's, "
                "so removing the evidence removed the claim"
                % (d.get("claim_before") or {}).get("phrase")
                if gone else
                "the lead HELD with the evidence removed: %s" % d.get("held_after")
                if d_held else
                "the claim was present before: %s, and after: %s. It had to "
                "disappear, or the lead had to hold." % (before, after)),
    }
    for run in missing:
        out[run] = {"verdict": "NOT RUN",
                    "why": "this run was not executed, and a run that did not "
                           "happen is not a pass"}
    for run, entry in out.items():
        entry["invocations_used"] = (runs.get(run) or {}).get("invocations_used")
    return out


def criterion_verdicts(result):
    """The four frozen criteria, each PASSED or BLOCKED from the measurements."""
    email = result.get("email") or {}
    linkedin = result.get("linkedin") or {}
    negative = result.get("negative_test") or {}
    signature = result.get("signature_chain") or {}
    wire = result.get("wire") or {}
    runs = result.get("runs") or {}
    baseline = runs.get("A") or {}
    matrix = matrix_verdicts(result)

    out = {}

    blocked = [run for run, entry in matrix.items()
               if entry["verdict"] != "PASSED"]
    out["1 causal matrix"] = {
        "verdict": "PASSED" if not blocked else "BLOCKED",
        "why": ("A2 control held and B, C and D each moved what had to move"
                if not blocked else
                "BLOCKED on %s. See the per-run expected against observed."
                % ", ".join(sorted(blocked))),
    }

    found_anywhere = (bool(signature.get("mailbox_has_signature_field"))
                      or bool(signature.get("client_has_signature_field"))
                      or bool(signature.get("inventory_has_signature_field"))
                      or bool(signature.get("projection_has_signature_field")))
    out["2 signature chain"] = {
        "verdict": "PASSED" if found_anywhere else "BLOCKED",
        "why": ("a signature field was found and reached the rendered message"
                if found_anywhere else
                "NO LINK OF THE CHAIN CARRIES A SIGNATURE. `sender_signature` "
                "exists nowhere in this repository; the local mailbox model has "
                "no signature field, the client's sender block has none, the "
                "sender inventory has none, the provider projection has none, "
                "and the rendered final message ends without one. An empty "
                "signature is a BLOCK and this is it. No signature was "
                "synthesised: what a sender's signature says is the operator's "
                "and the client's decision."),
    }

    primary = negative.get("primary") or {}
    gate_ok = (email.get("sequencegate_present")
               and not email.get("sequencegate_vacuous")
               and (email.get("sequencegate") or {}).get("passed") is True
               and (email.get("sequencegate_leads_checked") or 0) > 0)
    negative_ok = (primary.get("refused") and primary.get("names_the_gate")
                   and primary.get("names_the_check")
                   and bool(primary.get("names_the_steps"))
                   and negative.get("gate_is_what_refuses") is True)
    out["3 offer sequencing with a negative test"] = {
        "verdict": "PASSED" if (gate_ok and negative_ok) else "BLOCKED",
        "why": ("the ladder ran on a zero-write staging run, the verdict is on "
                "the report with %s lead(s) actually checked, a rotated ladder "
                "is REFUSED naming the gate, the check and the steps, and with "
                "the gate bypassed the same broken campaign reaches the "
                "projection"
                % email.get("sequencegate_leads_checked")
                if (gate_ok and negative_ok) else
                "gate verdict usable: %s (present %s, vacuous %s, leads %s). "
                "negative test attributable: %s (refused %s, names gate %s, "
                "names check %s, names steps %s, gate is what refuses %s)"
                % (gate_ok, email.get("sequencegate_present"),
                   email.get("sequencegate_vacuous"),
                   email.get("sequencegate_leads_checked"), negative_ok,
                   primary.get("refused"), primary.get("names_the_gate"),
                   primary.get("names_the_check"),
                   primary.get("names_the_steps"),
                   negative.get("gate_is_what_refuses"))),
    }

    has_copy = bool(baseline.get("cadence"))
    has_email_projection = bool(((email.get("report") or {}).get("plan") or {})
                                .get("provider_sequence"))
    has_linkedin_projection = bool(linkedin.get("graph"))
    zero_writes = wire.get("provider_request_count") == 0
    complete = (has_copy and has_email_projection and has_linkedin_projection
                and zero_writes)
    out["4 audit artifact per message"] = {
        "verdict": "PASSED" if complete else "BLOCKED",
        "why": ("per-message audit, full copy, copylint, sequencegate, the "
                "SequencePlan, both provider projections, suppression, spend "
                "and provider writes = 0"
                if complete else
                "copy stored: %s. EmailBison projection: %s. HeyReach graph "
                "projection: %s. provider writes 0: %s."
                % (has_copy, has_email_projection, has_linkedin_projection,
                   zero_writes)),
    }
    return out, matrix


def write(result, path):
    runs = result.get("runs") or {}
    baseline = runs.get("A") or {}
    email = result.get("email") or {}
    linkedin = result.get("linkedin") or {}
    negative = result.get("negative_test") or {}
    signature = result.get("signature_chain") or {}
    wire = result.get("wire") or {}
    comparisons = result.get("comparisons") or {}
    contact_key = None
    for key in (baseline.get("cadence") or {}):
        contact_key = key
        break

    provider_calls = wire.get("provider_request_count")
    sg_present = email.get("sequencegate_present")
    sg = email.get("sequencegate") or {}

    lines = []
    add = lines.append

    add("# TASK-425 - the one account dry run, and the audit artifact")
    add("")
    add("**Generated by `scripts/task425_one_account_dry_run.py`. Every number "
        "below is a value that run recorded; nothing here is restated from "
        "prose.**")
    add("")
    add("    run at            %s" % result.get("at"))
    add("    account           %s   (a fixture, reserved domain, invented "
        "people)" % (baseline.get("record_after") or {}).get("company"))
    add("    persona in run A  %s" % baseline.get("persona"))
    add("    state directory   %s   (throwaway; the production queue was never "
        "opened)" % result.get("store"))
    add("    model             %s  via %s" % (result.get("model"),
                                              result.get("model_host")))
    add("    PROVIDER WRITES   %s" % provider_calls)
    add("")

    # ------------------------------------------------------------- the verdicts
    criteria, matrix = criterion_verdicts(result)
    add("## THE FOUR FROZEN CRITERIA")
    add("")
    add("**Every verdict here is COMPUTED from a value this run recorded.** "
        "Nothing below is an assertion about the system; each line names the "
        "measurement it rests on, and a criterion that cannot be met says so "
        "plainly rather than being narrowed until it passes.")
    add("")
    for name in sorted(criteria):
        entry = criteria[name]
        add("### %s - %s" % (name.upper(), entry["verdict"]))
        add("")
        add(entry["why"])
        add("")
    add("### The matrix, run by run")
    add("")
    add(_table([[run, matrix[run]["verdict"],
                 matrix[run].get("invocations_used"),
                 matrix[run]["why"]]
                for run in sorted(matrix)],
               ["run", "verdict", "entrypoint invocations", "why"]))
    add("")

    # ------------------------------------------------------------ zero writes
    add("## PROVIDER WRITES = 0, PROVED")
    add("")
    add("Two transports over `providers.request`, the single HTTP seam every "
        "provider module goes through, with the REAL `bison` and `heyreach` "
        "modules left in place underneath. A fake provider cannot prove that "
        "nothing was told to a provider, only that nothing was told to the "
        "fake.")
    add("")
    add("**BOTH TRAPS WERE FIRED ON PURPOSE** against a real EmailBison route, "
        "because `assertEqual([], requests)` is satisfied just as well by a "
        "trap that was never installed.")
    add("")
    add("### The generation-phase trap (model host allowed, everything else "
        "refused)")
    add(jfence(result.get("trap_generation")))
    add("### The staging-phase trap (every call refused)")
    add(jfence(result.get("trap_staging")))
    add("")
    add("### Every host this run contacted")
    add(jfence(wire.get("hosts")))
    add("### Every request that reached a provider host")
    add(jfence(wire.get("provider_requests")))
    add("")
    add("    PROVIDER REQUESTS TO EMAILBISON OR HEYREACH   %s" % provider_calls)
    add("")
    add("`sending.live` for `productive`, read from "
        "`killswitch.workspace_state` rather than from prose:")
    add(jfence(result.get("killswitch")))
    add("A dry run never reads it - `bisonfactory.stage` returns above the "
        "workspace read - so this run is NOT evidence that the killswitch "
        "works. It is recorded so nobody reads it as such.")
    add("")

    # -------------------------------------------------------------- the account
    add("## THE ACCOUNT")
    add("")
    add("`tests/task425fixture.py`. A reserved domain and invented people: the "
        "brief permits a real public domain and forbids a real person, and "
        "this takes the stricter half of that permission. The client's own "
        "domain is deliberately absent from the fixture: it is already two "
        "known baseline suite failures and a third occurrence in a new tracked "
        "file would raise a standing count for no gain.")
    add("")
    add("### Admitted research - the ONLY thing that can license a claim")
    add(jfence(baseline.get("admitted_facts")))
    add("### CLIENT_SUPPLIED facts - qualification and strategy, NO claim")
    add("Operator decision B, 2026-09-28. All six client-CSV keys, each naming "
        "its source file and row, returned by `packfacts.pack_for` under "
        "`unused[CLIENT_SUPPLIED]` and kept OUT of `pack[\"facts\"]`.")
    add(jfence(baseline.get("client_supplied")))
    add("### Contacts")
    add(_table([[c.get("key"), c.get("title"), c.get("persona"),
                 c.get("email")]
                for c in (baseline.get("record_after") or {}).get("contacts")
                or ()],
               ["contact", "title", "persona", "address"]))
    add("")
    add("### Cadence, declared by this campaign rather than inherited")
    add("    %s" % result.get("cadence_name"))
    add(jfence(result.get("cadence_steps")))
    add("")

    # ------------------------------------------------------- criterion 1
    add("## CRITERION 1 - THE CAUSAL MATRIX")
    add("")
    add("Same account, everything else constant. Each run states its EXPECTED "
        "change and its OBSERVED diff. An unexpected change, or no change, is "
        "a BLOCK.")
    add("")
    add("**THE CAUSAL CARRIER IS THE PROMPT, and it is reported as well as the "
        "copy.** A copy diff alone cannot say whether a change travelled "
        "through the decision layer or came out of the model's own variance. "
        "The rendered prompt is deterministic given the inputs, so run A2 "
        "repeats run A with identical inputs and is the control for the whole "
        "matrix: if a prompt moves there, no copy diff below is attributable.")
    add("")
    for run in ("A2", "B", "C", "D"):
        outcome = runs.get(run)
        if not outcome:
            continue
        diff = comparisons.get(run) or {}
        add("### Run %s - %s" % (run, outcome.get("label")))
        add("")
        add("    VARIABLE   %s" % outcome.get("variable"))
        add("    EXPECTED   %s" % outcome.get("expected"))
        add("")
        add("**OBSERVED**")
        add("")
        add("    DETERMINISTIC prompt stages that changed    %s"
            % (diff.get("deterministic_stages_changed") or "none"))
        add("    model-dependent stages that changed         %s"
            % (diff.get("model_dependent_stages_changed") or "none"))
        add("    selected offer        %s  ->  %s"
            % (diff.get("selected_offers_before"),
               diff.get("selected_offers_after")))
        add("    capabilities          %s  ->  %s"
            % ((diff.get("capabilities_before") or {}).get("capability_order"),
               (diff.get("capabilities_after") or {}).get("capability_order")))
        add("    step objectives       %s  ->  %s"
            % (json.dumps(diff.get("step_objectives_before")),
               json.dumps(diff.get("step_objectives_after"))))
        add("    admitted facts        %d  ->  %d"
            % (len(diff.get("admitted_before") or ()),
               len(diff.get("admitted_after") or ())))
        add("    steps whose copy changed   %s"
            % (diff.get("steps_whose_copy_changed") or "NONE"))
        add("    copy identical             %s" % diff.get("copy_identical"))
        add("    held / refused before      %s" % (diff.get("held_before")
                                                   or "none"))
        add("    held / refused after       %s" % (diff.get("held_after")
                                                   or "none"))
        add("")
        add("**The claim under test, `%s`**" % (diff.get("claim_before") or {}
                                                ).get("phrase"))
        add(jfence({"before": diff.get("claim_before"),
                    "after": diff.get("claim_after")}))
        add("**em1, unified diff against run A**")
        add(fence("\n".join(diff.get("em1_diff") or []) or "(no difference)",
                  "diff"))
        add("")

    # ------------------------------------------------------- criterion 2
    add("## CRITERION 2 - THE SIGNATURE CHAIN")
    add("")
    add("    mailbox owner -> sender_signature -> the rendered final message "
        "in the provider projection")
    add("")
    add("Measured link by link. **No signature was synthesised**: what a "
        "sender's signature says is the operator's and the client's decision, "
        "and inventing one to make this pass would put words nobody approved "
        "at the bottom of every email.")
    add("")
    add(jfence({k: v for k, v in signature.items()
                if k not in ("final_rendered_body", "rendered_messages")}))
    add("")
    add("**THE RENDERED FINAL MESSAGE, in full.** The projection's steps are a "
        "TEMPLATE of merge fields and the words travel per lead in custom "
        "variables, so this is the template with this lead's own variables "
        "resolved through `bisonfactory._variables_for` - what the provider "
        "would actually be told. Reporting `<p>{BODY_5}</p>` and calling the "
        "signature absent would be true of every campaign ever staged and would "
        "prove nothing.")
    add("")
    add(fence(signature.get("final_rendered_body")))
    add("")
    add("**Every rendered message, every step**")
    add(jfence(signature.get("rendered_messages")))
    add("")

    # ------------------------------------------------------- criterion 3
    add("## CRITERION 3 - OFFER SEQUENCING AS STEP OBJECTIVES, WITH A NEGATIVE "
        "TEST")
    add("")
    add("    Offer A   margin visibility -> quote versus burn -> resource "
        "decisions that move margin")
    add("              -> Report Intelligence as mechanism, only if it "
        "strengthens the angle -> reframe and close")
    add("    Offer B   project visibility -> time -> resourcing")
    add("              -> AI Time Tracking as mechanism, only if it "
        "strengthens the angle -> one operational view")
    add("")
    add("The ladder this run enforced, read from the offer record rather than "
        "restated:")
    add(jfence(baseline.get("step_objectives")))
    add("")
    add("### The gate's verdict on the staged campaign")
    add("")
    add("    report[\"sequencegate\"] PRESENT   %s" % sg_present)
    add("    leads the gate was asked about   %s"
        % email.get("sequencegate_leads_checked"))
    add("    vacuous pass                     %s"
        % email.get("sequencegate_vacuous"))
    add("    VERDICT                          %s"
        % verdict(sg_present, sg.get("passed"),
                  email.get("sequencegate_leads_checked")))
    add("")
    add("The key is asserted PRESENT before it is read. It is ABSENT for a "
        "zero-lead campaign in both modes, so `report.get(\"sequencegate\", "
        "{}).get(\"passed\")` is `None`, and `None` is not `True`. **And the "
        "leads are COUNTED**, because the key has a second way to lie: present, "
        "`passed: True`, `leads: []` when no lead carried approved copy, since "
        "`_refuse_sequence_gate` writes `not refused` and `refused` is empty "
        "too. A gate asked about nobody reports what a gate that passed "
        "everybody reports.")
    add("")
    add(jfence(sg))
    add("")
    add("### THE NEGATIVE TEST - a sequence that violates the ladder is "
        "REFUSED")
    add("")
    add("em1 and em3 exchange bodies and are re-stamped so the approval still "
        "certifies the words present. The only property that changed is which "
        "rung each step pursues; every other gate sees the batch it just "
        "passed.")
    add("")
    for name in ("primary", "secondary"):
        case = negative.get(name) or {}
        add("#### %s mutation: %s" % (name, case.get("mutation")))
        add("")
        add("    contacts mutated                  %s"
            % case.get("contacts_mutated"))
        add("    REFUSED                           %s" % case.get("refused"))
        add("    the refusal names the gate        %s"
            % case.get("names_the_gate"))
        add("    the refusal names step_objectives %s"
            % case.get("names_the_check"))
        add("    the refusal names the steps       %s"
            % case.get("names_the_steps"))
        add("")
        add(fence(case.get("why") or "(not refused)"))
        add("")
    add("    with the gate BYPASSED, the rotated campaign reached the "
        "projection with %s provider steps"
        % negative.get("bypassed_reached_projection"))
    add("    so the gate is what refuses      %s"
        % negative.get("gate_is_what_refuses"))
    add("")
    add("That last pair is the part that makes this a negative test rather "
        "than an assertion about a message. Asserting on the text is not "
        "enough: the message is built from the gate's own report, so a gate "
        "refusing for the wrong reason still names itself. What is measured is "
        "an EFFECT - with `sequencegate.check` replaced by a verdict that "
        "passes everything, the identical broken campaign must reach the "
        "projection.")
    add("")
    add("The rotation is the primary case because it guarantees the property "
        "the check refuses on: every rung's vocabulary sits at a step that is "
        "not its own. The single swap is reported beside it because the two "
        "measure different sensitivities, and picking whichever mutation "
        "refuses would be choosing the evidence.")
    add("")

    # ------------------------------------------------------- criterion 4
    add("## CRITERION 4 - THE AUDIT ARTIFACT, PER MESSAGE")
    add("")
    if contact_key:
        add("Contact `%s`." % contact_key)
        add("")
        add(_audit_per_message(result, baseline, contact_key))
    else:
        add("_No copy was stored for any contact on run A, so there is no "
            "per-message artifact. The run's own refusal is above._")
    add("")
    add("### Full copy, every contact, run A")
    for key in sorted((baseline.get("cadence") or {})):
        add("")
        add("#### %s" % key)
        add("")
        add(_copy_block(baseline, key))
    add("")
    add("### copylint, on the staged batch")
    add(jfence(email.get("copylint")))
    add("### The EmailBison projection")
    add(jfence(((email.get("report") or {}).get("plan") or {})
               .get("provider_sequence")))
    add("### Every projection of the ONE canonical plan")
    add("")
    add("ONE TRUTH, per `docs/OPERATING-MODE.md`: preview, provider adapters, "
        "approval and QA are PROJECTIONS of one plan, never second "
        "implementations. All of these are derived from the SAME plan object, so "
        "there is nothing for them to disagree with. A projection that refuses "
        "records its refusal rather than taking the others down.")
    add(jfence(result.get("projections")))
    add("### The canonical SequencePlan")
    add(jfence(((email.get("report") or {}).get("plan") or {})
               .get("sequence_plan")))
    add("### The EmailBison report, whole")
    add(jfence(email))
    add("### The HeyReach projection")
    add(jfence({"refused": linkedin.get("refused"),
                "why": linkedin.get("why"),
                "graph": linkedin.get("graph"),
                "touch_report": linkedin.get("touch_report")}))
    add("### The HeyReach report, whole")
    add(jfence(linkedin.get("report")))
    add("### Suppression")
    add(jfence(result.get("suppression")))
    add("### Spend, client aware")
    add("")
    spend = result.get("spend") or {}
    add("    ledger rows written              %s" % spend.get("row_count"))
    add("    expected_total                   %s"
        % ((spend.get("report") or {}).get("expected_total")))
    add("    the model id is priced           %s"
        % spend.get("model_in_price_file"))
    add("    calls ledgered but UNPRICED      %s" % spend.get("unpriced_calls"))
    add("    calls ledgered WITH a price      %s" % spend.get("priced_calls"))
    add("")
    add("**`expected_total: 0` DOES NOT MEAN NO CALL WAS MADE.** A model absent "
        "from `config/model-prices.yaml` still gets a ledger row with "
        "`expected_cost: 0` and its call name - that file's own header says a "
        "missing row and a free call must not be indistinguishable. The model "
        "this run asked for is not in it, so every completion is ledgered "
        "visibly and unpriced, and the honest reading of the number above is "
        "\"N unpriced model calls\", not \"nothing was spent\". The model calls "
        "per run are counted separately below.")
    add("")
    add(jfence(spend))
    add("")
    add("### Model calls per run")
    add(_table([[run, (runs.get(run) or {}).get("model_calls"),
                 (runs.get(run) or {}).get("generation_stamp") or "(none)",
                 (runs.get(run) or {}).get("error") or "-"]
                for run in sorted(runs)],
               ["run", "model calls", "generation stamp", "error"]))
    add("")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
