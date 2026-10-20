
param($OutFile)
$tasks = @(); $svcs = @()
try { Get-ScheduledTask -ErrorAction Stop | Where-Object { $_.TaskPath -notlike '\Microsoft\*' -and $_.State -ne 'Disabled' } | ForEach-Object {
    $a = $_.Actions | Select-Object -First 1
    $tasks += @{ name = [string]$_.TaskName; where = [string]$_.TaskPath; exec = [string]$a.Execute; args = [string]$a.Arguments } } } catch {}
try { Get-CimInstance Win32_Service -Filter "StartMode='Auto'" -ErrorAction Stop | ForEach-Object {
    $svcs += @{ name = [string]$_.Name; display = [string]$_.DisplayName; path = [string]$_.PathName } } } catch {}
@{ tasks = $tasks; services = $svcs } | ConvertTo-Json -Depth 4 -Compress | Out-File -Encoding UTF8 $OutFile
