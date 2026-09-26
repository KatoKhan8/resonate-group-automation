RESONATE OS — OPERATOR CONTEXT RECONCILIATION CHECKLIST
REFERENCE ONLY — NOT A NEW DIRECTIVE
2026-09-26

PURPOSE

This is the actual checklist text you asked me to paste.

Save this document as:

docs/reference/OPERATOR-CONTEXT-CHECKLIST-2026-09-26.md

IMPORTANT:

This is NOT a new governing directive.

This is NOT permission to redesign the architecture.

This is NOT permission to launch anything.

This is NOT permission to stop or interrupt current useful work.

This is a REFERENCE CHECKLIST containing the important architecture decisions,
operator decisions, safety constraints, implementation principles, known defects,
known false alarms, Productive client context, Offer Engine decisions, account-first
principles, copy-engine principles, model/cost principles, and Phase 1 acceptance
criteria established during today's work.

Current machine state wins.

Current origin/master wins over stale statements in this checklist.

The governing vertical-slice directive remains governing.

OPERATING-MODE.md remains governing for current operating mode.

Do not mechanically turn every checklist item into a task.

============================================================
NEW OPERATOR DECISIONS — THESE ARE AUTHORITATIVE
============================================================

Before the 100-item reconciliation checklist, persist and respect these NEW
operator decisions.

DECISION A — capability_by_persona

capability_by_persona becomes a LIST per persona.

The FIRST entry is the PRIMARY angle.

Canonical mapping:

economic_buyer:
  - profitability
  - budgeting
  - billing

champion:
  - resource_planning
  - project_management
  - time_tracking

This is now an explicit operator decision.

Do NOT maintain another persona-to-capability mapping elsewhere.

Change cadence.product_words and EVERY reader of capability_by_persona so they
correctly consume a list, preserving order.

The first capability is the primary angle.

All readers and tests must move together.

Do NOT change the YAML shape without changing the load-bearing readers in the same
task/integration because cadence.py's historical single-key lookup would break.

Tests must prove:

1. list parses correctly
2. primary angle is first
3. all configured capabilities remain available
4. cadence.product_words consumes the list correctly
5. no reader assumes a scalar
6. economic_buyer resolves profitability first, then budgeting, then billing
7. champion resolves resource_planning first, then project_management, then
   time_tracking
8. no duplicate persona mapping exists elsewhere
9. copy path remains functional
10. changing order changes angle priority predictably

DECISION B — ownership boundary

capability_by_persona owns ONLY:

persona → ordered capability-angle preference

It does NOT own:

persona → campaign offer

The new canonical offers: block owns persona-to-offer / campaign-offer semantics.

Do not conflate the two.

DECISION C — Productive Offer A

Offer A is for:

ECONOMIC BUYER

Primary conceptual problem/value territory:

profitability
+
budgeting
+
financial visibility
+
operational visibility

Approved mechanism:

demo / walkthrough with Productive AE

The final canonical structure still needs proper provenance/evidence fields and
must remain pending until explicitly operator-approved.

Do not invent quantified ROI.

Do not invent customer outcomes.

Do not invent guarantees.

DECISION D — Productive Offer B

Offer B is for:

OPERATIONS / CHAMPION

Primary conceptual problem/value territory:

project_management
+
time_tracking
+
resource_planning
+
delivery / operational visibility

Approved mechanism:

trial OR demo / walkthrough

The final canonical structure still needs proper provenance/evidence fields and
must remain pending until explicitly operator-approved.

DECISION E — trial

Add the Productive trial to the canonical offers: block.

Current evidence classification:

VERIFIED

because it is supported by:

public Productive material
+
client brief

The previously observed wording was:

14 day self serve trial

Do not silently promote that to CLIENT_APPROVED merely because it is public.

Record provenance accurately.

Reconfirmation from the client/operator may remain requested.

Do not invent additional trial terms.

DECISION F — demo

Demo / walkthrough is operator-approved.

A demo period of up to one month may be offered if needed.

A booked Productive AE meeting is an approved CTA.

Do not infer:

discount
guarantee
free consulting
free audit
custom implementation
custom deliverable

from demo approval.

DECISION G — profitability

Productive can show project profitability / margin while a project is still
running.

This concept is operator/client approved.

Allowed concept:

see project profitability while the project is still running

Do NOT automatically strengthen it into:

real-time
live to the second
instant

unless stronger wording is separately supported.

DECISION H — evidence / case studies

