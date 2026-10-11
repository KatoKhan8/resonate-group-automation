"""The synthetic sandbox fixture, and a positive control for every assertion.

WHAT THIS FILE IS. `scripts/sandbox_fixture.py` invents 300 prospect records
over 100 companies for the 60-day sandbox simulation. This module asserts the
properties that make that fixture safe to feed to the EXISTING production
flow, and - because a check nobody has watched fail is not a check - every one
of those assertions is paired with a POSITIVE CONTROL that poisons a copy of
the fixture and proves the same checker reports the problem.

The checkers are module-level `_check_*` functions returning a list of
problems rather than assertions inlined into tests, for exactly that reason:
the control has to run the SAME code the real assertion runs. A control that
re-implements the check proves only that the re-implementation works.

ISOLATION IS PHASE 1's, NOT A NEW ONE. `tests/test_sandbox_phase1.py` at
963a7d64 established it and this module reuses it unchanged:

  * `_production_root()` resolves the MAIN checkout through `.git`, because
    this file normally runs from a linked worktree where `work/` does not
    exist at all. Measured here on 2026-10-12: the worktree has NO
    `work/queue.jsonl`, NO `work/campaigns.jsonl`, NO `work/agency-dnc.jsonl`
    and NO `config/suppress.local.txt`. Every one of the production
    assertions below would have been VACUOUS against the worktree - the
    domain scan would have searched an empty string and passed, and the
    before/after comparison would have compared None to None. `setUp`
    asserts each file is present before using it.
  * `store.use_directory()` into a throwaway temp directory, with
    `queue_path()` AND `campaigns_path()` asserted to have BOTH moved and the
    `CAMPAIGNS` override asserted gone - a stale `CAMPAIGNS` would otherwise
    survive the redirect and keep pointing at the real file.
  * md5 of the production files in `setUp`, re-checked in `addCleanup`, plus
    the mtime and the size the operator asked for specifically.

THE RECORD SHAPE IS THE REAL ONE, AND THAT IS WHAT MOST OF THIS CHECKS.
The fixture is fed to the production flow, not to a reimplementation, so the
interesting failures are shape failures that nothing would complain about:

  * `store.validate()` accepts a contact key of `c1` as readily as
    `kelly-smith`, so a positional key would have passed every test while
    every downstream join keyed on a person was keyed on a position.
  * `rec["cadence"]` and `rec["cadence_steps"]` are different keys. Steps
    under the wrong one yield "not part of the configured cadence for this
    contact" on every step and no other error.
  * a hand-built research dict has none of the eighteen scored fields
    `evidence.make` produces, and raises inside `quality._selected`.
  * evidence that scores UNUSABLE licenses nothing, so the copy path silently
    falls back to persona pain - and a count of facts cannot see it.
  * `verification.is_sendable` RECOMPUTES and ignores a stored flag, so a
    `sendable: true` written by hand is a no-op, and the two controls here
    prove the two-confirmation policy genuinely bites.

THE BOTH-DIRECTION DOMAIN CHECK IS THE ONE THAT MATTERS, and the two
directions fail for different reasons, so they get separate controls:

  (a) a synthetic domain found in production state would mean this fixture
      had been written into the real queue, or that a coined name collided
      with a live account. Its control injects a domain READ OUT OF the real
      queue at runtime and proves the scanner finds it - which also proves
      the scanner is reading a file with content in it.
  (b) a real client domain found in the fixture would mean a live customer
      had been pulled into synthetic data and could be cold-sequenced. Its
      control injects a real domain into a copy of the fixture. The only one
      spelled out in this file is `productive.io`, which is the client's own
      and is already tracked in `config/clients/productive.yaml`; every other
      needle is READ from the gitignored roster at runtime, because a customer
      name hardcoded into a tracked test reaches every clone of this repo.

ZERO DATA SPEND. Nothing here imports a provider or opens a socket. The
fixture generator is called in-process.
"""
import copy
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest

from src import (agencydnc, cadence, clients, dedupe, evidence, linkedin,
                 packfacts, store, verification)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import sandbox_fixture                        # noqa: E402


def _production_root():
    """The MAIN checkout, even when this file sits in a linked worktree.

    Lifted verbatim from `tests/test_sandbox_phase1.py`. See the module
    docstring: without it every production assertion in this file is vacuous.
    """
    dot = os.path.join(ROOT, ".git")
    if os.path.isdir(dot):
        return ROOT
    with open(dot, encoding="utf-8") as handle:
        pointer = handle.read().strip()
    # `gitdir: <main>/.git/worktrees/<name>`
    gitdir = pointer.split(":", 1)[1].strip()
    if not os.path.isabs(gitdir):
        gitdir = os.path.abspath(os.path.join(ROOT, gitdir))
    return os.path.dirname(os.path.dirname(os.path.dirname(gitdir)))


PRODUCTION = _production_root()

# The production state the fixture must stay out of, and be absent from.
PRODUCTION_STATE = ("queue.jsonl", "campaigns.jsonl", "agency-dnc.jsonl")

# Which of those actually hold plaintext domains. `agency-dnc.jsonl` does NOT:
# it stores only sha256 fingerprints, by design, so a domain scan of it is a
# check that cannot fail. See `test_the_agency_dnc_holds_no_plaintext_at_all`
# and `test_no_synthetic_contact_is_on_the_agency_dnc`, which asks that file
# the question it can actually answer.
PLAINTEXT_STATE = ("queue.jsonl", "campaigns.jsonl")

# The untracked live-customer roster. Gitignored, so it is in the MAIN
# checkout and never in a worktree.
SUPPRESS_LOCAL = os.path.join(PRODUCTION, "config", "suppress.local.txt")

# The operator's brief says twelve. Asserted as a FLOOR, not an equality: a
# thirteenth paying customer must not fail the suite, but a roster that has
# been truncated or replaced by the tracked template must.
SUPPRESS_LOCAL_MINIMUM = 12

# One domain known to be in that roster AND to be the client's own. If this is
# missing, the file that loaded was not the real roster.
ROSTER_SENTINEL = "productive.io"

SEED = 1
OTHER_SEED = 2
EXPECTED_RECORDS = 300
EXPECTED_COMPANIES = 100
CONTACTS_PER_COMPANY = 3          # EQUALITY, per the operator's correction
COHORT_FLOOR = 50
COHORT_DIMENSIONS = ("geo", "industry", "headcount_band", "signal", "persona")

# The live top-level record keys, from a real production row.
RECORD_KEYS = (
    "id", "domain", "client", "batch", "company", "lane", "signal", "state",
    "stages", "events", "log", "excluded", "drop_reason", "hook", "context",
    "diagnosis", "waterfall", "sizing", "qualification", "company_facts",
    "research", "contacts", "cadence",
)

# The live contact keys.
CONTACT_KEYS = (
    "key", "name", "email", "linkedin", "persona", "title", "primary",
    "angle", "email_source", "sendable", "mx", "reoon", "verdict",
    "verification", "bison_lead_id",
)


def _md5(path):
    if not os.path.exists(path):
        return None
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _roster_domains(path):
    """The live-customer domains, comments and blanks dropped."""
    out = []
    for line in _read(path).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.lower())
    return out


def _by_record(fixture):
    grouped = {}
    for record in fixture["records"]:
        grouped.setdefault(record["id"], []).append(record)
    return grouped


# ------------------------------------------------------------- the checkers
#
# Each returns [] for a clean fixture and a non-empty list of strings
# otherwise. Tests assert emptiness on the real fixture and non-emptiness on a
# poisoned copy, through this same function.

