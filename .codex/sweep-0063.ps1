$ErrorActionPreference = 'Continue'
# SELF-CHECK: the querying process must be visible, else the table is unreadable
$self = Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
if ($self) {
  Write-Output ("SELFCHECK pid={0} cl_len={1}" -f $self.ProcessId, $self.CommandLine.Length)
} else {
  Write-Output "SELFCHECK FAILED - process table unreadable, nothing below is evidence"
  exit 2
}
# Sweep for anything suite-shaped
$rows = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_suite|tests\.offline|unittest' -and $_.ProcessId -ne $PID }
if ($rows) {
  foreach ($r in @($rows)) {
    $cl = $r.CommandLine
    if ($cl.Length -gt 200) { $cl = $cl.Substring(0,200) }
    Write-Output ("MATCH pid={0} cl={1}" -f $r.ProcessId, $cl)
  }
} else {
  Write-Output "NO_MATCHES"
}
# Holder liveness
foreach ($hp in 84496, 83452, 66704) {
  $h = Get-CimInstance Win32_Process -Filter "ProcessId=$hp"
  if ($h) { Write-Output ("HOLDER {0} ALIVE" -f $hp) } else { Write-Output ("HOLDER {0} ABSENT" -f $hp) }
}
