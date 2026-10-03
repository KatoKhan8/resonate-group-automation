# Phase 2 - the final table

> ovo kaže što sustav radi 120 dana, ne što bi zaradio; svaki odgovor je iz stope, ne iz tržišta

One row per scenario. 30 scenarios x 3 firings = 90, each on a DIFFERENT account and a DIFFERENT simulated day, every verdict set in advance from the scenario's own `expected` block before the run began.

`latency` is from injecting the event to holding the verdict. The operator's threshold is 15 minutes (900s).

| scenario | firings | matched | unmatched | max latency (s) | late | unverifiable keys |
|---|---|---|---|---|---|---|
| S01 | 3 | 3 | 0 | 0.0155 | no | `rule2_step` |
| S02 | 3 | 3 | 0 | 0.0154 | no | `rule2_step` |
| S03 | 3 | 3 | 0 | 0.0007 | no | `hygiene_verdict`, `rule2_step` |
| S04 | 3 | 3 | 0 | 0.0000 | no | `collision_decision`, `rule2_step`, `rule2_step_unimplemented` |
| S05 | 3 | 3 | 0 | 0.0000 | no | `collision_decision`, `only_the_operator_may_close`, `rule2_step`, `rule2_step_unimplemented` |
| S06 | 3 | 3 | 0 | 0.0000 | no | `classification_only_no_send`, `collision_decision`, `revival_cooling_days_in_claude_md`, `revival_cooling_days_in_code`, `rule2_step`, `rule2_step_unimplemented` |
| S07 | 3 | 3 | 0 | 0.0010 | no | `collision_decision`, `gap_rule_does_not_exist`, `rule2_step`, `rule2_step_unimplemented` |
| S08 | 3 | 3 | 0 | 0.0000 | no | `collision_decision`, `rule2_step`, `rule2_step_unimplemented`, `treated_as_blocked` |
| S09 | 3 | 0 | 3 | 0.0127 | no | `classifier_unaudited` |
| S10 | 3 | 3 | 0 | 0.0135 | no | `hygiene_verdict`, `rule2_step` |
| S11 | 3 | 3 | 0 | 0.0128 | no | - |
| S12 | 3 | 3 | 0 | 0.0149 | no | - |
| S13 | 3 | 0 | 3 | 0.0143 | no | `hygiene_action`, `hygiene_verdict` |
| S14 | 3 | 3 | 0 | 0.0157 | no | `rule2_step` |
| S15 | 3 | 0 | 3 | 0.0136 | no | `classifier_unaudited` |
| S16 | 3 | 0 | 3 | 0.0144 | no | - |
| S17 | 3 | 0 | 3 | 0.0003 | no | - |
| S18 | 3 | 3 | 0 | 0.0151 | no | `rule2_step` |
| S19 | 3 | 3 | 0 | 0.0020 | no | `hygiene_action`, `hygiene_verdict`, `rule2_step` |
| S20 | 3 | 3 | 0 | 0.0033 | no | `still_blocked_on_day_120` |
| S21 | 3 | 3 | 0 | 0.0007 | no | `hygiene_verdict`, `rule2_step` |
| S22 | 3 | 3 | 0 | 0.0000 | no | `held_on_day_0`, `held_on_day_44`, `hold_appears_in_weekly_report`, `hold_duration_days_on_day_44`, `rule2_step`, `rule2_step_unimplemented` |
| S23 | 3 | 3 | 0 | 0.0000 | no | `rule2_step_unimplemented`, `send_performed`, `verdict`, `window_applied_must_be_named` |
| S24 | 3 | 0 | 3 | 0.0157 | no | - |
| S25 | 3 | 3 | 0 | 0.0000 | no | `deciding_code_must_be_named`, `gap_config_key_exists`, `rule2_step`, `rule2_step_unimplemented` |
| S26 | 3 | 3 | 0 | 0.0003 | no | `still_refused_on_day_120` |
| S27 | 3 | 3 | 0 | 0.0000 | no | `appears_in_weekly_send_plan`, `estate_bounce_rate_source`, `mailbox_selected`, `send_plan_shrinks_against_forward_book` |
| S28 | 3 | 3 | 0 | 0.0178 | no | - |
| S29 | 3 | 0 | 3 | 0.0203 | no | - |
| S30 | 3 | 3 | 0 | 0.0175 | no | `day_14_step_pushed`, `day_21_step_offered`, `step_shown_withdrawn_in_send_plan` |
| **total** | 90 | 69 | 21 | 0.0203 | 0 late | |

## Latency

| statistic | seconds |
|---|---|
| min | 0.000004 |
| median | 0.003203 |
| p90 | 0.015410 |
| max | 0.020261 |
| threshold | 900 |
| over threshold | 0 of 90 |

Every verdict is reached in-process, so the measured latency is milliseconds and **nothing is late**. That is a statement about this harness, not about production: a live system reaches these verdicts through a provider poll, and this run does not measure that.

## Every unmatched field