def _check_counts(fixture):
    problems = []
    records, companies = fixture["records"], fixture["companies"]
    if len(records) != EXPECTED_RECORDS:
        problems.append("expected %d records, got %d"
                        % (EXPECTED_RECORDS, len(records)))
    if len(companies) != EXPECTED_COMPANIES:
        problems.append("expected %d companies, got %d"
                        % (EXPECTED_COMPANIES, len(companies)))
    ids = [company["id"] for company in companies]
    if len(set(ids)) != len(ids):
        problems.append("company id is not unique")
    domains = [company["domain"] for company in companies]
    if len(set(domains)) != len(domains):
        problems.append("company domain is not unique")
    orphans = {record["id"] for record in records} - set(ids)
    if orphans:
        problems.append("records name %d unknown companies: %s"
                        % (len(orphans), sorted(orphans)[:3]))
    return problems


def _check_three_per_company(fixture):
    """EXACTLY three, asserted as equality. The operator's correction of
    2026-10-12 replaced a 2-3 range; a company that lost a decision maker now
    fails instead of landing inside the old tolerance."""
    problems = []
    grouped = _by_record(fixture)
    for company in fixture["companies"]:
        held = grouped.get(company["id"], [])
        if len(held) != CONTACTS_PER_COMPANY:
            problems.append("%s has %d decision makers, expected exactly %d"
                            % (company["id"], len(held), CONTACTS_PER_COMPANY))
    return problems


def _check_distinct_decision_makers(fixture):
    """Distinct PEOPLE and distinct PERSONAS inside one company.

    Both halves matter and they fail differently: three records naming one
    person is a duplicate, and three distinct people all holding the same
    persona is a cohort that is not what it says it is.
    """
    problems = []
    for company_id, held in sorted(_by_record(fixture).items()):
        for field in ("name", "email", "linkedin", "key", "persona"):
            values = [record[field] for record in held]
            if len(set(values)) != len(values):
                problems.append("%s repeats %s: %s"
                                % (company_id, field, sorted(values)))
    everyone = [record["name"] for record in fixture["records"]]
    if len(set(everyone)) != len(everyone):
        problems.append("the same person appears at more than one company")
    return problems


def _check_linkedin(fixture):
    """Every record has a URL, and it is ALREADY its own canonical form.

    A missing URL is a data-loss defect in this system - HeyReach's inbox
    carries no identifier but `profileUrl`, so the URL is how a reply is
    matched back to a record. The fixture must not hide that rule by quietly
    omitting one, so an empty, None or absent URL is a problem here, and
    equality with `canonical()` is asserted rather than mere truthiness: a URL
    that canonicalises to something ELSE would join two spellings downstream.
    """
    problems = []
    for record in fixture["records"]:
        where = "%s/%s" % (record["id"], record["key"])
        url = record.get("linkedin")
        if not url:
            problems.append("%s has no LinkedIn URL" % where)
            continue
        canonical = linkedin.canonical(url)
        if canonical is None:
            problems.append("%s: canonical() refused %r" % (where, url))
        elif canonical != url:
            problems.append("%s: %r canonicalises to %r"
                            % (where, url, canonical))
    for row in fixture["queue_records"]:
        for contact in row["contacts"]:
            if not contact.get("linkedin"):
                problems.append("%s/%s has no LinkedIn URL on the contact"
                                % (row["id"], contact.get("key")))
    return problems


def _check_emails(fixture):
    """EVERY address ends `.invalid`. `example.com` is NOT permitted.

    The first brief allowed `example.com`; the operator's correction of
    2026-10-12 removed it. `.invalid` is reserved by RFC 6761 and can never be
    delegated, so an address under it cannot be delivered by any resolver
    anywhere - which is the whole point: if a sandbox record ever reached a
    live sender, the send fails instead of landing in a stranger's inbox.
    """
    problems = []
    addresses = [("%s/%s" % (record["id"], record["key"]), record.get("email"))
                 for record in fixture["records"]]
    addresses += [("%s/%s" % (row["id"], contact.get("key")),
                   contact.get("email"))
                  for row in fixture["queue_records"]
                  for contact in row["contacts"]]
    for where, email in addresses:
        if not email:
            problems.append("%s has no email" % where)
            continue
        domain = str(email).rsplit("@", 1)[-1].lower()
        if not domain.endswith(".invalid"):
            problems.append("%s: %r is not under .invalid" % (where, email))
        if dedupe.normalise_email(email) != email:
            problems.append("%s: %r is not normalise_email-canonical"
                            % (where, email))
    for company in fixture["companies"]:
        if not str(company["domain"]).lower().endswith(".invalid"):
            problems.append("company domain %r is not under .invalid"
                            % company["domain"])
    return problems


def _check_cohorts(fixture):
    """No cohort under 50, and each one homogeneous in all five dimensions."""
    problems = []
    members = {}
    for record in fixture["records"]:
        members.setdefault(record["cohort"], []).append(record)

    declared = {cohort["key"]: cohort for cohort in fixture["cohorts"]}
    if set(declared) != set(members):
        problems.append("declared cohorts %s but records use %s"
                        % (sorted(declared), sorted(members)))

    for key, held in sorted(members.items()):
        spec = declared.get(key)
        if len(held) < COHORT_FLOOR:
            problems.append("cohort %s holds %d records, under the floor of %d"
                            % (key, len(held), COHORT_FLOOR))
        for dimension in COHORT_DIMENSIONS:
            values = {record[dimension] for record in held}
            if len(values) != 1:
                problems.append("cohort %s is not homogeneous in %s: %s"
                                % (key, dimension, sorted(values)))
                continue
            if spec is not None and spec[dimension] != held[0][dimension]:
                problems.append(
                    "cohort %s declares %s=%r but its records carry %r"
                    % (key, dimension, spec[dimension], held[0][dimension]))
        if spec is not None and spec.get("size") != len(held):
            problems.append("cohort %s declares size %r, holds %d"
                            % (key, spec.get("size"), len(held)))
    return problems


def _check_record_shape(fixture):
    """The keys the live flow reads, and the ones only a provider could fill.

    `store.validate()` is the real gate but a thin one - it requires eight
    top-level fields and one key per contact. Everything else below is a shape
    the flow depends on and nothing validates.
    """
    problems = []
    rows = fixture["queue_records"]
    if len(rows) != EXPECTED_COMPANIES:
        problems.append("expected %d queue rows, got %d"
                        % (EXPECTED_COMPANIES, len(rows)))
    for row in rows:
        found = store.validate(row)
        if found:
            problems.append("%s: %s" % (row.get("id"), found))
        for key in RECORD_KEYS:
            if key not in row:
                problems.append("%s: record is missing %s"
                                % (row.get("id"), key))
        steps = row.get(cadence.CADENCE_KEY)
        if not isinstance(steps, list) or not steps:
            problems.append("%s: %s is not a non-empty list"
                            % (row.get("id"), cadence.CADENCE_KEY))
        else:
            for step in steps:
                for field in cadence.REQUIRED_STEP_FIELDS:
                    if field not in step:
                        problems.append("%s: cadence step missing %s"
                                        % (row.get("id"), field))
        for contact in row.get("contacts") or []:
            where = "%s/%s" % (row.get("id"), contact.get("key"))
            for key in CONTACT_KEYS:
                if key not in contact:
                    problems.append("%s: contact is missing %s" % (where, key))
            for key in sandbox_fixture.NULL_WITHOUT_A_PROVIDER:
                if contact.get(key) is not None:
                    problems.append(
                        "%s: %s is %r, but nothing here can know it without a "
                        "provider" % (where, key, contact.get(key)))
            if str(contact.get("key") or "").startswith("c") \
                    and str(contact.get("key") or "")[1:].isdigit():
                problems.append("%s: contact key is positional, not a person"
                                % where)
    return problems


