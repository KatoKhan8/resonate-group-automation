# TASK-0110 existence sweep: every named artifact for the 19 UNKNOWN rows.
$env:GIT_CONFIG_COUNT = $null
$out = @()

# --- Filesystem artifacts (direct logs) ---
$fs = @(
  'C:\Users\Zvonimir\Desktop\resonate-ops\glm-review-2026-10-14\TASK-0020-halt-repro\MUTATION-PROOF.txt',
  'C:\Users\Zvonimir\Desktop\resonate-ops\glm-review-2026-10-14\b4_template_map.py'
)
foreach ($p in $fs) {
  if (Test-Path -LiteralPath $p) {
    $i = Get-Item -LiteralPath $p
    $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.Substring(0,16)
    $out += "FS EXISTS  $p  $($i.Length)B  mtime=$($i.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))  sha256=$h"
  } else { $out += "FS MISSING $p" }
}
$out += "--- .codex/0063 dir ---"
if (Test-Path '.codex\0063') {
  Get-ChildItem '.codex\0063' | ForEach-Object { $out += "  0063: $($_.Name)  $($_.Length)B  $($_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))" }
} else { $out += "  .codex\0063 MISSING" }
$out += "--- resonate-ops glm-review-2026-10-14 dir (names only) ---"
if (Test-Path 'C:\Users\Zvonimir\Desktop\resonate-ops\glm-review-2026-10-14') {
  Get-ChildItem 'C:\Users\Zvonimir\Desktop\resonate-ops\glm-review-2026-10-14' -Recurse -File |
    ForEach-Object { $out += "  review: $($_.FullName.Replace('C:\Users\Zvonimir\Desktop\resonate-ops\glm-review-2026-10-14\',''))  $($_.Length)B" }
} else { $out += "  glm-review-2026-10-14 dir MISSING" }

# --- Git ref artifacts ---
$refs = @(
  '04c0bbb37:tests/test_no_template_escapes_the_word_contract.py',
  'fca459853:tests/test_every_body_is_signed_by_the_pools_owner.py',
  'fca459853:tests/fixtures/sender-estate-2026-09-21.json',
  '6caa9ea58:tests/test_a_safety_pause_fails_open.py',
  '93162471d:tests/test_a_pause_of_an_unresolvable_campaign_refuses.py',
  '93162471d:tests/test_a_plan_whose_copy_fails_lint_is_refused.py',
  '93162471d:tests/test_a_positive_reply_holds_the_account_and_suppresses_nobody.py',
  '93162471d:tests/test_a_refused_pause_pauses_nothing.py',
  '93162471d:tests/test_a_refused_stop_does_not_lose_the_reply.py',
  '93162471d:tests/test_an_absent_leads_copy_is_named_not_passed.py',
  '06bd434de:tests/test_the_word_ceiling_is_enforced_on_the_composed_body.py',
  '3e0d3289f:tests/test_a_resume_verb_from_batch_activate_must_pass_the_door.py',
  '3e0d3289f:tests/test_a_resume_verb_from_resume_487_must_pass_the_door.py',
  '0f7228a99:scripts/batch_activate.py',
  '0f7228a99:scripts/resume_487.py',
  '8dc1ed55f:tests/test_no_template_escapes_the_word_contract.py',
  '8dc1ed55f:tests/test_every_body_is_signed_by_the_pools_owner.py',
  '8dc1ed55f:tests/fixtures/sender-estate-2026-09-21.json',
  '8dc1ed55f:tests/test_a_safety_pause_fails_open.py',
  '8dc1ed55f:tests/test_the_word_ceiling_is_enforced_on_the_composed_body.py',
  '8dc1ed55f:tests/test_a_resume_verb_from_batch_activate_must_pass_the_door.py',
  '8dc1ed55f:tests/test_a_resume_verb_from_resume_487_must_pass_the_door.py',
  '8dc1ed55f:tests/test_a_pause_of_an_unresolvable_campaign_refuses.py'
)
foreach ($r in $refs) {
  git cat-file -e "$r" 2>$null
  if ($LASTEXITCODE -eq 0) {
    $sha = git rev-parse "$r"
    $out += "GIT EXISTS $r blob=$sha"
  } else { $out += "GIT MISSING $r" }
}
$out += "--- tree flavour: CR bytes in requirements.txt ---"
$raw = [System.IO.File]::ReadAllBytes('requirements.txt')
$cr = ($raw | Where-Object { $_ -eq 13 }).Count
$out += "requirements.txt CR=$cr size=$($raw.Length)B"
$out | Out-File -FilePath '.codex\0110\existence.txt' -Encoding utf8
Get-Content '.codex\0110\existence.txt'