Public Productive case studies may be named in cold outreach with figures that are
actually published on those pages, subject to stored-page evidence and traceability.

Do NOT license a figure merely because it appears in an operator summary.

page_text must support the actual claim.

TASK-365 is intended to store case-study page evidence and trace claims.

A summary figure absent from the stored source page is:

NOT LICENSED

and must be reported, not invented.

DECISION I — current six records

The six historical offer records are now understood primarily as:

CAPABILITY
+
VALUE PROPOSITION
+
MESSAGING ANGLE

They are NOT, by themselves, genuine prospect-facing campaign offers.

Do not approve them merely to unblock generation.

The smallest intended correction is:

capabilities:
  existing six capability/value records

offers:
  actual campaign-level Offer A/B

Campaign strategy should consume the real Offer A/B layer.

DECISION J — TASK-321

TASK-321 was found in REWORK while dispatcher scans TODO.

It has been moved back to TODO with rework context preserved and dispatched.

Do not create a duplicate TASK-321.

Verify current machine state.

============================================================
100-PART RECONCILIATION CHECKLIST
============================================================

1. CURRENT MACHINE TRUTH

Always begin from current:

origin/master
git status
task registry
governing docs

Do not assume conversation text is newer than machine state.

2. PRODUCTION FREEZE

No new prospect-facing launch without explicit operator APPROVED.

3. NO NEW CAMPAIGN ACTIVATION

Do not activate campaigns for testing.

4. NO NEW LEAD ENROLMENT

Do not enrol/attach new leads or cohorts without authorization.

5. NO PROSPECT-FACING SENDS

Dry runs/previews are allowed; provider-changing sends are not.

6. EXISTING ACTIVE CAMPAIGNS

Do not pause or modify existing active campaigns merely because development is
ongoing.

7. CAMPAIGN 493

Historical latest verified state had campaign 493 as the only campaign sending.

Verify current provider/runtime state before making any current claim.

8. IMMEDIATE OBJECTIVE

Finish one production-realistic vertical slice rather than expanding architecture.

9. TARGET CHAIN

Second Brain
→ Offer Engine
→ Campaign Strategy
→ Account Research
→ Buying Committee
→ Five Skills
→ Email
→ LinkedIn
→ QA
→ Approval
→ Safety
→ Provider-ready payload

must work as one system.

10. WIRED MEANS CONSUMED

A component is not wired merely because its file/function exists.

Its output must reach a real consumer and real production entrypoint.

11. UPSTREAM CHANGE TEST

Changing valid upstream information should be capable of changing appropriate
downstream context/output.

12. CONSUMER-BEFORE-PRODUCER

Before adding a producer ask:

who consumes this output?

13. NO ZERO-CONSUMER FEATURES

A component whose output reaches nobody in the production chain is not Phase 1
complete.

14. ACCOUNT-FIRST RESEARCH

Research primarily at company/account level.

15. REUSE COMPANY RESEARCH

Do not repeat full company research for every decision maker.

16. LIGHTWEIGHT PERSON RELEVANCE

Person-level enrichment should add role/person relevance to shared account research.

17. BUYING COMMITTEE

Treat a company as an account with approximately 2–3 relevant contacts where
appropriate.

18. DO NOT FORCE THREE CONTACTS

Use only genuinely relevant contacts.

19. EXISTING ACCOUNT MODEL

Reuse current account.py/accountpolicy.py/accountstate.py architecture where still
canonical.

20. DO NOT REBUILD ACCOUNT MODEL

No parallel account orchestration store.

21. ACCOUNT RELATIONSHIPS

Preserve relationships among account, contacts, roles, campaign, offers, research,
channel state, replies, referrals, suppression and outcomes.

22. REFERRAL EFFECT

Referral from contact A to contact B should be able to affect account/contact
priority and unnecessary follow-up behavior.

23. ONE CONTACT NOT INTERESTED

Does not automatically equal company-wide DNC.

24. COMPANY-WIDE REMOVAL

Explicit company-wide removal should suppress appropriately at account level.

25. FUTURE ORCHESTRATION

Data model should support future next-best-action account motion without building
the full autonomous engine now.

26. PRODUCTIVE ICP

Services-oriented businesses that track time.

27. TIME TRACKING MUST-HAVE

Time tracking is a structural ICP condition.

28. PRODUCTIVE PRIMARY VERTICALS

Marketing agencies and software agencies are primary targets.

29. PRODUCTIVE SIZE

Primary threshold: 20+ employees.

