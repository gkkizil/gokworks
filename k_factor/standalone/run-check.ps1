param(
    [ValidateSet('inspect', 'verify')][string]$Mode = 'inspect',
    [string]$Request = '',
    [string]$SolidWorksInteropDir = 'C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist',
    [string]$PythonCommand = ''
)

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$runDirectory = Join-Path $PSScriptRoot ('reports\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
if (-not $Request) { $Request = Join-Path $PSScriptRoot ('examples\' + $Mode + '.json') }
$Request = (Resolve-Path $Request).Path
$requestData = Get-Content -LiteralPath $Request -Raw -Encoding UTF8 | ConvertFrom-Json
if ($requestData.mode -ne $Mode) { throw 'Request mode does not match -Mode.' }
if (-not (Test-Path -LiteralPath (Join-Path $SolidWorksInteropDir 'SolidWorks.Interop.sldworks.dll'))) {
    throw 'SolidWorks interop not found. Pass the installed api\redist folder with -SolidWorksInteropDir.'
}
$dotnet = (Get-Command dotnet -ErrorAction Stop).Source
if (-not $PythonCommand) {
    $venvPython = Join-Path $workspace '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) { $PythonCommand = $venvPython }
    else { $PythonCommand = (Get-Command py -ErrorAction Stop).Source }
}
$project = Join-Path $PSScriptRoot 'csharp\Gokworks.KrProbe.csproj'
$buildDirectory = Join-Path $runDirectory 'build'
$csharpReport = Join-Path $runDirectory 'csharp.json'
$pythonReport = Join-Path $runDirectory 'python.json'
$comparisonReport = Join-Path $runDirectory 'comparison.json'

Push-Location $workspace
try {
    & $dotnet build $project --configuration Release "-p:SolidWorksInteropDir=$SolidWorksInteropDir" --output $buildDirectory
    if ($LASTEXITCODE -ne 0) { throw 'C# build failed.' }
    & $dotnet (Join-Path $buildDirectory 'Gokworks.KrProbe.dll') --request $Request --report $csharpReport
    if ($LASTEXITCODE -ne 0) { throw "C# run failed. Report: $csharpReport. Python was not started." }
    $nativeResult = Get-Content -LiteralPath $csharpReport -Raw -Encoding UTF8 | ConvertFrom-Json
    $expectedStatus = if ($Mode -eq 'inspect') { 'inspected' } else { 'verified' }
    if ($nativeResult.status -ne $expectedStatus) { throw "C# did not complete the requested check. Report: $csharpReport. Python was not started." }
    if ($Mode -eq 'verify' -and $nativeResult.rollback.verified -ne $true) { throw "C# restoration was not verified. Python was not started. Do not save the part. Report: $csharpReport" }
    # Bind the second engine before any Python write, rather than detecting a
    # different document/configuration only after both transactions finish.
    $boundRequest = [ordered]@{}
    foreach ($property in $requestData.PSObject.Properties) { $boundRequest[$property.Name] = $property.Value }
    $boundRequest['document_path'] = $nativeResult.document_path
    $boundRequest['configuration'] = $nativeResult.configuration
    $boundRequest['feature_name'] = $nativeResult.before.feature_name
    $boundRequest['expected_state'] = $nativeResult.before
    $pythonRequest = Join-Path $runDirectory 'python-request.json'
    $boundRequest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $pythonRequest -Encoding UTF8
    & $PythonCommand -m k_factor.standalone.python --request $pythonRequest --report $pythonReport
    if ($LASTEXITCODE -ne 0) { throw "Python run failed. Report: $pythonReport" }
    $comparisonArguments = @((Join-Path $PSScriptRoot 'compare_reports.py'), $csharpReport, $pythonReport, '--output', $comparisonReport)
    if ($Mode -eq 'inspect') { $comparisonArguments += '--inspection' }
    & $PythonCommand @comparisonArguments
    if ($LASTEXITCODE -ne 0) { throw "Runs were not verified as equivalent. Report: $comparisonReport" }
    Write-Host "Reports: $runDirectory"
}
finally {
    Pop-Location
}