def _check_research(fixture):
    """The research list, as `evidence.make` objects that actually license.

    Three separate failures, all invisible to a count of facts: a hand-built
    dict missing the scored fields, a fact that scores UNUSABLE so the copy
    path falls back, and a source URL that is not same-site so
    `packfacts.identity_of` refuses it.
    """
    problems = []
    scored = set(evidence.make(fact="a fact with at least four words in it",
                               source_url="https://x.invalid/a",
                               source_type="t", provider="p",
                               record_id="r", today="2026-10-12"))
    for row in fixture["queue_records"]:
        items = row.get("research")
        if not isinstance(items, list) or not items:
            problems.append("%s: research is not a non-empty list"
                            % row.get("id"))
            continue
        for item in items:
            if not isinstance(item, dict):
                problems.append("%s: research item is %s, not an evidence dict"
                                % (row.get("id"), type(item).__name__))
                continue
            missing = scored - set(item)
            if missing:
                problems.append("%s: evidence item missing %s"
                                % (row.get("id"), sorted(missing)))
            if item.get("quality") not in evidence.USABLE:
                problems.append("%s: evidence %s scores %r, so the copy path "
                                "would fall back to persona pain"
                                % (row.get("id"), item.get("evidence_id"),
                                   item.get("quality")))
        pack, _unused = packfacts.pack_for(row)
        if len(pack["facts"]) != len(items):
            problems.append("%s: %d of %d research rows licensed"
                            % (row.get("id"), len(pack["facts"]), len(items)))
        known = {item.get("evidence_id") for item in items
                 if isinstance(item, dict)}
        for contact in row.get("contacts") or []:
            selected = ((contact.get("personalization") or {})
                        .get("selected_evidence_ids"))
            if not selected:
                problems.append(
                    "%s/%s has no selected_evidence_ids, so personalisation "
                    "quality cannot be computed"
                    % (row.get("id"), contact.get("key")))
                continue
            dangling = set(selected) - known
            if dangling:
                problems.append("%s/%s selects evidence that is not on the "
                                "record: %s" % (row.get("id"),
                                                contact.get("key"),
                                                sorted(dangling)))
    return problems


def _check_sendability(fixture, policy):
    """The stored flag must equal the recomputation, for all 300.

    `is_sendable` never reads the stored value, so the two can drift silently:
    a fixture could carry `sendable: true` on a contact the policy refuses and
    nothing would say so until a send was attempted.
    """
    problems = []
    for row in fixture["queue_records"]:
        for contact in row["contacts"]:
            where = "%s/%s" % (row["id"], contact.get("key"))
            recomputed = verification.is_sendable(contact, policy)
            if contact.get("sendable") != recomputed:
                problems.append("%s: stored sendable=%r, recomputed %r"
                                % (where, contact.get("sendable"), recomputed))
            if not recomputed:
                problems.append("%s: not sendable under the client's policy"
                                % where)
            decision = verification.resolve(contact, policy)
            if decision.get("confirmation_count") \
                    != policy["required_confirmations"]:
                problems.append(
                    "%s: %r confirmations, policy requires %r"
                    % (where, decision.get("confirmation_count"),
                       policy["required_confirmations"]))
    return problems


def _domain_hits(needles, haystack):
    """Which of `needles` occur in `haystack`. One compiled alternation, so a
    27 MB file is one pass rather than a hundred."""
    if not needles:
        return []
    pattern = re.compile("|".join(re.escape(needle)
                                  for needle in sorted(needles)),
                         re.IGNORECASE)
    return sorted({match.group(0).lower()
                   for match in pattern.finditer(haystack)})


class SealedSandbox(unittest.TestCase):
    """A store copy, production state md5'd, and nothing on the wire."""

    def setUp(self):
        # THE MAIN CHECKOUT, NOT THIS WORKTREE, AND ASSERTED PRESENT. A
        # worktree has no `work/` at all, so every scan below would read an
        # empty string and pass, and the before/after would compare None
        # to None.
        self.prod_paths = {name: os.path.join(PRODUCTION, "work", name)
                           for name in PRODUCTION_STATE}
        for name, path in self.prod_paths.items():
            self.assertTrue(os.path.exists(path),
                            "production %s not found at %s - every assertion "
                            "against it would be vacuous" % (name, path))
        self.assertTrue(os.path.exists(SUPPRESS_LOCAL),
                        "the live-customer roster is not at %s - the "
                        "real-domain assertions would have nothing to exclude"
                        % SUPPRESS_LOCAL)

        # md5 AND mtime AND size, which is what the operator asked for: a
        # rewrite with identical bytes still moves the mtime, and a truncation
        # that happened to preserve the digest is not a thing but a size check
        # costs nothing.
        self.before = {name: (_md5(path), os.path.getmtime(path),
                              os.path.getsize(path))
                       for name, path in self.prod_paths.items()}
        self.assertTrue(all(digest for digest, _, _ in self.before.values()))
        self.addCleanup(self._assert_production_untouched)

        self.tmp = tempfile.mkdtemp(prefix="sandbox-fixture-")
        self.sandbox = os.path.join(self.tmp, "work")
        before_queue = store.queue_path()
        before_campaigns = store.campaigns_path()
        self.addCleanup(store.use_directory(self.sandbox))

        self.assertNotEqual(store.queue_path(), before_queue)
        self.assertNotEqual(store.campaigns_path(), before_campaigns)
        self.assertTrue(store.queue_path().startswith(
            os.path.abspath(self.sandbox)), store.queue_path())
        self.assertTrue(store.campaigns_path().startswith(
            os.path.abspath(self.sandbox)), store.campaigns_path())
        # A STALE `CAMPAIGNS` WOULD SURVIVE THE REDIRECT. `use_directory`
        # works by CLEARING the override set, so its absence is the thing that
        # proves campaigns moved with the queue.
        self.assertIsNone(os.environ.get("CAMPAIGNS"))
        for resolved in (store.queue_path(), store.campaigns_path()):
            self.assertNotIn(os.path.abspath(resolved),
                             {os.path.abspath(path)
                              for path in self.prod_paths.values()}, resolved)

        self.config = clients.load(sandbox_fixture.CLIENT)
        self.policy = verification.policy_for(self.config)
        self.fixture = sandbox_fixture.build(SEED)

    def _assert_production_untouched(self):
        now = {name: (_md5(path), os.path.getmtime(path),
                      os.path.getsize(path))
               for name, path in self.prod_paths.items()}
        self.assertEqual(now, self.before,
                         "this test changed the main checkout's work/ state")

    def poisoned(self):
        """A deep copy to wreck, so the control cannot leak into another test."""
        return copy.deepcopy(self.fixture)


