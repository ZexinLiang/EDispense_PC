Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
Function Await($op, $resultType) {
  $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($op))
  $task.Wait(20000) | Out-Null
  return $task.Result
}
[void][Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
[void][Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if($profile -eq $null){
  # 断网态:用任意一个connection profile拉manager
  $mgr = $null
  try { $mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($null) } catch {}
} else {
  $mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
}
if($mgr -eq $null){ Write-Output "ERR-nomgr"; exit 1 }
$state = $mgr.TetheringOperationalState
Write-Output ("STATE-BEFORE=" + $state)
if($state -ne 'On'){
  $res = Await ($mgr.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
  Write-Output ("START=" + $res.Status)
} else {
  Write-Output "ALREADY-ON"
}
Write-Output ("STATE-AFTER=" + $mgr.TetheringOperationalState)