30. PRODUCTIVE GEOGRAPHIES

UK, Western Europe, Australia and USA are primary geographies.

31. ECONOMIC BUYER PERSONAS

CEO, Founder, Owner, COO, CFO.

32. CHAMPION PERSONAS

Operations Manager, Project Manager, Finance Manager.

33. OPERATIONS DIRECTOR

May belong to both economic-buyer and champion contexts depending on account,
seniority and strategy.

34. capability_by_persona SHAPE

It is now an ordered LIST per persona.

35. ECONOMIC BUYER CAPABILITY ORDER

profitability
→ budgeting
→ billing

36. CHAMPION CAPABILITY ORDER

resource_planning
→ project_management
→ time_tracking

37. PRIMARY ANGLE

First list entry is primary.

38. NO SECOND CAPABILITY MAPPING

Do not create another mapping elsewhere.

39. CAPABILITY MAPPING OWNERSHIP

capability_by_persona controls angle ordering only.

40. OFFER OWNERSHIP

offers: controls actual campaign offer semantics/persona-to-offer relationship.

41. CAPABILITY ≠ OFFER

A Productive capability is not automatically a campaign offer.

42. SIX HISTORICAL RECORDS

Treat them as capability/value proposition/messaging-angle records unless current
master has already migrated them.

43. OFFER A

Economic buyer:

profitability
+
budgeting
+
financial/operational visibility
+
demo with Productive AE.

44. OFFER B

Operations/champion:

project management
+
time tracking
+
resource planning
+
trial or demo.

45. TWO PRIMARY OFFERS

Campaign architecture should support two genuinely distinct primary approved
offers.

46. OFFER DIFFERENTIATION

Do not make Offer A and Offer B the same argument with different nouns.

47. BUDGETING VS PROFITABILITY

Budgeting and profitability are distinct capabilities.

48. BUDGETING

Conceptually: budget/quoted amount vs consumption/burn.

49. PROFITABILITY

Conceptually: revenue/cost/project margin.

50. ACTIVE-PROJECT PROFITABILITY

Productive can show profitability while a project is still running.

51. STRONGER TIMING WORDS

Do not use real-time/live-to-the-second unless independently supported.

52. DEMO APPROVED

Demo/walkthrough is approved.

53. PRODUCTIVE AE CTA

Booked AE meeting is an approved CTA.

54. ONE-MONTH DEMO

Operator has approved offering a demo period of up to one month if needed.

55. TRIAL

Canonical Offer B may include Productive trial based on VERIFIED public + brief
evidence.

56. TRIAL PROVENANCE

Do not mislabel public/brief verification as canonical-config approval.

57. NO INVENTED COMMERCIAL TERMS

No invented discounts, guarantees, pricing, POCs, consulting or deliverables.

58. CLIENT-APPROVED MESSAGING TERRITORY

Productive may be positioned as an end-to-end platform for services businesses.

59. TOOL CONSOLIDATION

Replacing multiple disconnected tools is approved messaging territory.

60. SILOED DATA

Delivery/resourcing/finance silos are approved messaging territory.

61. OPERATIONAL VISIBILITY

Approved messaging territory.

62. PROFITABILITY VISIBILITY

Approved messaging territory.

63. TIME TRACKING FOUNDATION

Time tracking may be positioned as a foundation for utilization, profitability and
forecasting where supported by client material.

64. INTEGRATIONS

Accounting/HR/related integrations may be discussed only within verified Productive
capability/material.

65. VALUE FOR MONEY

Broad positioning may be supported; quantified savings require evidence.

66. KNOWLEDGE STATUS

Preserve:

VERIFIED
CLIENT_APPROVED
INFERRED
UNKNOWN

67. INFERRED IS NOT FACT

May guide strategy, may not silently license factual copy.

68. UNKNOWN IS NOT SAFE

Unknown must not become zero/clean/false/safe.

69. SECOND BRAIN

Build on canonical client config/current Second Brain; do not create a parallel
knowledge store.

70. SECOND BRAIN CONTENT

Should support client, market, competitor, customer, offer, messaging and learning
knowledge as appropriate.

71. PROVENANCE

Material knowledge should retain source/date/status where possible.

72. KNOWLEDGE GAPS

Questions should be BLOCKING / IMPORTANT / OPTIONAL rather than one giant generic
questionnaire.

73. PRODUCTIVE RESOLVED QUESTIONS

Do not re-ask demo permission, active-project profitability, budgeting primary
persona or basic Productive persona definitions unless contradictory evidence
appears.