| scenario | field | expected | actual | firings |
|---|---|---|---|---|
| S09 | `accountpolicy_outcome` | `positive` | `unknown` | 3 |
| S09 | `notification_fired` | `True` | `False` | 3 |
| S09 | `replies_classify` | `positive` | `interested` | 3 |
| S09 | `replies_confidence_at_least` | `75` | `60` | 3 |
| S13 | `accountpolicy_outcome` | `referral` | `not_icp` | 3 |
| S13 | `replies_classify` | `referral` | `not_relevant` | 3 |
| S15 | `counts_as_positive` | `True` | `False` | 3 |
| S15 | `notification_fired` | `True` | `False` | 3 |
| S15 | `replies_classify` | `question` | `unknown` | 3 |
| S16 | `replies_classify` | `objection` | `unknown` | 3 |
| S17 | `accountpolicy_outcome` | `not_now` | `unknown` | 3 |
| S17 | `cadence_stopped` | `True` | `False` | 3 |
| S24 | `channels_email_allowed` | `False` | `True` | 3 |
| S29 | `channels_email_allowed` | `False` | `True` | 3 |
| S29 | `channels_linkedin_allowed` | `False` | `True` | 3 |
| S29 | `cross_channel_stop` | `True` | `False` | 3 |

## Every key no authority could answer

These are not passes. A scenario asserting a key that no module computes is reported here and becomes a TASK.

| scenario | key | why |
|---|---|---|
| S01 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S02 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S03 | `hygiene_verdict` | hygiene.check raised TypeError in the sandbox |
| S03 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S04 | `collision_decision` | collision.account_policy needs provider truth, and a sandbox has none |
| S04 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S04 | `rule2_step_unimplemented` | the marker itself, not a verdict |
| S05 | `collision_decision` | collision.account_policy needs provider truth, and a sandbox has none |
| S05 | `only_the_operator_may_close` | a policy, not a computed verdict |
| S05 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S05 | `rule2_step_unimplemented` | the marker itself, not a verdict |
| S06 | `classification_only_no_send` | no revival classifier exists to ask |
| S06 | `collision_decision` | collision.account_policy needs provider truth, and a sandbox has none |
| S06 | `revival_cooling_days_in_claude_md` | a document, not a verdict |
| S06 | `revival_cooling_days_in_code` | a config value, not a verdict |
| S06 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S06 | `rule2_step_unimplemented` | the marker itself, not a verdict |
| S07 | `collision_decision` | collision.account_policy needs provider truth, and a sandbox has none |
| S07 | `gap_rule_does_not_exist` | the absence IS the finding; nothing to call |
| S07 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S07 | `rule2_step_unimplemented` | the marker itself, not a verdict |
| S08 | `collision_decision` | collision.account_policy needs provider truth, and a sandbox has none |
| S08 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S08 | `rule2_step_unimplemented` | the marker itself, not a verdict |
| S08 | `treated_as_blocked` | depends on collision_decision, which is unanswerable here |
| S09 | `classifier_unaudited` | a LABEL the operator requires on every positive rate until 100 classifier-positives are reviewed |
| S10 | `hygiene_verdict` | hygiene.check raised TypeError in the sandbox |
| S10 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S13 | `hygiene_action` | no authority in this codebase answers this key |
| S13 | `hygiene_verdict` | hygiene.check raised TypeError in the sandbox |
| S14 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S15 | `classifier_unaudited` | a LABEL the operator requires on every positive rate until 100 classifier-positives are reviewed |
| S18 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S19 | `hygiene_action` | no authority in this codebase answers this key |
| S19 | `hygiene_verdict` | hygiene.check raised TypeError in the sandbox |
| S19 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S20 | `still_blocked_on_day_120` | asserted by the day-120 sweep, below |
| S21 | `hygiene_verdict` | hygiene.check raised TypeError in the sandbox |
| S21 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S22 | `held_on_day_0` | needs a revival hold authority |
| S22 | `held_on_day_44` | needs a revival hold authority |
| S22 | `hold_appears_in_weekly_report` | reported by this run, not by a module |
| S22 | `hold_duration_days_on_day_44` | needs a revival hold authority |
| S22 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S22 | `rule2_step_unimplemented` | the marker itself, not a verdict |
| S23 | `rule2_step_unimplemented` | the marker itself, not a verdict |
| S23 | `send_performed` | no send is performed in a sandbox by construction |
| S23 | `verdict` | needs a revival classifier |
| S23 | `window_applied_must_be_named` | needs a revival window reader |
| S25 | `deciding_code_must_be_named` | requires a reader that does not exist |
| S25 | `gap_config_key_exists` | no config key exists to read |
| S25 | `rule2_step` | no module computes the five-step rule-2 label; BLOCKED_FOREVER / ON_HOLD / COLD_LEAD / STARI return 0 grep hits across src/ |
| S25 | `rule2_step_unimplemented` | the marker itself, not a verdict |
| S26 | `still_refused_on_day_120` | asserted by the day-120 sweep, below |
| S27 | `appears_in_weekly_send_plan` | reported in the send plan |
| S27 | `estate_bounce_rate_source` | a provenance string, not a verdict |
| S27 | `mailbox_selected` | senderheadroom answers per mailbox; reported in the send plan |
| S27 | `send_plan_shrinks_against_forward_book` | reported in the send plan |
| S30 | `day_14_step_pushed` | needs a campaign timeline the sandbox has none of |
| S30 | `day_21_step_offered` | needs a campaign timeline the sandbox has none of |
| S30 | `step_shown_withdrawn_in_send_plan` | reported in the send plan |

