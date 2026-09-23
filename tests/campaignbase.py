"""Shared setup for the campaign, Slack, reply and orchestration tests.

Every test here runs against a temporary queue and a temporary campaign file,
with the network tripwire from ProviderTest still armed. Nothing reaches a
provider, a workspace or the developer's own queue.
"""
import os
import shutil
import tempfile

from src import approve, campaigns, cadence, clients, orchestrator, store
from tests.base import ProviderTest

CLIENT = "demo"

# Two companies, so a pause on one can be shown not to touch the other.
COMPANIES = (
    ("acme", "Acme Services", "acme.test"),
    ("borealis", "Borealis Consulting", "borealis.test"),
)


def contact(key, name, email, linkedin=None, persona="champion", angle="ops",
            sendable=True, title="Operations Manager"):
    """A contact whose verification block is built from real evidence.

    It used to hand-write `state: "verified"` over an empty evidence list.
    That worked only because `is_sendable` trusted the stored state, and it
    modelled something that cannot exist: an address no provider has ever been
    asked about, marked as cleared. Now that sendability is recomputed from
    the evidence every time, the fixture has to carry the evidence a real
    verified contact carries - two independent confirmations, because that is
    what the default policy requires.
    """
    from src import verification

    person = {
        "key": key, "name": name, "email": email, "title": title,
        "linkedin": linkedin or f"https://www.linkedin.com/in/{key}",
        "persona": persona, "angle": angle,
    }
    if sendable:
        evidence = [verification.result("contactout", verification.S_VALID, email),
                    verification.result("deliverable", verification.S_VALID, email)]
    else:
        evidence = [verification.result("contactout", verification.S_ACCEPT_ALL,
                                        email, catch_all=True)]
    verification.apply(person, verification.decide(evidence), evidence)
    return person


# One body per generated step. They have to differ: two identical emails in
# one sequence is a defect the product now refuses to approve, and a fixture
# that could not pass its own product's QA is not modelling a campaign.
SUBJECTS = {
    "day1": "quick question about {company}",
    "day15": "one thing that might be worth {company} knowing",
}

BODIES = {
    "day1": (
        "Hi {first},\n\n"
        "Noticed {company} runs delivery across a few teams at once. The "
        "pattern we see in teams that size is that utilisation and margin are "
        "only known at the end of the month, which is after the month when "
        "anything could have been done about them.\n\n"
        "Most operations leads we speak to lose the best part of a day every "
        "month reconciling time before they can answer a question anyone "
        "actually asked.\n\n"
        "Is that roughly how it works with you today, or have you already put "
        "something in place for it?\n"),
    "day15": (
        "Hi {first},\n\n"
        "One more thought and then I will stop. The teams closest to "
        "{company} in size tend to arrive at the same place: they stop "
        "reconciling hours after the fact, and start seeing project margin "
        "while the project is still running.\n\n"
        "What makes the difference is rarely a new process for the delivery "
        "team. It is that the finance view and the delivery view stop being "
        "two spreadsheets maintained by two different people.\n\n"
        "Would it be useful to see what that looked like for a team your "
        "size?\n"),
}


