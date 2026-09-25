# HeyReach support request — StopLeadInCampaign 404s on a present lead

Draft for the operator to send from their own account. Ten lines, no client
names, no prospect data. The lead in question is the operator's own profile in
our own test campaign, so nothing here is a client's.

---

Subject: StopLeadInCampaign returns 404 for a lead GetLeadsFromCampaign reports as present

1. `POST https://api.heyreach.io/api/public/campaign/StopLeadInCampaign` returns 404 for a lead your own read endpoints report as present and running in that campaign.
2. Request body we send: `{"campaignId": 620829, "leadMemberId": "<LinkedIn member URN, the ACoAA… value>", "leadUrl": "https://www.linkedin.com/in/<vanity>"}`
3. Response: `404 {"errorMessage": "The lead is not present in the campaign you are trying to modify"}`
4. We also tried `leadMemberId` as your numeric lead id (`314376993`, from GetLeadsFromCampaign) — identical 404.
5. `GET /campaign/GetLeadsFromCampaign?campaignId=620829` returns exactly 1 row: `id 314376993`, `leadCampaignStatus "InSequence"`, `leadMessageStatus "MessageSent"`.
6. `GET /campaign/GetCampaignsForLead` for the same profile URL returns campaign `620829` with `leadStatus "InSequence"`.
7. Campaign 620829 is `IN_PROGRESS`, one seat, one lead; reads taken seconds either side of each write, so this is not a timing race.
8. **Question 1: what exact body shape does StopLeadInCampaign expect — which identifier belongs in `leadMemberId`, and is `leadUrl` required alongside it?**
9. **Question 2: why does it 404 on a lead your own endpoints report as present, and is there a lead state or campaign scope in which it is rejected?**
10. Context: we use this to stop one person's progression after they reply on another channel, so it is an opt-out path and we cannot ship the integration until it is confirmed working.

---

## Notes for us, not for the message

**Everything above is measured, 2026-09-25 between 10:51Z and 10:56Z.** Three
writes, two identifier shapes, identical response. The lead read `InSequence`
before and after every attempt, so nothing was stopped and no state needs
settling.

**The fail-closed readback is why this is a support question and not an
incident.** `stop_lead_in_campaign` reads back per lead and raises when the
provider still reports the lead in a running status, so this system has never
reported a stop that did not happen. `providerwrites.perform` recorded the
attempt in the action ledger as `heyreach.stop_lead / unverified /
by operator-authorized`.

**What it blocks:** the email → LinkedIn direction of the cross-channel stop.
A prospect who replies by email cannot be stopped on LinkedIn. The operator's
containment is to enrol LinkedIn-only cohorts — contacts in no email campaign
— so nobody is enrolled who could need a stop on a channel we cannot stop.

**Do not send** the campaign's name, the client's name, or any prospect
identifier. The ids above are ours and the profile is the operator's own.
