
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op,$rt){ $m=$asTask.MakeGenericMethod($rt); $tk=$m.Invoke($null,@($op)); $tk.Wait(); $tk.Result }
$prof=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if($prof -eq $null){ Write-Output 'NO-INTERNET-PROFILE'; exit }
$mgr=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($prof)
Write-Output ("BEFORE-State=" + $mgr.TetheringOperationalState)
Write-Output ("ClientCount=" + $mgr.ClientCount)
Write-Output ("MaxClients=" + $mgr.MaxClientCount)
$cfg=$mgr.GetCurrentAccessPointConfiguration()
Write-Output ("SSID=" + $cfg.Ssid)
Write-Output ("Band=" + $cfg.Band)
if($mgr.TetheringOperationalState -eq 1){
  $r=Await ($mgr.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
  Start-Sleep 2
}
$r2=Await ($mgr.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
Write-Output ("StartStatus=" + $r2.Status)
Write-Output ("AFTER-State=" + $mgr.TetheringOperationalState)
