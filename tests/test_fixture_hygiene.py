"""Nothing tracked in git may name a real person, customer or prospect.

Git is for ever. A real customer domain, a real colleague's work address or a
line of real CRM narrative in a tracked file is a data incident that no later
cleanup fully undoes - deleting it from HEAD leaves it in every clone and every
blob. So this scans mechanically, and it scans EVERYTHING tracked rather than
just the fixtures.

Scope note, and it is the point of this file's history: this guard used to walk
`tests/` only, and BUILD-SPEC.md, PLAYBOOK.md and prototype/ were deliberately
excluded because "the real examples in those are the author's own". That
exclusion is what let a named real person, a live prospect's address and the
paying-customer roster sit in tracked source until a pre-GitHub audit found
them. Whose data it is does not change what a push does with it, so the
exclusion is gone and the scan is repository-wide.

The rules below are deliberately of two kinds:

  ABSOLUTE  - a property every tracked file must have, with no allowlist. These
              cannot rot, and they are the load-bearing ones. The strongest is
              "every email address in this repository is on a reserved domain":
              it needs no list of who is real, so it catches the name nobody
              thought to add.

  KNOWN-SET - a small, enumerated set of values that are allowed to appear
              (phone numbers). These trip only on something genuinely new,
              which is a human classification decision rather than a false
              positive.

What is deliberately NOT flagged: email-gateway vendor hostnames (proofpoint,
mimecast, barracuda and friends in `src/mx.py`), provider API base URLs, and
Resonate's own domain. Those are infrastructure this system talks to, they are
public, and treating them as PII would make this file noise that gets skipped.
"""
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Reserved and example domains, safe by RFC 2606 / RFC 6761. Nothing here can
# resolve, so nothing here can be contacted by accident.
SAFE_SUFFIXES = (".test", ".example", "example.com", "example.org",
                 "example.net", "localhost", ".invalid")

# Real domains this project has touched: clients, suppressed accounts,
# prospects, and the estates seen through a provider credential. Every one of
# these was in tracked source at some point; none may return.
FORBIDDEN_DOMAINS = (
    # prospects and third parties
    "arbona.hr", "bornfight.com", "five.agency", "beauhurst.com", "robotiq.ai",
    "levelupleads.io", "whatson.ai", "fornate.com", "leapin.co", "jobadder.com",
    "321webmarketing.com", "20northmarketing.com", "adcreations.com",
    "adcuratio.com", "1secondleads.com", "28row.com", "adblend.co",
    "anewagencyworld.com", "aubryandco.com", "arcoagency.se", "nineyards.ie",
    "thirtythree-usa.com",
    # the paying-customer roster
    "clay.com", "relpro.com", "auvale.de", "alta.com", "tawk.to",
    "synquery.com", "farseer.io", "q-agency.com", "netnada.com.au",
    "nextoria.com", "cyber64.hr", "productive.io",
    # client sending infrastructure
    "goproductive.online", "goproductive.net", "goproductivelab.com",
    "goproductivelabs.live", "tryproductive.online", "withproductive.online",
    "gonetnada.com", "trynetnada.live", "netnadadigital.shop",
    # our own people's addresses belong outside git too
    "contactout.io",
)

