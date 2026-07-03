param(
  [string]$Ssid = $(if($env:EDISPENSE_AP_SSID){$env:EDISPENSE_AP_SSID}else{"EDispense-AP"}),
  [string]$Passphrase = $(if($env:EDISPENSE_AP_PASS){$env:EDISPENSE_AP_PASS}else{"changeme12345"})
)

[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking,ContentType=WindowsRuntime] | Out-Null
[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking,ContentType=WindowsRuntime] | Out-Null

$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if($profile -eq $null){ Write-Output "NO-INTERNET-PROFILE"; }
else {
  Write-Output ("UPSTREAM=" + $profile.ProfileName)
  $mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
  Write-Output ("STATE-BEFORE=" + $mgr.TetheringOperationalState)
  $cfg = $mgr.GetCurrentAccessPointConfiguration()
  Write-Output ("SSID-CUR=" + $cfg.Ssid)
  # 设置SSID/密码
  $cfg.Ssid = $Ssid
  $cfg.Passphrase = $Passphrase
  $t = $mgr.ConfigureAccessPointAsync($cfg)
  while($t.Status -eq 0){ Start-Sleep -Milliseconds 200 }
  Write-Output ("CONFIG-RESULT=" + $t.Status)
  # 启动
  $op = $mgr.StartTetheringAsync()
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while($op.Status -eq 0 -and $sw.Elapsed.TotalSeconds -lt 25){ Start-Sleep -Milliseconds 300 }
  Write-Output ("START-STATUS=" + $op.Status)
  try{ $r = $op.GetResults(); Write-Output ("START-RESULT=" + $r.Status) }catch{ Write-Output ("START-ERR=" + $_.Exception.Message) }
  Write-Output ("STATE-AFTER=" + $mgr.TetheringOperationalState)
}
