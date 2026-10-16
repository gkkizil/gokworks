param(
    [Parameter(Mandatory = $true)][string]$PackagePath,
    [Parameter(Mandatory = $true)][string]$RequestPath,
    [Parameter(Mandatory = $true)][string]$ReportPath
)

$ErrorActionPreference = 'Stop'
$report = [ordered]@{
    status = 'unavailable'
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    finished_at = $null
    artifact_id = $null
    source_commit = $null
    files = @{}
    defender = @{}
    excluded_paths_temporarily_removed = @()
    scan_exit_code = $null
    detections = @()
    error = $null
    limitations = 'A local Defender scan is not a Chrome Safe Browsing verdict or proof of safety.'
}
$removed = @()
$restorePreferences = @{}
$scanLog = [IO.Path]::ChangeExtension([IO.Path]::GetFullPath($ReportPath), '.scan.log')
try {
    # This script may alter exclusions ONLY on the disposable GitHub runner.
    # It must never change protection settings on the user's Windows machine.
    if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') {
        throw 'This scan is restricted to an ephemeral GitHub Windows runner.'
    }
    $PackagePath = (Resolve-Path -LiteralPath $PackagePath).Path
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $report.artifact_id = $request.artifact_id
    $report.source_commit = $request.source_commit
    foreach ($property in $request.expected_executables.PSObject.Properties) {
        if ([IO.Path]::GetFileName($property.Name) -ne $property.Name) { throw 'Expected executable must be a filename.' }
        $path = Join-Path $PackagePath $property.Name
        $digest = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($digest -ne $property.Value) { throw "Original artifact hash mismatch: $($property.Name)" }
        $signature = Get-AuthenticodeSignature -LiteralPath $path
        $report.files[$property.Name] = @{
            sha256 = $digest
            bytes = (Get-Item -LiteralPath $path).Length
            authenticode_status = $signature.Status.ToString()
            signer = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
        }
    }
    $unexpected = @(Get-ChildItem -LiteralPath $PackagePath -Recurse -File | Where-Object {
        $_.Extension -in @('.exe', '.dll', '.ps1', '.cmd', '.bat', '.vbs', '.js') -and -not $report.files.ContainsKey($_.Name)
    })
    if ($unexpected.Count) { throw "Unexpected executable/script in the original package: $($unexpected.Name -join ', ')" }
    $service = Get-Service -Name WinDefend -ErrorAction Stop
    if ($service.Status -ne 'Running') { Start-Service -Name WinDefend -ErrorAction Stop }
    try { Update-MpSignature -ErrorAction Stop }
    catch { $report.defender.signature_update_error = $_.Exception.Message }
    $computer = Get-MpComputerStatus -ErrorAction Stop
    $report.defender.engine_version = $computer.AMEngineVersion
    $report.defender.signature_version = $computer.AntivirusSignatureVersion
    $report.defender.signature_updated_at = $computer.AntivirusSignatureLastUpdated.ToUniversalTime().ToString('o')
    $report.defender.running_mode = $computer.AMRunningMode
    $report.defender.service_enabled = $computer.AMServiceEnabled
    $report.defender.antivirus_enabled = $computer.AntivirusEnabled
    if (-not $computer.AMServiceEnabled -or -not $computer.AntivirusEnabled -or $computer.AMRunningMode -ne 'Normal') {
        throw 'Defender is not running as an enabled antivirus in Normal mode; coverage cannot be established.'
    }
    if ($computer.AntivirusSignatureLastUpdated -lt (Get-Date).AddDays(-7)) { throw 'Defender signatures are older than seven days.' }

    # Runner images exclude C:\ and D:\. Remove only exclusions covering this
    # package, then restore their exact original values in finally.
    $preferences = Get-MpPreference
    $scanPreferences = @{ DisableArchiveScanning = $false; DisableScriptScanning = $false; PUAProtection = 1; ScanAvgCPULoadFactor = 50 }
    foreach ($name in $scanPreferences.Keys) { $restorePreferences[$name] = $preferences.$name }
    Set-MpPreference @scanPreferences -ErrorAction Stop
    $report.defender.custom_scan_preferences = $scanPreferences
    $report.defender.original_path_exclusions = @($preferences.ExclusionPath)
    $report.defender.original_extension_exclusions = @($preferences.ExclusionExtension)
    foreach ($excluded in @($preferences.ExclusionPath)) {
        if (-not $excluded) { continue }
        $expanded = [Environment]::ExpandEnvironmentVariables($excluded).TrimEnd('\')
        if ($PackagePath -like "$expanded\*" -or $PackagePath -eq $expanded) {
            Remove-MpPreference -ExclusionPath $excluded -ErrorAction Stop
            $removed += $excluded
        }
    }
    $report.excluded_paths_temporarily_removed = @($removed)
    $remaining = Get-MpPreference
    foreach ($excluded in @($remaining.ExclusionPath)) {
        if (-not $excluded) { continue }
        $expanded = [Environment]::ExpandEnvironmentVariables($excluded).TrimEnd('\')
        if ($PackagePath -like "$expanded\*" -or $PackagePath -eq $expanded) {
            throw 'An effective Defender path exclusion still covers the package.'
        }
    }
    if (@($remaining.ExclusionExtension | Where-Object { $_ -in @('exe', '.exe', '*') }).Count) {
        throw 'An executable extension exclusion prevents establishing scan coverage.'
    }
    if ($remaining.DisableArchiveScanning -or $remaining.DisableScriptScanning -or [int]$remaining.PUAProtection -ne 1) {
        throw 'Effective scan settings do not include archive/script and unwanted-application inspection.'
    }
    $candidates = @(Get-ChildItem -Path "$env:ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    $scanner = if ($candidates.Count) { $candidates[0].FullName } else { "$env:ProgramFiles\Windows Defender\MpCmdRun.exe" }
    if (-not (Test-Path -LiteralPath $scanner)) { throw 'MpCmdRun.exe was not found.' }
    $report.defender.scanner = $scanner
    $scanStart = Get-Date
    & $scanner -Scan -ScanType 3 -File $PackagePath 2>&1 | Out-File -LiteralPath $scanLog -Encoding UTF8
    $report.scan_exit_code = $LASTEXITCODE
    $detections = @(Get-MpThreatDetection -ErrorAction Stop | Where-Object {
        # Conservatively retain every new detection during the dedicated scan,
        # including detections in an unpacked temporary payload.
        $_.InitialDetectionTime -ge $scanStart.AddMinutes(-1)
    })
    $report.detections = @($detections | Select-Object ThreatID, InitialDetectionTime, LastThreatStatusChangeTime, Resources, ActionSuccess)
    if ($detections.Count) {
        $report.status = 'detected'
        throw 'Defender reported a detection during this scan. Check the recorded resources; do not publish or execute this package.'
    }
    if ($report.scan_exit_code -ne 0) { throw "Defender scan did not complete successfully: exit $($report.scan_exit_code)" }
    foreach ($name in @($report.files.Keys)) {
        $path = Join-Path $PackagePath $name
        if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $report.files[$name].sha256) {
            throw "The package changed or was quarantined during the scan: $name"
        }
    }
    $report.status = 'no_detection'
}
catch { $report.error = $_.Exception.Message }
finally {
    if ($restorePreferences.Count) {
        try { Set-MpPreference @restorePreferences -ErrorAction Stop }
        catch { $report.error = "$($report.error) Scan-setting restoration failed: $($_.Exception.Message)"; $report.status = 'unavailable' }
    }
    foreach ($excluded in $removed) {
        try { Add-MpPreference -ExclusionPath $excluded -ErrorAction Stop }
        catch { $report.error = "$($report.error) Exclusion restoration failed: $($_.Exception.Message)"; $report.status = 'unavailable' }
    }
    $report.finished_at = (Get-Date).ToUniversalTime().ToString('o')
    $destination = [IO.Path]::GetFullPath($ReportPath)
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($destination)) -Force | Out-Null
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $destination -Encoding UTF8
}
if ($report.status -ne 'no_detection') { exit 2 }