# Real people, and the real client/estate names that are roster disclosure in
# themselves. Lower-cased; matched as substrings.
FORBIDDEN_NAMES = (
    "mahovic", "mahović", "klaric", "klarić", "blackler", "hopkins",
    "gudelj", "galic", "galić", "ivce", "pavlovic", "pavlović",
    "van ulden", "baauw", "karsant", "lucic", "gokdeniz", "beslic", "beslić",
    "brooke baron", "brookebaron", "josephoneill", "joseph o'neill",
    "lingenfelter", "dahlstrom",
    "mediaboard", "netnada", "cyber64",
    # Bare company and given-name tokens, without the domain or surname.
    # A prospect reaches a draft as "hi Brooke, ... how Nineyards handles it",
    # which carries no address and no TLD and so matched nothing above. That
    # is the shape real data actually arrives in here - generated copy, not a
    # fixture row - and it is why this block exists as well as the domains.
    "nineyards", "brooke", "arbona", "bornfight", "jobadder", "adcuratio",
    "adcreations", "321webmarketing", "20northmarketing", "1secondleads",
    "28row", "adblend", "anewagencyworld", "aubryandco", "arcoagency",
    "thirtythree-usa", "goproductive", "gonetnada", "trynetnada",
    # THE CLIENT'S OWN SENDING ROSTER, added 2026-09-17, and it is the gap
    # this list had rather than an extension of its scope. Every name above
    # is a PROSPECT or one of ours; none is a person who SENDS. So on
    # 2026-09-17 three tracked files - a design document, a task result and
    # `attach_sender_to_487.py` - named the ten humans who own the 225 inboxes,
    # and all thirteen assertions here passed. A guard that knows the people
    # we write TO and not the people we write AS is half a guard.
    #
    # Surnames only, matched as substrings, which is the same trade the block
    # above already makes: this file has to name what it forbids in order to
    # forbid it, and these names are already in the repository's history.
    # `scripts/email_sender_estate.py` prints the roster live for anyone
    # holding the credential, which is where it belongs.
    "vrbat", "simicic", "simcic", "rendulic", "mamic", "mamić",
    "vizintin", "vižintin", "zrncevic", "zrnčević", "tomislav car",
    # THE HANDLE, NOT ONLY THE SURNAME. Added 2026-09-23 after the operator's
    # own LinkedIn vanity name reached a tracked document
    # (`HUMAN-ACTIONS-REQUIRED.md`, 17:21) and a second one reached a script
    # comment as an attribution.
    #
    # `beslic` above already matched it as a substring, so this adds no
    # coverage the guard did not have - it adds a LEGIBLE FAILURE. The report
    # read `HUMAN-ACTIONS-REQUIRED.md: beslic`, which sends the next reader
    # looking for a surname in prose when what is actually in the file is a
    # profile URL. A guard that is right about the violation and misleading
    # about its shape costs the time it was meant to save.
    #
    # NOTE FOR ANYONE TEMPTED THE OTHER WAY: the fix for a real name in a
    # tracked file is to remove the name, never to add it to `FAKE_VANITY`
    # below. That list is an allowlist of INVENTED handles; putting a real
    # one in it would retire the guard for exactly the person it protects.
    "zbeslic",
)

# Figures read from a real provider account. A count is not anonymous when it
# is the client's business volume.
FORBIDDEN_FIGURES = (
    # ContactOut account
    "179268", "142737", "39826", "119616", "54317", "32509",
    # EmailBison estate
    "189,683", "189683", "269,973", "269973", "27,144", "27144",
    "17,362", "17362", "1,853",
)

# The only phone numbers allowed to appear anywhere. Every one is in a range
# reserved for fiction (Ofcom drama, 555, or plainly impossible digits).
ALLOWED_PHONES = {
    "+1234567890", "+385 1 555 0100", "+385000000000",
    "+44 20 7000 0000", "+44 20 7946 0000",
}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE = re.compile(r"\+\d[\d ().-]{7,}\d")

TEXT_SUFFIXES = (".py", ".json", ".jsonl", ".csv", ".txt", ".md", ".yaml",
                 ".yml", ".cfg", ".ini", ".toml", ".html", ".js", ".css")

SELF = "tests/test_fixture_hygiene.py"

