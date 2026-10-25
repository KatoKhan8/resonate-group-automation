# Fresh material read: operator decision

This packet requests one new read phase. It does not authorize execution or sending. All earlier read6/read11/diagnostic3 and 24 October refresh/followup phases remain closed.

Prepared entry: `isolated_read.PROPOSED.py:capture_phase`, SHA256 `9a1326f5eebcbd2c166e30251eb99ee783ecc6db3c793ae94e0460886edbb889`. Code, test and dependency hashes are in `isolated-read-review.json`.

Scope: workspace10, campaign540, the existing four retained firms excluding Savage, with exact existing provider IDs resolved from the pinned private cohort inputs. No new cohort or client configuration changes. Fixed base: `https://send.resonategroup.co/api`; GET only.

| Route | Maximum attempts |
|---|---:|
| `/users`, before and after | 2 |
| `/leads/{existing pinned ID}` | 4 |
| `/campaigns/540` | 1 |
| `/campaigns/540/leads`, pages1-8 | 8 |
| `/campaigns/v1.1/540/sequence-steps` | 1 |
| `/campaigns/540/sender-emails`, pages1-8 | 8 |
| `/custom-variables`, pages1-8 | 8 |
| Total ceiling | 32 |

Unused page slots are skipped only after validated complete pagination. No other campaign, template, reply or event traversal. Limits:600seconds total,1MiB per response,8MiB aggregate; each collection also has8pages/102rows/1MiB aggregate/60seconds. No retries, redirects or proxies. Stop on auth/quota/error, uncertainty, identity/schema drift, incomplete pages or any limit. Claims remain sticky; no automatic new phase.

Approval must include local preparation of exact private cohort/root/credential/authority hashes and a new once-only directory. Only existing BISON_KEY/BISON_BASE from the explicitly bound existing config/.env are used, inside the isolated child after its durable claim. No key output/export, auth or billing changes. Original responses and receipts remain bounded private local artifacts; user and Slack output contains counts/status only. No production work/ or provider-module reads/writes are required. Directory privacy is the operator's responsibility; no ACL changes are implied.

This read may establish current material, workspace, sequence identity, membership and inventory observations. It does not renew approval or prove sender health, suppression/touch/collision coverage or external namespace nonuse. Missing title and unsupported metadata remain blocking; fixtures never fill missing facts. Source/gate integration and launch/send retain separate exact decisions. Status remains NO-GO.