class CampaignTest(ProviderTest):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-campaign-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.campaign_file = os.path.join(self.tmp, "work", "campaigns.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)

        # `addCleanup` where the state is captured, NOT `tearDown` - the same
        # reason `ProviderTest` gives one class up, and this class is the
        # instance it was warning about. `unittest` does not call `tearDown`
        # when a `setUp` raises, and `clients.load(CLIENT)` below can raise:
        # the three variables were then left pointing at a temp directory that
        # the cleanup went on to delete. Measured 2026-09-23 as
        # `test_replywatch` leaving OUT at `rga-campaign-<tmp>\out`, inherited
        # by every module after it.
        self._env = {k: os.environ.get(k) for k in ("QUEUE", "CAMPAIGNS", "OUT")}
        self.addCleanup(self._restore_env, self._env)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        os.environ["QUEUE"] = self.queue
        os.environ["CAMPAIGNS"] = self.campaign_file
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        self.config = clients.load(CLIENT)

    # ------------------------------------------------------------ fixtures

    def reset_estate(self):
        """Empty the queue before writing a fixture over it.

        `store.save` refuses a write that drops paid verification evidence, and
        a fixture builder replacing an estate looks exactly like that loss -
        because it is one. Saying so explicitly is the difference between
        "this is a fresh estate" and "we quietly lost four verifier credits",
        which is the distinction the guard exists to force.
        """
        store.save([])

    def seed_records(self, companies=COMPANIES):
        recs = []
        for rid, company, domain in companies:
            rec = store.new_record(rid, "cold", CLIENT, company, domain)
            rec["state"] = "drafted"
            # The cold lane refuses to ship without one, and rightly so.
            rec["hook"] = f"{company} runs delivery across several teams"
            rec["company_facts"] = {"industry": "Professional services",
                                    "employees": 40}
            rec["contacts"] = [
                contact(f"{rid}-champ", f"Champ {company}", f"champ@{domain}"),
            ]
            recs.append(rec)
        # A reset, not an update. `store.save` refuses a write that drops paid
        # verification evidence, and re-seeding over an estate a previous pass
        # has already verified looks exactly like that loss - because it is
        # one. Clearing first says what this means: a fresh estate, with no
        # before to lose.
        self.reset_estate()
        store.save(recs)
        return recs

    def draft_everything(self, recs, config=None):
        """Write the generated steps, as phase 5 would.

        Only day1 and day15 are generated; the rest are templates the cadence
        expands fresh on every read, so writing a body for those would be
        fiction that the engine ignores.
        """
        config = config or self.config
        for rec in recs:
            for contact in rec.get("contacts") or []:
                first = (contact.get("name") or "there").split()[0]
                stored = rec.setdefault("cadence", {}).setdefault(contact["key"], {})
                for step_key in cadence.GENERATED_KEYS:
                    stored.setdefault(step_key, {})
                    stored[step_key].update({
                        "channel": "email",
                        "generated": True,
                        "subject": SUBJECTS.get(step_key,
                                                SUBJECTS["day1"]).format(
                            company=rec["company"]),
                        "body": BODIES.get(step_key, BODIES["day1"]).format(
                            first=first, company=rec["company"]),
                    })
        return recs

    def approve_drafts(self, recs, by="U0DEMOADMIN1", config=None,
                       campaign=None):
        config = config or self.config
        approved = 0
        for rec in recs:
            timeline = cadence.build(rec, config, recs=recs, campaign=campaign)
            for contact_key, steps in timeline["contacts"].items():
                for step_key, step in steps.items():
                    if step.get("channel") != "email":
                        continue
                    try:
                        approve.approve_step(rec, contact_key, step_key, by=by,
                                             config=config, step=step)
                        approved += 1
                    except approve.NotApprovable:
                        pass
        return approved

    def make_campaign(self, recs=None, campaign_id="camp-1", senders_=True,
                      external=True, volume=True):
        recs = recs if recs is not None else store.load()
        campaign = orchestrator.create(campaign_id, CLIENT, "Demo campaign",
                                       record_ids=[r["id"] for r in recs],
                                       created_by="U0DEMOADMIN1")
        if senders_:
            campaign["senders"] = {
                "email": [{"id": "bison-1", "daily_limit": 40},
                          {"id": "bison-2", "daily_limit": 40}],
                "linkedin": [{"id": "hr-1", "daily_limit": 20}],
            }
        if external:
            campaign["bison_campaign_id"] = "9001"
            campaign["heyreach_campaign_id"] = "7001"
        if volume:
            campaign["daily_volume"] = {"email": 20, "linkedin": 10}
        campaigns.save([campaign])
        return campaign

    def ready_campaign(self, campaign_id="camp-1"):
        """A campaign with drafted, approved records and everything mapped."""
        recs = self.seed_records()
        self.draft_everything(recs)
        self.approve_drafts(recs)
        store.save(recs)
        recs = store.load()
        campaign = self.make_campaign(recs, campaign_id=campaign_id)
        return campaign, recs

    def approved_campaign(self, campaign_id="camp-1", by="U0DEMOADMIN1"):
        campaign, recs = self.ready_campaign(campaign_id)
        orchestrator.prepare(campaign, recs, self.config)
        orchestrator.request_approval(campaign, recs, self.config)
        result = orchestrator.decide(campaign, by, "approve",
                                     fingerprint=campaigns.fingerprint(
                                         campaign, recs, self.config),
                                     interaction_id="i-1", config=self.config,
                                     recs=recs)
        campaigns.save([campaign])
        return campaign, recs, result

    def save_campaign(self, campaign):
        rows = [c for c in campaigns.load()
                if c["campaign_id"] != campaign["campaign_id"]]
        rows.append(campaign)
        campaigns.save(rows)