#: THE ONE EXEMPTION, AND IT IS NARROW ON PURPOSE.
#:
#: OPERATOR DECISION, 2026-09-23: the test identity may be named in these two
#: files and nowhere else.
#:
#: `src/testidentity.py` exists because a `positive_reply` for the operator's
#: own test identity was routed to A CLIENT'S OWN CHANNEL - the client would
#: have been told a prospect was interested when the "prospect" was the
#: operator exercising a cross-channel stop. The module suppresses that at
#: the write (`notify.plan`) and at the read (the reply counts).
#:
#: **AN EXCLUSION HAS TO BE ABLE TO NAME WHAT IT EXCLUDES.** So a safety
#: mechanism needs exactly the value this guard forbids, and the two cannot
#: both be satisfied by argument. One of them has to give, deliberately.
#:
#: The alternative was moving the value into gitignored config. Rejected, on
#: the rule this repository already has about safety paths: a config read
#: that fails would leave the exclusion silently not working, and a
#: suppression that quietly stops suppressing is worse than a name in a
#: tracked file we chose to put there.
#:
#: SCOPED TO THE THREE IDENTITY CHECKS - the name, the LinkedIn handle and
#: the ADDRESS. All three for the same reason and no others: the module
#: holds `CONTACT_KEYS`, `LINKEDIN_SLUGS` and `EMAILS`, and an exclusion
#: cannot match on a value it is not allowed to hold. These files are
#: still checked for phone numbers, live account figures, client domains
#: and CRM narrative - `tracked_files` does not skip them, so a real
#: PROSPECT reaching either file still fails. Compare `SELF` just above,
#: exempt for the same structural reason: this file has to name what it
#: forbids in order to forbid it.
#:
#: **AND THE WRONG FIX IS ONE SCREEN AWAY.** `FAKE_VANITY` below is an
#: allowlist of INVENTED handles. Putting a real one there would turn the
#: assertion green by retiring the guard for exactly the person it protects.
#: If a real name appears in a file not listed here, REMOVE THE NAME - never
#: widen this tuple to match the file.
TEST_IDENTITY_FILES = (
    "src/testidentity.py",
    "tests/test_the_test_identity_is_never_counted.py",
)


def names_the_test_identity_on_purpose(path):
    """Is this one of the two files the operator allowed it in?"""
    return path in TEST_IDENTITY_FILES


def tracked_files():
    """Every file git actually tracks. Untracked local state is not our problem.

    Walking the filesystem instead would scan `work/`, `out/` and the real
    `config/suppress.local.txt` - all gitignored, all full of real data by
    design - and this guard would fail permanently on an operator's machine
    while proving nothing about what a push would carry.
    """
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0")
            if p and p.endswith(TEXT_SUFFIXES) and p != SELF]


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8", errors="replace") as f:
        return f.read()


def corpus():
    return [(p, read(p)) for p in tracked_files()]