class Counts(SealedSandbox):

    def test_exactly_300_records_over_exactly_100_companies(self):
        self.assertEqual(_check_counts(self.fixture), [])
        self.assertEqual(len(self.fixture["records"]), EXPECTED_RECORDS)
        self.assertEqual(len(self.fixture["companies"]), EXPECTED_COMPANIES)
        self.assertEqual(len(self.fixture["queue_records"]),
                         EXPECTED_COMPANIES)

    def test_control_a_missing_record_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"].pop()
        self.assertNotEqual(_check_counts(poisoned), [])

    def test_control_a_duplicate_company_domain_is_caught(self):
        poisoned = self.poisoned()
        poisoned["companies"][1]["domain"] = poisoned["companies"][0]["domain"]
        self.assertNotEqual(_check_counts(poisoned), [])

    def test_every_company_has_exactly_three_decision_makers(self):
        self.assertEqual(_check_three_per_company(self.fixture), [])
        for row in self.fixture["queue_records"]:
            self.assertEqual(len(row["contacts"]), CONTACTS_PER_COMPANY,
                             row["id"])

    def test_control_a_company_with_two_decision_makers_is_caught(self):
        """The operator's correction made three an EQUALITY. Under the old
        2-3 range this control would have passed, which is the point of it."""
        poisoned = self.poisoned()
        victim = poisoned["companies"][0]["id"]
        seen = 0
        kept = []
        for record in poisoned["records"]:
            if record["id"] == victim:
                seen += 1
                if seen > 2:
                    continue
            kept.append(record)
        poisoned["records"] = kept
        problems = _check_three_per_company(poisoned)
        self.assertNotEqual(problems, [])
        self.assertTrue(any("has 2 decision makers" in problem
                            for problem in problems), problems)

    def test_control_a_company_with_four_decision_makers_is_caught(self):
        poisoned = self.poisoned()
        extra = copy.deepcopy(poisoned["records"][0])
        extra["name"] = "Extra Mockworth"
        extra["key"] = "extra-mockworth"
        poisoned["records"].append(extra)
        self.assertNotEqual(_check_three_per_company(poisoned), [])


class DecisionMakers(SealedSandbox):

    def test_the_three_are_distinct_people_with_distinct_personas(self):
        self.assertEqual(_check_distinct_decision_makers(self.fixture), [])

    def test_control_the_same_person_twice_in_one_company_is_caught(self):
        poisoned = self.poisoned()
        first, second = poisoned["records"][0], poisoned["records"][1]
        self.assertEqual(first["id"], second["id"])
        for field in ("name", "email", "linkedin", "key"):
            second[field] = first[field]
        self.assertNotEqual(_check_distinct_decision_makers(poisoned), [])

    def test_control_two_distinct_people_sharing_a_persona_is_caught(self):
        poisoned = self.poisoned()
        first, second = poisoned["records"][0], poisoned["records"][1]
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(first["persona"], second["persona"])
        second["persona"] = first["persona"]
        self.assertNotEqual(_check_distinct_decision_makers(poisoned), [])

    def test_every_persona_is_one_the_client_config_declares(self):
        """READ FROM CONFIG, not hardcoded. `personas.classify` decides whether
        a contact is a persona by matching its title against exactly this
        list, so a title invented here would be set aside as "not a persona for
        this client" and the cohort would be empty in practice while looking
        full in the JSON."""
        declared = {}
        for family in ("champion", "economic_buyer"):
            declared[family] = {
                str(title).strip().lower() for title in
                (self.config["personas"][family]["titles"] or [])}
        self.assertTrue(declared["champion"])
        self.assertTrue(declared["economic_buyer"])
        for record in self.fixture["records"]:
            family = record["persona_family"]
            self.assertIn(record["persona"].lower(), declared[family],
                          "%s is not a %s title in config/clients/%s.yaml"
                          % (record["persona"], family,
                             sandbox_fixture.CLIENT))

    def test_the_four_champion_personas_the_brief_names_are_all_present(self):
        used = {record["persona"] for record in self.fixture["records"]}
        for persona in ("Operations Manager", "Operations Director",
                        "Project Manager", "Finance Manager"):
            self.assertIn(persona, used)

    def test_control_an_undeclared_persona_would_be_rejected_by_the_generator(self):
        """The generator itself refuses a persona the client does not list, so
        this cannot be shipped by editing BLOCKS alone."""
        original = sandbox_fixture.BLOCKS[0]["personas"]
        patched = (("Chief Vibes Officer", "champion", "operations"),
                   ) + tuple(original[1:])
        sandbox_fixture.BLOCKS[0]["personas"] = patched
        try:
            with self.assertRaises(ValueError):
                sandbox_fixture.build(SEED)
        finally:
            sandbox_fixture.BLOCKS[0]["personas"] = original
        # And the restore really restored, so no later test inherits this.
        self.assertEqual(sandbox_fixture.build(SEED)["counts"]["records"],
                         EXPECTED_RECORDS)


class LinkedInUrls(SealedSandbox):

    def test_every_record_has_a_url_that_survives_canonical(self):
        self.assertEqual(_check_linkedin(self.fixture), [])
        self.assertTrue(all(record.get("linkedin")
                            for record in self.fixture["records"]))

    def test_control_a_missing_url_is_caught(self):
        """The data-loss rule this fixture must not hide."""
        poisoned = self.poisoned()
        poisoned["records"][0]["linkedin"] = ""
        self.assertNotEqual(_check_linkedin(poisoned), [])

    def test_control_an_absent_url_field_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"][0].pop("linkedin")
        self.assertNotEqual(_check_linkedin(poisoned), [])

    def test_control_a_missing_url_on_the_contact_is_caught(self):
        poisoned = self.poisoned()
        poisoned["queue_records"][0]["contacts"][0]["linkedin"] = None
        self.assertNotEqual(_check_linkedin(poisoned), [])

    def test_control_a_non_profile_url_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"][0]["linkedin"] = "https://example.invalid/in/nope"
        self.assertIsNone(linkedin.canonical(poisoned["records"][0]["linkedin"]))
        self.assertNotEqual(_check_linkedin(poisoned), [])

    def test_control_a_non_canonical_spelling_is_caught(self):
        """It is a real profile URL and `canonical()` accepts it - it just is
        not already canonical, so storing it would make one person two keys."""
        poisoned = self.poisoned()
        url = "HTTPS://WWW.LinkedIn.com/in/Elspire-Invenby-Sandbox/?trk=x"
        poisoned["records"][0]["linkedin"] = url
        self.assertIsNotNone(linkedin.canonical(url))
        self.assertNotEqual(linkedin.canonical(url), url)
        self.assertNotEqual(_check_linkedin(poisoned), [])


class Emails(SealedSandbox):

    def test_every_email_is_incapable_of_resolving(self):
        self.assertEqual(_check_emails(self.fixture), [])
        for record in self.fixture["records"]:
            self.assertTrue(record["email"].endswith(".invalid"),
                            record["email"])

    def test_control_an_example_com_address_is_caught(self):
        """`example.com` was permitted by the first brief and is NOT permitted
        now. This control is the operator's correction, made executable."""
        poisoned = self.poisoned()
        poisoned["records"][0]["email"] = "ops.lead@example.com"
        self.assertNotEqual(_check_emails(poisoned), [])

    def test_control_an_example_com_address_on_a_contact_is_caught(self):
        poisoned = self.poisoned()
        poisoned["queue_records"][0]["contacts"][0]["email"] = "x@example.com"
        self.assertNotEqual(_check_emails(poisoned), [])

    def test_control_a_plain_com_address_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"][0]["email"] = "ops.lead@realagency.com"
        self.assertNotEqual(_check_emails(poisoned), [])

    def test_control_a_deliverable_tld_hidden_in_a_subdomain_is_caught(self):
        """`.invalid` has to be the TLD, not a label somewhere in the middle.
        `mail.invalid.example.com` resolves perfectly well."""
        poisoned = self.poisoned()
        poisoned["records"][0]["email"] = "ops@mail.invalid.example.com"
        self.assertNotEqual(_check_emails(poisoned), [])

    def test_control_a_non_invalid_company_domain_is_caught(self):
        poisoned = self.poisoned()
        poisoned["companies"][0]["domain"] = "realagency.com"
        self.assertNotEqual(_check_emails(poisoned), [])