74. CASE-STUDY CLAIMS

Only stored evidence actually supporting the claim may license prospect-facing
figures.

75. TASK-365

Store case-study pages and trace every allowed claim to source evidence.

76. FIVE PHASE-1 SKILLS

Account research
signal verification/relevance
campaign strategy
cold email writing
LinkedIn writing.

77. SKILLS MUST BE RUNTIME-WIRED

Docs-only skills do not count.

78. EMAIL ROLE

Structured commercial/value argument.

79. LINKEDIN ROLE

Lighter, contextual, relationship/account-oriented communication.

80. CHANNEL COMPLEMENTARITY

LinkedIn should complement Email rather than paraphrase it.

81. PRESERVE RICH LINKEDIN TREE

Do not simplify existing LinkedIn cadence/tree without evidence/review.

82. HISTORICAL LINKEDIN CADENCE

Historically canonical Productive LinkedIn cadence was five steps at
1/3/6/10/15.

Verify current canonical source.

83. HISTORICAL EMAIL THREADING

Historically verified:

A-new
A-reply
B-new
B-reply
C-new

days:

1/4/8/12/21.

Do not reopen as a defect without current evidence.

84. CANONICAL SEQUENCE REPRESENTATION

Use one canonical structured sequence representation if current architecture still
requires it.

85. PROJECTIONS DO NOT OWN BUSINESS LOGIC

Preview, HTML, XLSX and provider serialization should project/consume canonical
state rather than reimplement cadence/strategy.

86. APPROVAL IDENTITY

Operator approval must bind to the exact materially provider-ready artifact.

87. RERENDER INVALIDATES APPROVAL

Material artifact change after approval must require new approval identity/hash.

88. SUPPRESSION ON RESUME

Current suppression state must be re-evaluated when resuming.

89. CROSS-CHANNEL STOP

Code-level linkage is not the same as provider-runtime proof.

90. PROVIDER TRUTH

Unreadable provider state remains UNKNOWN.

91. PROVIDER PAGINATION

Provider reads must be complete; no silent partial estate.

92. ACCOUNT IDENTITY

Wrong-company/domain/person/research joins must fail closed.

93. GROUNDING

Claim support must be semantic/evidentiary, not token coincidence.

94. UNRENDERED VARIABLES

No unresolved template variables may reach provider-ready messages.

95. SIGNATURES

Required sender signature must be available before production send.

96. SEMANTIC REPETITION

Five emails and LinkedIn touches must add distinct value, not repeat one argument
with different wording.

97. COST REUSE

Generate expensive intelligence once at the highest reusable level:

client
campaign/persona
account
contact delta
message.

98. SPEND CEILING

A ceiling must refuse expensive work before the call, not merely observe/report it.

99. TEST FALSIFIABILITY

For safety/integration tests ask:

HOW COULD THIS TEST PASS WHILE PRODUCTION IS STILL BROKEN?

Use negative controls/mutation-style proof where valuable.

100. FINAL PHASE-1 PRINCIPLE

STOP EXPANDING THE ARCHITECTURE.

Finish the first production-realistic vertical slice:

CANONICAL CLIENT KNOWLEDGE
→ APPROVED CAMPAIGN OFFER
→ VERIFIED ACCOUNT RESEARCH
→ BUYING COMMITTEE
→ ROLE RELEVANCE
→ EMAIL + LINKEDIN
→ QA
→ CANONICAL SEQUENCE REPRESENTATION
→ EXACT APPROVAL
→ CURRENT SAFETY STATE
→ PROVIDER-READY PAYLOAD

working as ONE VERIFIED SYSTEM.

============================================================
GLM RECONCILIATION TASK
============================================================

Now that the actual checklist text is present:

1. Save it exactly as REFERENCE ONLY under:

docs/reference/OPERATOR-CONTEXT-CHECKLIST-2026-09-26.md

Do NOT label it governing.

Do NOT replace the vertical-slice directive.

Do NOT replace OPERATING-MODE.md.

2. Dispatch GLM READ-ONLY to compare all 100 items plus the NEW OPERATOR DECISIONS
above against:

current origin/master
docs/OPERATING-MODE.md
docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md
docs/OFFER-REVIEW-2026-09-26.md
task registry
current canonical Productive config
current Offer Engine
current campaign strategy
current cadence readers
current safety/provider gates

3. GLM must return ONLY:

A. CONFIRMED GAPS

For each:

CHECKLIST ITEM
CURRENT MASTER EVIDENCE
FILE:LINE
WHY IT IS A REAL GAP
EXISTING TASK IF ANY
PROPOSED TASK ONLY IF NONE EXISTS
P0/P1/P2

B. STALE OR SUPERSEDED ITEMS

For each:

CHECKLIST ITEM
WHY STALE
CURRENT SOURCE OF TRUTH

C. OPERATOR DECISIONS NOT YET PERSISTED CANONICALLY

For each:

DECISION
WHERE IT SHOULD LIVE
CURRENT STATE
SMALLEST PERSISTENCE CHANGE

D. COVERED COUNT

Example:

COVERED: 87 / 100

Do NOT list all covered items.

4. Evidence discipline:

No file:line + no reproducible static evidence
→ not a CONFIRMED GAP.

Put uncertain items outside the confirmed-gap list.

5. GLM must NOT:

implement
merge
modify production
approve offers
change provider state
create duplicate architecture
create duplicate tasks
change canonical config itself

It reviews only.

6. Claude then triages GLM output.

For each confirmed gap:

if task already exists:
update/use existing task.

if no task exists and gap is real:
create the smallest task.

Do not create one task per checklist item.

Group only where the same underlying defect and same implementation surface justify
grouping.

7. Continue current critical path while GLM performs reconciliation.

Do NOT block:

TASK-321
TASK-365
current Offer A/B work
Five Skills integration
SequencePlan/current canonical sequence work

unless a proven dependency requires it.

============================================================
IMPLEMENT THE NEW capability_by_persona DECISION
============================================================

Separately from the GLM read-only reconciliation, the operator has now made the
capability_by_persona decision.

This IS implementation-authorizing input.

Create/reuse ONE task for the atomic change:

productive.yaml capability_by_persona:

economic_buyer:
  - profitability
  - budgeting
  - billing

champion:
  - resource_planning
  - project_management
  - time_tracking

AND:

change cadence.product_words

AND:

change EVERY reader

AND:

tests

AND:

no second mapping.

Do not split the YAML shape change from reader migration.

The task is complete only when the entire production copy path understands the
ordered list.

Search every reader before implementation.

Acceptance must include a regression test proving the first entry is primary and
later entries remain usable.

============================================================
IMPLEMENT THE CANONICAL OFFER A/B DATA LAYER
============================================================

Do not approve anything yet.

Implement/reuse the smallest canonical data structure required so the existing six
capability records are not pretending to be campaign offers.

Preferred conceptual structure:

capabilities:
  <existing six capability/value records>

offers:
  <Offer A>
  <Offer B>

Offer A:

persona:
  economic_buyer

capabilities:
  profitability
  budgeting

supporting territory:
  financial visibility
  operational visibility

mechanism:
  demo / walkthrough with Productive AE

CTA:
  booked Productive AE meeting / approved demo motion

Offer B:

persona:
  champion / operations

capabilities:
  project_management
  time_tracking
  resource_planning

supporting territory:
  delivery visibility
  operational control

mechanism:
  trial OR demo / walkthrough

Trial provenance:
  VERIFIED
  public + client brief

Do NOT mark Offer A/B approved.

Keep:

approval_status: pending

until explicit operator approval.

Campaign strategy should eventually reference actual Offer A/B identifiers through
its existing primary_offer / secondary_offer semantics rather than treating an
individual capability as the campaign offer.

============================================================
DO NOT LOSE CURRENT SAFETY STATE
============================================================

Preserve:

all six historical records pending until migrated/reclassified appropriately

no prospect-facing send

no activation

no resume

no enrolment

no attachment

no provider-changing test

campaign 493 untouched unless separately authorized

production freeze fully in force.

============================================================
FINAL RETURN
============================================================

Do not return another architecture essay.

Return:

CHECKLIST
SAVED / NOT SAVED
PATH
COMMIT / SHA

GLM RECONCILIATION
DISPATCHED / BLOCKED
WHY

capability_by_persona MIGRATION
TASK
STATUS
READERS FOUND
TEST ACCEPTANCE

OFFER A/B DATA LAYER
CURRENT STATUS
FILES
APPROVAL STATUS

TASK-321
CURRENT STATUS

TASK-365
CURRENT STATUS

CRITICAL PATH
CURRENT NEXT STEP

PRODUCTION
UNCHANGED / EXPLAIN ANY CHANGE

Continue the work.
Do not wait for another operator response unless a genuine operator-only decision
remains.
