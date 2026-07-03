
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$cm=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
$p=$cm::GetInternetConnectionProfile()
if($p){
 $mgr=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($p)
 Write-Output ("STATE=" + $mgr.TetheringOperationalState)
 Write-Output ("CLIENTS=" + $mgr.ClientCount)
 $ap=$mgr.GetCurrentAccessPointConfiguration()
 Write-Output ("SSID=" + $ap.Ssid)
 Write-Output ("PASS=" + $ap.Passphrase)
}else{ Write-Output "无活动联网profile" }