class Cohorts(SealedSandbox):

    def test_six_cohorts_of_fifty_none_under_the_floor(self):
        self.assertEqual(_check_cohorts(self.fixture), [])
        sizes = {}
        for record in self.fixture["records"]:
            sizes[record["cohort"]] = sizes.get(record["cohort"], 0) + 1
        self.assertEqual(len(sizes), 6)
        self.assertEqual(sorted(sizes.values()), [50] * 6)

    def test_every_cohort_is_homogeneous_in_all_five_dimensions(self):
        self.assertEqual(_check_cohorts(self.fixture), [])
        for key in {record["cohort"] for record in self.fixture["records"]}:
            held = [record for record in self.fixture["records"]
                    if record["cohort"] == key]
            for dimension in COHORT_DIMENSIONS:
                self.assertEqual(len({record[dimension] for record in held}), 1,
                                 "%s is mixed in %s" % (key, dimension))

    def test_control_a_cohort_under_fifty_is_caught(self):
        poisoned = self.poisoned()
        victim = poisoned["cohorts"][0]["key"]
        kept, dropped = [], 0
        for record in poisoned["records"]:
            if record["cohort"] == victim and dropped < 5:
                dropped += 1
                continue
            kept.append(record)
        poisoned["records"] = kept
        problems = _check_cohorts(poisoned)
        self.assertNotEqual(problems, [])
        self.assertTrue(any("under the floor" in problem
                            for problem in problems), problems)

    def test_control_a_mixed_geo_cohort_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"][0]["geo"] = "Australia"
        problems = _check_cohorts(poisoned)
        self.assertNotEqual(problems, [])
        self.assertTrue(any("geo" in problem for problem in problems), problems)

    def test_control_a_mixed_persona_cohort_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"][0]["persona"] = "CEO"
        problems = _check_cohorts(poisoned)
        self.assertNotEqual(problems, [])
        self.assertTrue(any("persona" in problem for problem in problems),
                        problems)

    def test_control_a_mixed_headcount_band_cohort_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"][0]["headcount_band"] = "500+"
        self.assertNotEqual(_check_cohorts(poisoned), [])

    def test_control_a_mixed_signal_cohort_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"][0]["signal"] = "something_else"
        self.assertNotEqual(_check_cohorts(poisoned), [])

    def test_control_a_mixed_industry_cohort_is_caught(self):
        poisoned = self.poisoned()
        poisoned["records"][0]["industry"] = "Logistics"
        self.assertNotEqual(_check_cohorts(poisoned), [])


class RecordShape(SealedSandbox):
    """The shape the EXISTING production flow consumes, not a nearby one."""

    def test_every_queue_row_has_the_live_record_and_contact_shape(self):
        self.assertEqual(_check_record_shape(self.fixture), [])

    def test_control_a_contact_with_no_key_is_caught(self):
        poisoned = self.poisoned()
        poisoned["queue_records"][0]["contacts"][0].pop("key")
        self.assertNotEqual(_check_record_shape(poisoned), [])

    def test_control_a_positional_contact_key_is_caught(self):
        """`store.validate` accepts `c1` - its only rule is one key per
        contact - so this is the failure nothing else would report."""
        poisoned = self.poisoned()
        poisoned["queue_records"][0]["contacts"][0]["key"] = "c1"
        problems = _check_record_shape(poisoned)
        self.assertNotEqual(problems, [])
        self.assertEqual(store.validate(poisoned["queue_records"][0]), [],
                         "store.validate was expected NOT to catch this")

    def test_control_a_missing_top_level_field_is_caught(self):
        poisoned = self.poisoned()
        poisoned["queue_records"][0].pop("qualification")
        self.assertNotEqual(_check_record_shape(poisoned), [])

    def test_control_cadence_steps_under_the_wrong_key_is_caught(self):
        """`cadence` and `cadence_steps` are different keys. Steps under the
        wrong one give "not part of the configured cadence for this contact"
        on every step and no other error at all."""
        poisoned = self.poisoned()
        row = poisoned["queue_records"][0]
        row["cadence"] = row.pop(cadence.CADENCE_KEY)
        problems = _check_record_shape(poisoned)
        self.assertNotEqual(problems, [])
        self.assertTrue(any(cadence.CADENCE_KEY in problem
                            for problem in problems), problems)

    def test_the_cadence_steps_are_the_real_seven(self):
        self.assertEqual(cadence.CADENCE_KEY, "cadence_steps")
        for row in self.fixture["queue_records"]:
            steps = row[cadence.CADENCE_KEY]
            self.assertEqual([step["key"] for step in steps],
                             [step["key"] for step in cadence.STEPS])

    def test_control_an_invented_provider_field_is_caught(self):
        """A synthetic `mx` or `verdict` is a fact about the world nothing here
        looked up. `verdict` is the sharper one: `legacy_evidence` reads it and
        would count it as a THIRD confirmation nobody obtained."""
        for field in sandbox_fixture.NULL_WITHOUT_A_PROVIDER:
            poisoned = self.poisoned()
            poisoned["queue_records"][0]["contacts"][0][field] = "valid"
            problems = _check_record_shape(poisoned)
            self.assertNotEqual(problems, [], field)
            self.assertTrue(any("without a provider" in problem
                                for problem in problems), (field, problems))


class Research(SealedSandbox):
    """Facts the real copy path can actually use."""

    def test_every_research_item_is_a_scored_evidence_object_that_licenses(self):
        self.assertEqual(_check_research(self.fixture), [])

    def test_the_facts_score_usable_not_merely_present(self):
        qualities = {item["quality"]
                     for row in self.fixture["queue_records"]
                     for item in row["research"]}
        self.assertTrue(qualities)
        self.assertEqual(qualities - set(evidence.USABLE), set(),
                         "some evidence is not USABLE, so the copy path would "
                         "fall back to persona pain")

    def test_control_a_hand_built_research_dict_is_caught(self):
        """The first draft of the generator hand-built these. It raises
        `AttributeError: 'str' object has no attribute 'get'` inside
        `quality._selected`, which is a long way from the cause."""
        poisoned = self.poisoned()
        poisoned["queue_records"][0]["research"] = [
            {"fact": "something true", "source_url": "https://x.invalid/a"}]
        problems = _check_research(poisoned)
        self.assertNotEqual(problems, [])
        self.assertTrue(any("missing" in problem for problem in problems),
                        problems)

    def test_control_an_unusable_fact_is_caught(self):
        """It is present, it is licensed, and the copy path cannot write from
        it. A count of facts sees four either way."""
        poisoned = self.poisoned()
        row = poisoned["queue_records"][0]
        weak = evidence.make(
            fact="We are a friendly team and we love what we do here.",
            source_url="https://%s/about" % row["domain"],
            source_type="synthetic_fixture", provider="sandbox",
            record_id=row["id"], published_at="2026-09-01",
            today="2026-10-12")
        self.assertNotIn(weak["quality"], evidence.USABLE)
        row["research"][0] = weak
        problems = _check_research(poisoned)
        self.assertNotEqual(problems, [])
        self.assertTrue(any("scores" in problem for problem in problems),
                        problems)

    def test_control_an_offsite_source_url_stops_licensing(self):
        """`packfacts.identity_of` admits a fact whose source is same-site with
        the record's own domain. Point it elsewhere and the copy path has
        nothing licensed to say - which a count of facts would not notice."""
        poisoned = self.poisoned()
        row = poisoned["queue_records"][0]
        for item in row["research"]:
            item["source_url"] = "https://somewhere-else.invalid/page"
        pack, _unused = packfacts.pack_for(row)
        self.assertEqual(pack["facts"], [])
        self.assertNotEqual(_check_research(poisoned), [])

    def test_control_a_missing_personalization_link_is_caught(self):
        """Without `selected_evidence_ids` personalisation quality cannot be
        computed, and the evidence sitting on the record does not help."""
        poisoned = self.poisoned()
        poisoned["queue_records"][0]["contacts"][0].pop("personalization")
        problems = _check_research(poisoned)
        self.assertNotEqual(problems, [])
        self.assertTrue(any("selected_evidence_ids" in problem
                            for problem in problems), problems)

    def test_control_a_dangling_evidence_id_is_caught(self):
        poisoned = self.poisoned()
        (poisoned["queue_records"][0]["contacts"][0]["personalization"]
         ["selected_evidence_ids"]) = ["ev_doesnotexist"]
        self.assertNotEqual(_check_research(poisoned), [])

    def test_every_source_url_is_fake_and_unfetchable(self):
        for row in self.fixture["queue_records"]:
            for item in row["research"]:
                host = item["source_url"].split("//", 1)[-1].split("/", 1)[0]
                self.assertTrue(host.endswith(".invalid"), item["source_url"])
                self.assertTrue(packfacts.same_site(host, row["domain"]),
                                item["source_url"])