class TestNoRealDataAnywhereInGit(unittest.TestCase):
    """ABSOLUTE rules. Repository-wide, no allowlist, no exempt directory."""

    def test_every_email_address_is_on_a_reserved_domain(self):
        """The strongest rule here, because it needs no list of real names.

        An address on a domain that can resolve is an address somebody could
        actually be mailed at. Whether it belongs to a prospect, a colleague or
        the author does not change that.
        """
        hits = []
        for path, text in corpus():
            if names_the_test_identity_on_purpose(path):
                continue           # see TEST_IDENTITY_FILES
            for domain in sorted(set(EMAIL.findall(text))):
                low = domain.lower()
                if not any(low == s or low.endswith(s) for s in SAFE_SUFFIXES):
                    hits.append(f"{path}: {domain}")
        self.assertEqual(sorted(set(hits)), [],
                         "addresses outside reserved domains:\n" + "\n".join(hits))

    def test_no_real_client_prospect_or_roster_domain(self):
        hits = []
        for path, text in corpus():
            low = text.lower()
            for domain in FORBIDDEN_DOMAINS:
                if domain in low:
                    hits.append(f"{path}: {domain}")
        self.assertEqual(hits, [], "real domains in tracked files:\n" + "\n".join(hits))

    def test_no_real_person_or_client_named(self):
        hits = []
        for path, text in corpus():
            if names_the_test_identity_on_purpose(path):
                continue           # see TEST_IDENTITY_FILES
            low = text.lower()
            for name in FORBIDDEN_NAMES:
                if name in low:
                    hits.append(f"{path}: {name}")
        self.assertEqual(hits, [], "real names in tracked files:\n" + "\n".join(hits))

    def test_no_live_account_figures(self):
        """Counts read from a real provider account are that account's business."""
        hits = []
        for path, text in corpus():
            for figure in FORBIDDEN_FIGURES:
                if figure in text:
                    hits.append(f"{path}: {figure}")
        self.assertEqual(hits, [], "live account figures:\n" + "\n".join(hits))

    def test_no_crm_narrative_about_a_real_account(self):
        blob = "".join(t for _, t in corpus()).lower()
        for phrase in ("sales dashboard", "closed lost", "trial issued",
                       "extension users", "calendly"):
            self.assertNotIn(phrase, blob, phrase)

    def test_no_name_shaped_slug_in_pii_field(self):
        """A name as a slug (ray-kingman) is the same person as Ray Kingman.

        TASK-174 hashed email_hash and name_hash but wrote contact_key in
        plain text, which was a person's name as a slug. Ten real names.
        The guard caught nothing because the slug shape is not in
        FORBIDDEN_NAMES and the field name is not PII-shaped.

        This test catches name-shaped slugs (two hyphenated lowercase words,
        each 2+ chars) in fields that are known to carry person identifiers:
        contact_key, contactkey, person_key, personkey, lead_key, leadkey.

        Excludes tests/ (synthetic fixtures) and focuses on docs/ and scripts/.
        """
        PII_FIELD = re.compile(
            r'["\']?(?:contact_key|contactkey|person_key|personkey|'
            r'lead_key|leadkey)["\']?\s*[:=]\s*["\']?([a-z]{2,}-[a-z]{2,}(?:-[a-z]{2,})*)',
            re.IGNORECASE
        )
        hits = []
        for path, text in corpus():
            if path.startswith("tests/"):
                continue
            for match in PII_FIELD.finditer(text):
                slug = match.group(1)
                if any(x in slug for x in ["test", "demo", "example", "sample",
                                           "mock", "fake", "dummy", "temp", "tmp",
                                           "champ", "buyer", "nobody", "someone"]):
                    continue
                hits.append(f"{path}: {slug}")
        self.assertEqual(hits, [],
                         "name-shaped slug in PII field:\n" + "\n".join(hits))

    def test_no_linkedin_url_with_real_vanity_name(self):
        """A LinkedIn URL with a real person's vanity name is PII.

        linkedin.com/in/ray-kingman identifies a real person as clearly as
        ray.kingman@company.com. The guard already catches the email; this
        catches the profile URL.

        Excludes tests/ (synthetic fixtures) and focuses on docs/, scripts/,
        and src/. Also excludes obvious test/demo/example/probe vanities and
        the project's own synthetic demo senders.
        """
        LINKEDIN = re.compile(r'linkedin\.com/in/([a-zA-Z0-9\-_]+)')
        FAKE_VANITY = {"example", "test", "demo", "probe", "unknown", "sample",
                       "mock", "fake", "dummy", "nobody", "someone", "person",
                       "zzqq9", "x", "b", "p", "s", "o", "c", "m", "bo", "pat",
                       "ann", "wei", "dana", "mara", "tom", "sarah", "petar",
                       "sara", "anna", "mark", "johnsmithacme", "sarahjonesacme",
                       "michaelgreenacme", "john-smith", "ada-lovelace",
                       "grace-hopper", "alan-turing", "dana-reed", "dana-oyelaran",
                       "dana-marsh", "jan-novak", "jan-novak-studio",
                       "ivana-saric", "tomislav-baric", "luka-peric", "rowan-blake",
                       "marin-kovac", "petra-jelic", "damir-vukovic", "mirna-zoric",
                       "luc-marchand", "cuk-simic", "ana-novak", "petarhorvat",
                       "sarasimic", "petar-horvat", "mark-bauer", "acme-champ",
                       "acme-ops", "someone-else", "belmont-champ", "ann-smith",
                       "alice-martin", "bob-chen", "carol-davis", "mina-ruzicic",
                       "mina-ruzicic-b4422438a", "vesna-p", "janedoe", "sarahbw",
                       "jamescascade", "emmanorth", "tompixel", "lisahorizon",
                       "pavanmarisetti", "william-barbat", "tomas-brabec",
                       "marek-havel", "ada-byrne", "ana-x", "dan-x", "person-",
                       "invented-sample", "rga-ws", "some-company",
                       "johnsmith", "sarahjones", "casper", "c1", "a",
                       "example-person", "test-person", "test-profile",
                       "jan", "jan-novak-2", "petra-s", "petar2", "ana",
                       "a-person", "jane", "dalemorgan", "danamarsh",
                       "ansel-a", "bergen-b", "ada", "never-replied",
                       "pablo-estrada", "frank-merrow", "hugo-bramley",
                       "iris-hallow", "liang-wei", "mira-kovacs", "otto-lindqvist",
                       "sanne-de-vries", "lea-perisic", "harriet-vance",
                       "jesse-hollis", "nikola-feric", "unknown-0", "unknown-"}
        hits = []
        for path, text in corpus():
            if names_the_test_identity_on_purpose(path):
                continue           # see TEST_IDENTITY_FILES
            if path.startswith("tests/"):
                continue
            for match in LINKEDIN.finditer(text):
                vanity = match.group(1).lower()
                if vanity in FAKE_VANITY:
                    continue
                if any(x in vanity for x in ["-demo", "-test", "-example", "-acme"]):
                    continue
                hits.append(f"{path}: {vanity}")
        self.assertEqual(sorted(set(hits)), [],
                         "LinkedIn URL with real vanity name:\n" + "\n".join(sorted(set(hits))))


