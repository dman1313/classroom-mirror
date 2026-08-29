[CmdletBinding()]
param(
    [switch] $CheckOnly
)

$ErrorActionPreference = "Stop"

if (-not $CheckOnly) {
    Write-Error "No installation was attempted. This increment supports -CheckOnly only."
    exit 64
}

function Test-EffectiveDirectoryWriteAccess {
    param([Parameter(Mandatory = $true)][string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }

    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principalSids = @($identity.User.Value)
        $principalSids += @($identity.Groups | ForEach-Object { $_.Value })
        $writeRights = [Security.AccessControl.FileSystemRights]::WriteData `
            -bor [Security.AccessControl.FileSystemRights]::CreateFiles `
            -bor [Security.AccessControl.FileSystemRights]::CreateDirectories `
            -bor [Security.AccessControl.FileSystemRights]::Modify `
            -bor [Security.AccessControl.FileSystemRights]::FullControl
        $allowed = $false
        $denied = $false
        foreach ($rule in (Get-Acl -LiteralPath $Path).Access) {
            try {
                $ruleSid = $rule.IdentityReference.Translate(
                    [Security.Principal.SecurityIdentifier]
                ).Value
            }
            catch {
                continue
            }
            if (($principalSids -contains $ruleSid) -and (($rule.FileSystemRights -band $writeRights) -ne 0)) {
                if ($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Deny) {
                    $denied = $true
                }
                else {
                    $allowed = $true
                }
            }
        }
        return ($allowed -and -not $denied)
    }
    catch {
        return $false
    }
}

$isWindows = $env:OS -eq "Windows_NT"
if (-not $isWindows) {
    Write-Output "Windows version: unsupported non-Windows host"
    Write-Output "Architecture: unsupported"
    Write-Output "Python/runtime: not checked"
    Write-Output "Execution policy: $((Get-ExecutionPolicy).ToString())"
    Write-Output "Per-user data: unavailable"
    Write-Output "Camera availability: not checked"
    Write-Output "Administrator: unknown"
    Write-Output "Preflight ready: False"
    exit 1
}

$osVersion = [Environment]::OSVersion.Version
$isSupportedWindows = $osVersion.Major -eq 10
$isX64 = ($env:PROCESSOR_ARCHITECTURE -eq "AMD64") -or `
    ($env:PROCESSOR_ARCHITEW6432 -eq "AMD64")
$architecture = if ($isX64) { "x64" } else { $env:PROCESSOR_ARCHITECTURE }

$pythonDescription = "not found"
$pythonReady = $false
$projectPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $projectPython -PathType Leaf) {
    $pythonVersion = & $projectPython --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pythonDescription = "$pythonVersion; project runtime present"
        $pythonReady = $true
    }
}
else {
    $pythonCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    }
    if ($null -ne $pythonCommand) {
        $pythonVersion = & $pythonCommand.Source --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonDescription = "$pythonVersion; project runtime missing"
        }
    }
}

$effectivePolicy = Get-ExecutionPolicy
$languageMode = $ExecutionContext.SessionState.LanguageMode

$dataParentReady = $false
if ($env:LOCALAPPDATA) {
    $dataParentReady = Test-EffectiveDirectoryWriteAccess -Path $env:LOCALAPPDATA
}
$dataDescription = "%LOCALAPPDATA%\ClassroomMirror; writable parent=$dataParentReady"

$cameraCount = 0
$cameraInventoryReady = $false
try {
    $cameras = @(Get-CimInstance -ClassName Win32_PnPEntity `
        -Filter "PNPClass = 'Camera' OR PNPClass = 'Image'" -ErrorAction Stop)
    $cameraCount = $cameras.Count
    $cameraInventoryReady = $true
}
catch {
    $cameraInventoryReady = $false
}
$cameraAvailable = $cameraInventoryReady -and ($cameraCount -gt 0)
$cameraDescription = "devices=$cameraCount; inventory-only (not an open/read PASS)"

$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
$isAdministrator = $principal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

$ready = $isSupportedWindows -and $isX64 -and $pythonReady -and `
    $dataParentReady -and $cameraAvailable -and (-not $isAdministrator)

Write-Output "Windows version: $($osVersion.ToString()); supported Windows 10/11=$isSupportedWindows"
Write-Output "Architecture: $architecture; supported x64=$isX64"
Write-Output "Python/runtime: $pythonDescription"
Write-Output "Execution policy: $effectivePolicy; language mode=$languageMode"
Write-Output "Per-user data: $dataDescription"
Write-Output "Camera availability: $cameraDescription"
Write-Output "Administrator: $isAdministrator (required: False)"
Write-Output "Preflight ready: $ready"

if ($ready) {
    exit 0
}
exit 1