class Sendability(SealedSandbox):
    """The zero-credit email path, and proof the policy is enforced not bypassed."""

    def test_the_client_policy_is_the_one_we_think_it_is(self):
        self.assertEqual(self.policy["primary"], "deliverable")
        self.assertEqual(self.policy["secondary"], "reoon")
        self.assertEqual(self.policy["required_confirmations"], 2)
        self.assertFalse(self.policy["trust_secondary_when_primary_unknown"])

    def test_every_contact_is_sendable_and_the_stored_flag_agrees(self):
        self.assertEqual(_check_sendability(self.fixture, self.policy), [])
        row = self.fixture["queue_records"][0]
        decision = verification.resolve(row["contacts"][0], self.policy)
        self.assertTrue(decision["sendable"])
        self.assertEqual(decision["confirmation_count"], 2)
        self.assertEqual(sorted(decision["confirmed_by"]),
                         ["deliverable", "reoon"])

    def test_control_one_confirmation_alone_is_not_sendable(self):
        """THE POLICY CONTROL. Two independent providers are required, and
        this proves the requirement bites rather than being decoration."""
        poisoned = self.poisoned()
        contact = poisoned["queue_records"][0]["contacts"][0]
        contact["verification"]["evidence"] = \
            contact["verification"]["evidence"][:1]
        self.assertFalse(verification.is_sendable(contact, self.policy))
        self.assertEqual(
            verification.resolve(contact, self.policy)["confirmation_count"], 1)
        self.assertNotEqual(_check_sendability(poisoned, self.policy), [])

    def test_control_evidence_for_a_different_address_is_not_sendable(self):
        """Evidence is ADDRESS-BOUND by construction, so verdicts about
        somebody else's mailbox cannot clear this one. Without this, a fixture
        could carry two valid verdicts that were never about its own address."""
        poisoned = self.poisoned()
        contact = poisoned["queue_records"][0]["contacts"][0]
        self.assertTrue(contact["email"].endswith(".invalid"))
        for entry in contact["verification"]["evidence"]:
            entry["email"] = "someone.else@elsewhere.invalid"
        self.assertFalse(verification.is_sendable(contact, self.policy))
        self.assertNotEqual(_check_sendability(poisoned, self.policy), [])

    def test_control_a_stored_sendable_flag_cannot_fake_it(self):
        """`is_sendable` recomputes and never reads the stored flag, so this
        poisoning changes nothing about sendability - and the checker catches
        the DISAGREEMENT between the two, which is the only visible symptom."""
        poisoned = self.poisoned()
        contact = poisoned["queue_records"][0]["contacts"][0]
        contact["verification"] = {"evidence": []}
        contact["sendable"] = True
        self.assertFalse(verification.is_sendable(contact, self.policy))
        problems = _check_sendability(poisoned, self.policy)
        self.assertNotEqual(problems, [])
        self.assertTrue(any("stored sendable=True" in problem
                            for problem in problems), problems)

    def test_no_verdict_charged_a_credit(self):
        for row in self.fixture["queue_records"]:
            for contact in row["contacts"]:
                for entry in contact["verification"]["evidence"]:
                    self.assertIs(entry["charged"], False)
                    self.assertIn("synthetic", str(entry["reason"]).lower())