class TestKnownSets(unittest.TestCase):
    """KNOWN-SET rules. A new value is a question for a human, not a failure."""

    def test_every_phone_number_is_a_reserved_fiction(self):
        found = set()
        where = {}
        for path, text in corpus():
            for raw in PHONE.findall(text):
                number = raw.strip()
                found.add(number)
                where.setdefault(number, path)
        unexpected = sorted(found - ALLOWED_PHONES)
        self.assertEqual(
            unexpected, [],
            "phone numbers not in the reserved-fiction set:\n" +
            "\n".join(f"{where[n]}: {n}" for n in unexpected) +
            "\n\nIf this number is synthetic, add it to ALLOWED_PHONES. If it "
            "belongs to a real person, it must not be tracked at all.")


class TestTheSuppressionRosterIsNotInGit(unittest.TestCase):
    """The roster of who is paying us is confidential; the mechanism is not.

    `config/suppress.txt` is the tracked template and carries only reserved
    domains. The real list is `config/suppress.local.txt`, gitignored, merged
    at load time. `tests/test_ingest.py` proves the merge actually happens -
    which is the half that matters, because a template that loads and a roster
    that does not look identical right up until a live customer is sequenced.
    """

    def test_the_tracked_template_holds_only_reserved_domains(self):
        from src import ingest
        entries = ingest.load_suppress(ingest.SUPPRESS)
        self.assertTrue(entries, "the tracked template is empty")
        for entry in entries:
            self.assertTrue(
                any(entry == s or entry.endswith(s) for s in SAFE_SUFFIXES),
                f"{entry} is a real domain in the tracked suppression template")

    def test_the_real_roster_is_not_tracked(self):
        from src import ingest
        rel = os.path.relpath(ingest.SUPPRESS_LOCAL, ROOT).replace(os.sep, "/")
        listed = subprocess.run(["git", "ls-files", "--", rel], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(listed, "",
                         f"{rel} is TRACKED. It holds the live customer roster "
                         f"and must be gitignored.")

    def test_the_real_roster_is_ignored_so_it_cannot_be_added_by_accident(self):
        from src import ingest
        rel = os.path.relpath(ingest.SUPPRESS_LOCAL, ROOT).replace(os.sep, "/")
        ignored = subprocess.run(["git", "check-ignore", rel], cwd=ROOT,
                                 capture_output=True, text=True).returncode
        self.assertEqual(ignored, 0, f"{rel} is not gitignored")


class TestSecretsAreNotTracked(unittest.TestCase):
    def test_no_env_file_is_tracked(self):
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.split()
        bad = [p for p in tracked
               if os.path.basename(p).startswith(".env")
               and not p.endswith(".example")]
        self.assertEqual(bad, [], f"env files tracked: {bad}")

    def test_no_runtime_state_directory_is_tracked(self):
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.split()
        bad = [p for p in tracked
               if p.startswith(("work/", "out/", "logs/", "prototype/work/",
                                "prototype/out/"))]
        self.assertEqual(bad, [], f"runtime state tracked: {bad}")


if __name__ == "__main__":
    unittest.main()
