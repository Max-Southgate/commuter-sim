# Runs the MVG delay collector in the foreground (it only polls inside the configured
# commute windows, so it's safe to leave running all day).
#
# To start it automatically when you log in to Windows, register it with Task Scheduler:
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -File `"$PSScriptRoot\run_collector.ps1`""
#   $trigger = New-ScheduledTaskTrigger -AtLogOn
#   Register-ScheduledTask -TaskName "commuter-sim collector" -Action $action -Trigger $trigger
#
# Logs go to data/collector.log.

$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "backend"
$log = Join-Path $repo "data\collector.log"
New-Item -ItemType Directory -Force (Join-Path $repo "data") | Out-Null

Set-Location $backend
# Full path to uv, because Task Scheduler's PATH may not include ~/.local/bin.
$uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
# Python writes the (UTF-8, rotating) log itself; PowerShell redirection would produce UTF-16.
& $uv run python -m app.collectors --log-file $log departures