class Determinism(SealedSandbox):

    def _generate(self, seed, name):
        out = os.path.join(self.tmp, name)
        sandbox_fixture.write(sandbox_fixture.build(seed), out)
        with open(out, "rb") as handle:
            return handle.read()

    def test_the_same_seed_twice_is_byte_identical(self):
        first = self._generate(SEED, "first.json")
        second = self._generate(SEED, "second.json")
        self.assertEqual(hashlib.md5(first).hexdigest(),
                         hashlib.md5(second).hexdigest())
        self.assertEqual(first, second)

    def test_a_different_seed_is_different_data(self):
        """Different BYTES is the weak half; different PEOPLE is the point. A
        generator that reseeded only the whitespace would pass the first."""
        mine = sandbox_fixture.build(SEED)
        theirs = sandbox_fixture.build(OTHER_SEED)
        self.assertNotEqual(sandbox_fixture.dumps(mine),
                            sandbox_fixture.dumps(theirs))
        self.assertNotEqual({record["name"] for record in mine["records"]},
                            {record["name"] for record in theirs["records"]})
        self.assertNotEqual({company["domain"]
                             for company in mine["companies"]},
                            {company["domain"]
                             for company in theirs["companies"]})

    def test_a_different_seed_keeps_every_structural_invariant(self):
        """The partition is structure, not seeded data: a second seed must
        move the names and keep the cohorts."""
        other = sandbox_fixture.build(OTHER_SEED)
        for checker in (_check_counts, _check_three_per_company,
                        _check_distinct_decision_makers, _check_linkedin,
                        _check_emails, _check_cohorts, _check_record_shape,
                        _check_research):
            self.assertEqual(checker(other), [], checker.__name__)
        self.assertEqual(_check_sendability(other, self.policy), [])

    def test_no_wall_clock_leaked_into_the_bytes(self):
        """The two clock seams that actually bit: `verification.result`
        defaults `at` to `store.now()`, and `evidence.make` measures freshness
        from `today`. Both are passed fixed values, so the same seed is
        identical tomorrow - which a same-process double run cannot show."""
        fixture = sandbox_fixture.build(SEED)
        for row in fixture["queue_records"]:
            for contact in row["contacts"]:
                for entry in contact["verification"]["evidence"]:
                    self.assertEqual(entry["at"], sandbox_fixture.VERDICT_AT)
            for item in row["research"]:
                self.assertEqual(item["retrieved_at"],
                                 sandbox_fixture.WINDOW_START.isoformat())
                self.assertIsNotNone(item["age_days"])
        stamped = sandbox_fixture.dumps(fixture)
        self.assertNotIn(store.now()[:10], stamped.replace(
            sandbox_fixture.WINDOW_START.isoformat(), ""))

    def test_the_generator_is_deterministic_across_processes(self):
        """Same seed, a FRESH interpreter, identical bytes. Hash randomisation
        and dict iteration order live in the process, so two calls inside one
        process cannot see a defect that only a new process would show."""
        first = os.path.join(self.tmp, "proc-a.json")
        second = os.path.join(self.tmp, "proc-b.json")
        for out in (first, second):
            result = subprocess.run(
                [sys.executable, os.path.join(ROOT, "scripts",
                                              "sandbox_fixture.py"),
                 "--seed", str(SEED), "--out", out],
                cwd=ROOT, capture_output=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        with open(first, "rb") as handle:
            left = handle.read()
        with open(second, "rb") as handle:
            right = handle.read()
        self.assertEqual(hashlib.md5(left).hexdigest(),
                         hashlib.md5(right).hexdigest())

    def test_the_committed_seed_files_match_the_generator(self):
        """The two files in `docs/sandbox/` are the artefact the operator
        compares. If the generator changes and they are not regenerated, this
        says so instead of the diff being discovered later."""
        for seed in (SEED, OTHER_SEED):
            path = os.path.join(ROOT, "docs", "sandbox",
                                "fixture-seed-%d.json" % seed)
            self.assertTrue(os.path.exists(path), path)
            with open(path, "rb") as handle:
                committed = handle.read()
            self.assertEqual(
                committed.decode("utf-8"),
                sandbox_fixture.dumps(sandbox_fixture.build(seed)),
                "%s is stale - regenerate it" % path)


class DomainSafetyBothDirections(SealedSandbox):
    """The important one. Two directions, two failure modes, two controls."""

    def synthetic_domains(self):
        domains = {company["domain"].lower()
                   for company in self.fixture["companies"]}
        self.assertEqual(len(domains), EXPECTED_COMPANIES)
        return domains

    def real_domains(self):
        """The live-customer roster plus the client's own domain."""
        roster = _roster_domains(SUPPRESS_LOCAL)
        self.assertGreaterEqual(
            len(roster), SUPPRESS_LOCAL_MINIMUM,
            "%s holds %d domains, fewer than the %d the brief names - a "
            "truncated roster excludes nothing while looking like a roster "
            "that matches nothing" % (SUPPRESS_LOCAL, len(roster),
                                      SUPPRESS_LOCAL_MINIMUM))
        self.assertIn(ROSTER_SENTINEL, roster,
                      "%s does not contain %s, so the file that loaded is not "
                      "the real roster" % (SUPPRESS_LOCAL, ROSTER_SENTINEL))
        client_domain = str(self.config.get("domain") or "").strip().lower()
        self.assertTrue(client_domain,
                        "config/clients/%s.yaml declares no domain"
                        % sandbox_fixture.CLIENT)
        return set(roster) | {client_domain}

    # ---------------------------------------------------- direction (a)

    def test_no_synthetic_domain_appears_in_production_state(self):
        """The PLAINTEXT scan, over the files that actually hold plaintext."""
        synthetic = self.synthetic_domains()
        for name in PLAINTEXT_STATE:
            path = self.prod_paths[name]
            blob = _read(path)
            self.assertTrue(blob.strip(),
                            "%s is empty, so this scan proves nothing" % path)
            self.assertEqual(
                _domain_hits(synthetic, blob), [],
                "a synthetic domain is present in production %s" % name)
        roster = _read(SUPPRESS_LOCAL)
        self.assertTrue(roster.strip())
        self.assertEqual(_domain_hits(synthetic, roster), [],
                         "a synthetic domain is on the live-customer roster")

    def test_the_agency_dnc_holds_no_plaintext_at_all(self):
        """WHY THE DNC IS NOT IN THE SCAN ABOVE, AND THIS IS A FINDING.

        `work/agency-dnc.jsonl` stores ONLY `sha256("email:<address>")` and
        `sha256("linkedin:<url>")` - that is its privacy model, deliberately:
        "The file cannot be read to enumerate anybody."

        So a scan of that file for synthetic DOMAINS can never match, whatever
        the data. The brief asked for one, and it would have been a check
        incapable of failing - which is why the control for it failed on first
        run with "no host-like token in the DNC file" rather than passing
        quietly. This test pins the reason down as a property, and the next
        test asks the real question the right way.
        """
        dnc = _read(self.prod_paths["agency-dnc.jsonl"])
        self.assertTrue(dnc.strip())
        hosts = re.findall(r'[a-z0-9][a-z0-9-]*\.[a-z]{2,}', dnc.lower())
        self.assertEqual(hosts, [],
                         "the DNC now holds plaintext hosts, so it must be "
                         "added to PLAINTEXT_STATE above")
        self.assertEqual(_domain_hits({"@"}, dnc), [],
                         "the DNC now holds addresses")

    def test_no_synthetic_contact_is_on_the_agency_dnc(self):
        """The real question, asked the way the DNC answers it.

        `agencydnc.keys_for` builds the hashed keys for a candidate from its
        normalised email and canonical LinkedIn URL, which is exactly how the
        live import tests membership. Intersecting those against the loaded
        index is a check that CAN fail, unlike a domain scan of the same file.
        """
        index = agencydnc.load(self.prod_paths["agency-dnc.jsonl"])
        self.assertTrue(index, "the agency DNC loaded empty, so this proves "
                               "nothing")
        self.assertEqual(len(index), 15)
        for row in self.fixture["queue_records"]:
            for contact in row["contacts"]:
                keys = agencydnc.keys_for(contact)
                self.assertTrue(keys, "%s/%s produced no DNC keys at all"
                                % (row["id"], contact["key"]))
                self.assertEqual(
                    sorted(set(keys.values()) & set(index)), [],
                    "%s/%s is on the agency do-not-contact list"
                    % (row["id"], contact["key"]))

    def test_control_the_dnc_check_fires_on_a_fingerprinted_contact(self):
        """THE CONTROL FOR THE DNC, and it has to be done by FINGERPRINTING a
        synthetic contact rather than by planting a needle: the hash cannot be
        inverted, so there is no plaintext to plant.

        Written into a COPY in the temp directory. The real file is never
        opened for writing, and `addCleanup` re-checks its md5, mtime and size.
        """
        contact = self.fixture["queue_records"][0]["contacts"][0]
        copied = os.path.join(self.tmp, "agency-dnc.jsonl")
        with open(self.prod_paths["agency-dnc.jsonl"], encoding="utf-8") as src:
            original = src.read()
        with open(copied, "w", encoding="utf-8") as handle:
            handle.write(original)

        before = agencydnc.load(copied)
        self.assertEqual(sorted(set(agencydnc.keys_for(contact).values())
                                & set(before)), [])

        written = agencydnc.add("email",
                                dedupe.normalise_email(contact["email"]),
                                file_path=copied)
        after = agencydnc.load(copied)
        self.assertIn(written, after)
        self.assertEqual(len(after), len(before) + 1)
        hit = sorted(set(agencydnc.keys_for(contact).values()) & set(after))
        self.assertEqual(hit, [written],
                         "the DNC matcher missed a contact it had just been "
                         "given")
        # And the plaintext address still is not in the file - which is the
        # point of the fingerprint, and why the domain scan could not work.
        self.assertNotIn(contact["email"], _read(copied))

    def test_control_direction_a_fires_on_a_domain_really_in_the_queue(self):
        """THE CONTROL FOR (a). The needle is read OUT OF the real queue at
        runtime, so this proves two things at once: the scanner finds what is
        there, and the file it scanned actually had content. A control using an
        invented needle would prove only the regex compiles."""
        queue = _read(self.prod_paths["queue.jsonl"])
        found = re.findall(r'"domain":\s*"([^"]+)"', queue[:4_000_000])
        self.assertTrue(found, "no domain field in the production queue")
        planted = found[0].lower()
        self.assertFalse(planted.endswith(".invalid"), planted)
        hits = _domain_hits(self.synthetic_domains() | {planted}, queue)
        self.assertEqual(hits, [planted],
                         "the scanner missed a domain known to be in the file")

    def test_control_direction_a_fires_on_the_small_campaigns_file(self):
        """`campaigns.jsonl` is 115 KB, not 27 MB, and a scanner only ever
        tried on the big file is a scanner that was never tried on this one."""
        campaigns = _read(self.prod_paths["campaigns.jsonl"])
        self.assertTrue(campaigns.strip())
        found = re.findall(r'[a-z0-9][a-z0-9-]*\.[a-z]{2,}', campaigns.lower())
        self.assertTrue(found, "no host-like token in campaigns.jsonl")
        planted = found[0]
        self.assertFalse(planted.endswith(".invalid"), planted)
        hits = _domain_hits(self.synthetic_domains() | {planted}, campaigns)
        self.assertIn(planted, hits)

    # ---------------------------------------------------- direction (b)

    def test_no_real_client_domain_appears_in_the_fixture(self):
        real = self.real_domains()
        blob = sandbox_fixture.dumps(self.fixture)
        self.assertEqual(
            _domain_hits(real, blob), [],
            "a real client domain is present in the synthetic fixture")

    def test_control_direction_b_fires_on_an_injected_client_domain(self):
        """THE CONTROL FOR (b), and a separate one on purpose: it fails for a
        different reason than (a) - a live customer pulled into synthetic data
        is a customer who can be cold-sequenced out of a sandbox."""
        real = self.real_domains()
        poisoned = self.poisoned()
        poisoned["companies"][0]["domain"] = ROSTER_SENTINEL
        blob = sandbox_fixture.dumps(poisoned)
        self.assertEqual(_domain_hits(real, blob), [ROSTER_SENTINEL])

    def test_control_direction_b_fires_on_a_domain_buried_in_a_fact(self):
        """A real domain can arrive anywhere, not only in the `domain` field -
        a research snippet or a source URL is exactly where one would hide.

        THE NEEDLE IS READ FROM THE ROSTER AT RUNTIME AND NEVER WRITTEN DOWN
        HERE. `config/suppress.local.txt` is gitignored because "who is paying
        us is confidential, and a tracked file reaches every clone, every fork
        and every backup of this repository" - so hardcoding one of its
        domains into this tracked test file would publish a customer name and
        undo the whole reason that file is untracked. An earlier draft of this
        test did exactly that. The assertion is just as strong taking the
        needle from the file.
        """
        real = self.real_domains()
        needle = sorted(real - {ROSTER_SENTINEL})[0]
        poisoned = self.poisoned()
        row = poisoned["queue_records"][0]
        row["research"][0]["fact"] += " See also %s for context." % needle
        blob = sandbox_fixture.dumps(poisoned)
        self.assertIn(needle, _domain_hits(real, blob))
        # And the clean fixture does not contain it, so the hit above is the
        # poisoning rather than something already there.
        self.assertNotIn(needle,
                         _domain_hits(real, sandbox_fixture.dumps(
                             self.fixture)))

    def test_every_real_roster_domain_is_individually_detectable(self):
        """Each of the roster's domains, one at a time, proving the clean scan
        is not passing because one needle in the alternation is malformed."""
        clean = sandbox_fixture.dumps(self.fixture)
        for domain in sorted(self.real_domains()):
            self.assertEqual(_domain_hits({domain}, clean), [], domain)
            self.assertEqual(_domain_hits({domain}, clean + "\n%s\n" % domain),
                             [domain], domain)


class ProductionStateUntouched(SealedSandbox):
    """mtime AND size, asserted explicitly as well as in every addCleanup."""

    def test_production_queue_mtime_and_size_unchanged_by_generating(self):
        path = self.prod_paths["queue.jsonl"]
        before = (os.path.getmtime(path), os.path.getsize(path), _md5(path))
        sandbox_fixture.write(sandbox_fixture.build(SEED),
                              os.path.join(self.tmp, "out.json"))
        after = (os.path.getmtime(path), os.path.getsize(path), _md5(path))
        self.assertEqual(before, after)

    def test_control_the_mtime_and_size_comparison_can_fail(self):
        """The positive control for the before/after itself. A comparison
        nobody has seen fail is the shape of `_md5` answering None twice,
        which is exactly what this file would do against a worktree."""
        decoy = os.path.join(self.tmp, "decoy.jsonl")
        with open(decoy, "w", encoding="utf-8") as handle:
            handle.write('{"id": "x"}\n')
        before = (os.path.getmtime(decoy), os.path.getsize(decoy), _md5(decoy))
        with open(decoy, "a", encoding="utf-8") as handle:
            handle.write('{"id": "y"}\n')
        os.utime(decoy, (before[0] + 120, before[0] + 120))
        after = (os.path.getmtime(decoy), os.path.getsize(decoy), _md5(decoy))
        self.assertNotEqual(before, after)
        self.assertNotEqual(before[0], after[0], "mtime did not move")
        self.assertNotEqual(before[1], after[1], "size did not move")
        self.assertNotEqual(before[2], after[2], "md5 did not move")

    def test_nothing_was_written_into_the_redirected_sandbox_either(self):
        """The generator writes a JSON document and no queue state. If it ever
        starts calling `store.append`, this fails in the temp directory rather
        than being discovered in production."""
        sandbox_fixture.write(sandbox_fixture.build(SEED),
                              os.path.join(self.tmp, "out.json"))
        self.assertFalse(os.path.exists(store.queue_path()),
                         "the generator wrote queue state")
        self.assertFalse(os.path.exists(store.campaigns_path()),
                         "the generator wrote campaign state")


class ZeroDataSpend(SealedSandbox):
    """No provider, no network, no credit - as structure, not as a promise."""

    BANNED = ("contactout", "aiark", "ai_ark", "reoon", "cheapverifier",
              "deliverable", "apify", "requests", "urllib.request",
              "urllib", "httpx", "socket", "http.client", "src.providers",
              "src.enrich", "src.webfetch", "src.mx", "src.push",
              "src.dispatch")

    # The pure modules the generator is allowed to read a SHAPE from.
    ALLOWED_SRC = {"src", "src.store", "src.cadence", "src.clients",
                   "src.evidence", "src.verification"}

    def _imports(self):
        import ast
        path = os.path.join(ROOT, "scripts", "sandbox_fixture.py")
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                names.add(base)
                for alias in node.names:
                    names.add("%s.%s" % (base, alias.name) if base
                              else alias.name)
        return {name.lower() for name in names if name}

    def test_the_generator_imports_no_provider_and_no_network_module(self):
        imported = self._imports()
        for banned in self.BANNED:
            self.assertNotIn(banned, imported, "%s is imported" % banned)
        from_src = {name for name in imported
                    if name == "src" or name.startswith("src.")}
        self.assertEqual(from_src - self.ALLOWED_SRC, set(),
                         "the generator imports src modules outside the pure "
                         "allowlist")

    def test_control_the_import_scan_sees_an_import_that_is_there(self):
        """It really does find the modules that ARE imported, so a clean
        result above is a clean file rather than a scanner finding nothing."""
        imported = self._imports()
        self.assertIn("src.store", imported)
        self.assertIn("src.verification", imported)
        self.assertIn("random", imported)

    def test_control_the_banned_list_would_catch_a_provider_import(self):
        """A scanner is only as good as its list. This proves the list and the
        matcher agree on a name that is genuinely a provider."""
        self.assertIn("src.providers", self.BANNED)
        fake = {"json", "src.providers"}
        self.assertTrue([b for b in self.BANNED if b in fake])

    def test_the_fixture_declares_zero_spend(self):
        self.assertEqual(self.fixture["provider_calls"], 0)
        self.assertEqual(self.fixture["data_credits_spent"], 0)
        self.assertTrue(self.fixture["synthetic"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
