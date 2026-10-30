# Windows packaging of the 2.0.0-alpha (PAR_Spectrometer_2.exe: desktop shell + local service in one exe).
# The service runs V1.0.3's coordinator for tiers 1/2 on PySide6 (internal notes), so the package contains
# PySide6's QtCore (Qt 6, LGPL-3.0), pymodbus and pyserial (16_ section 8) and no PyQt5 (S-6). Qt 6 needs Windows 10
# 1809 or later (64-bit).
# Steps: front end (npm ci, npm run build) -> WebView2 offline installer (download or hand-placed, signature checked)
# -> PyInstaller (PAR_Spectrometer_2.spec) -> licences and manifest -> frozen self-test -> frozen window smoke
# -> ZIP + SHA-256.
# Output: release\<version>\PAR_Spectrometer_2\ and release\<version>\PAR_Spectrometer_2.0.0-alpha.N.zip(.sha256).
# V1.0.3's build_release.ps1 and PAR_Spectrometer.spec are separate and unchanged (internal notes section 4).
# Step-by-step instructions: internal notes NOT FOR RELEASE: internal alpha, no hardware
# acceptance. Keep this file ASCII-only: Windows PowerShell 5.1 reads a script without a BOM in the ANSI code page.
param(
    # Python with requirements-build.lock installed. Default: the repository's .venv.
    [string]$Python = "",
    # A WebView2 Evergreen Standalone Installer (x64) placed by hand. Without it the script downloads one from
    # Microsoft. Either way the file must carry a valid Authenticode signature from Microsoft Corporation.
    [string]$WebView2Installer = "",
    # Optional SHA-256 the installer must have (pins a file you already checked).
    [string]$WebView2Sha256 = "",
    # Skip the frozen self-test (not for a package that will be delivered).
    [switch]$SkipSelfTest,
    # Skip the frozen window smoke (needs a desktop session and the WebView2 runtime on the build computer).
    [switch]$SkipWindowSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest is many times slower with the progress bar

$ProjectRoot = Split-Path -Parent $PSCommandPath
if (-not $Python) {
    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
    throw "Development Python was not found: $Python. Create .venv and install requirements-build.lock, or pass -Python."
}
$Python = (Resolve-Path -LiteralPath $Python).Path
$Tool = Join-Path $ProjectRoot "tools\alpha_release.py"
$RuntimeTool = Join-Path $ProjectRoot "tools\alpha_runtime.py"

# Clean PATH (#66): PyInstaller looks for DLLs on PATH, and alpha.3 picked up ucrtbase.dll from a build agent's own
# tool folder that was on the caller's PATH. The build, the self-test and the smoke see only the build venv's
# Scripts, the base Python install it was made from and the Windows system folders; Node is added for the npm steps
# only, git is called by its full path. The caller's PATH is never used.
$BasePython = (& $Python -c "import sys; print(sys.base_prefix)").Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $BasePython)) { throw "Reading sys.base_prefix failed." }
$SystemRoot = $env:SystemRoot
$CleanPath = @(
    (Split-Path -Parent $Python), $BasePython, "$SystemRoot\System32", $SystemRoot, "$SystemRoot\System32\Wbem",
    "$SystemRoot\System32\WindowsPowerShell\v1.0"
) -join ";"
$NodeCommand = Get-Command node -ErrorAction SilentlyContinue
$NpmCommand = Get-Command npm -ErrorAction SilentlyContinue
$GitCommand = Get-Command git -ErrorAction SilentlyContinue
$env:Path = $CleanPath
Write-Host "PATH for the build: $CleanPath"

# Microsoft's permanent link to the Evergreen Standalone Installer (x64), from the WebView2 download page
# (https://developer.microsoft.com/microsoft-edge/webview2/, "Evergreen Standalone Installer", x64).
$WebView2Url = "https://go.microsoft.com/fwlink/?linkid=2124701"
$InstallerName = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
$Utf8 = New-Object System.Text.UTF8Encoding $false  # Python's json reads UTF-8 without a BOM

function Write-Json([object]$Value, [string]$Path) {
    [System.IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 4), $Utf8)
}

function Invoke-Checked([string]$What, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$What failed with exit code $LASTEXITCODE"
    }
}

function Test-WebView2Installer([string]$Path, [string]$Source, [string]$OriginalName) {
    # Authenticode: Status Valid means the file is unmodified and chains to a trusted root on this computer.
    $Signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($Signature.Status -ne "Valid") {
        throw "WebView2 installer signature is $($Signature.Status) ($($Signature.StatusMessage)): $Path"
    }
    $Subject = $Signature.SignerCertificate.Subject
    if ($Subject -notmatch "(^|,\s*)O=Microsoft Corporation(,|$)") {
        throw "WebView2 installer is not signed by Microsoft Corporation (signer: $Subject): $Path"
    }
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($WebView2Sha256 -and $Hash -ne $WebView2Sha256.ToLowerInvariant()) {
        throw "WebView2 installer SHA-256 $Hash does not match -WebView2Sha256 $WebView2Sha256"
    }
    $Item = Get-Item -LiteralPath $Path
    return [ordered]@{
        file = "redist/$InstallerName"
        source = $Source
        original_name = $OriginalName
        sha256 = $Hash
        size = $Item.Length
        signer = $Subject
        thumbprint = $Signature.SignerCertificate.Thumbprint
        version = $Item.VersionInfo.ProductVersion
        product = $Item.VersionInfo.ProductName
        description = $Item.VersionInfo.FileDescription
        sha256_pinned = [bool]$WebView2Sha256
    }
}

$Names = (& $Python $Tool names) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "Reading the alpha version failed." }
$Version = $Names.version
$AppName = $Names.app_name
$BuildRoot = Join-Path $ProjectRoot "build\$Version"
$MetaRoot = Join-Path $BuildRoot "meta"
$DistRoot = Join-Path $ProjectRoot "dist\$Version"
$ReleaseRoot = Join-Path $ProjectRoot "release\$Version"
$WebRoot = Join-Path $ProjectRoot "web"
Write-Host "Building $AppName $Version (NOT FOR RELEASE)"

Invoke-Checked "PyInstaller check" { & $Python -m PyInstaller --version | Out-Null }
if (-not $NodeCommand -or -not $NpmCommand) {
    throw "Node.js 22.22.2 or newer (with npm) is required to build the web front end."
}
$NodeDir = Split-Path -Parent $NodeCommand.Source

# 1. Front end: web/dist with the bundled fonts (Noto Sans SC, JetBrains Mono and their OFL texts). Node's folder is
#    on PATH for these two steps only.
Push-Location $WebRoot
$env:Path = "$NodeDir;$CleanPath"
try {
    Invoke-Checked "npm ci" { & $NpmCommand.Source ci --no-audit --no-fund }
    Invoke-Checked "npm run build" { & $NpmCommand.Source run build }
}
finally {
    $env:Path = $CleanPath
    Pop-Location
}

# 2. Build information: commit and time, bundled into the exe and repeated in build_manifest.json.
New-Item -ItemType Directory -Path $MetaRoot -Force | Out-Null
$Commit = "unknown"
$Dirty = $null
if ($GitCommand) {
    $Git = $GitCommand.Source
    # Not a git checkout (source ZIP from GitHub): rev-parse fails and prints nothing; keep "unknown".
    # Windows PowerShell 5.1 turns redirected native stderr into errors, which "Stop" would make fatal.
    $Previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $Head = & $Git -C $ProjectRoot rev-parse HEAD 2>$null
        $HeadExit = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $Previous
    }
    if ($HeadExit -eq 0 -and $Head) {
        $Commit = "$Head".Trim()
        $Dirty = [bool](& $Git -C $ProjectRoot status --porcelain --untracked-files=no)
    }
}
$BuildInfo = Join-Path $MetaRoot "build_info.json"
Write-Json ([ordered]@{
    version = $Version
    commit = $Commit
    dirty = $Dirty
    built_at = (Get-Date).ToUniversalTime().ToString("o")
}) $BuildInfo
if ($Dirty) {
    Write-Warning "The working tree has uncommitted changes; build_manifest.json records dirty=true."
}

# 3. WebView2 offline installer: hand-placed or downloaded, never committed to the repository.
$Installer = Join-Path $MetaRoot $InstallerName
Remove-Item -LiteralPath $Installer -Force -ErrorAction SilentlyContinue
if ($WebView2Installer) {
    Copy-Item -LiteralPath $WebView2Installer -Destination $Installer
    $OriginalName = Split-Path -Leaf $WebView2Installer
    $Source = "placed by hand: $OriginalName"
}
else {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-Host "Downloading the WebView2 Evergreen Standalone Installer (x64) from $WebView2Url"
    Invoke-WebRequest -Uri $WebView2Url -OutFile $Installer -UseBasicParsing
    $Source = $WebView2Url
    $OriginalName = $InstallerName
}
$WebView2Info = Join-Path $MetaRoot "webview2.json"
$Checked = Test-WebView2Installer $Installer $Source $OriginalName
Write-Json $Checked $WebView2Info
# Signature alone also fits Edge, the online bootstrapper or another architecture: check product name, size and
# x64 (tools/alpha_release.py check_webview2; review of PR #50, major 3).
Invoke-Checked "WebView2 installer identity" { & $Python $Tool check-webview2 $WebView2Info }
Write-Host "WebView2 installer OK: $($Checked.version), SHA-256 $($Checked.sha256), signed by $($Checked.signer)"

# 4. Keep the previous release folder instead of deleting it (same as build_release.ps1).
if (Test-Path $ReleaseRoot) {
    $ArchiveRoot = Join-Path $ProjectRoot ("stage_backups\release_" + $Version + "_" + (Get-Date -Format "yyyyMMdd_HHmmss_fff"))
    New-Item -ItemType Directory -Path (Split-Path -Parent $ArchiveRoot) -Force | Out-Null
    Move-Item -LiteralPath $ReleaseRoot -Destination $ArchiveRoot
    Write-Host "Previous release preserved: $ArchiveRoot"
}

# 5. PyInstaller: one exe, two processes (shell, --service), on the clean PATH. The spec records where every
#    collected binary comes from; the record is checked before anything is packaged (#66).
$env:Path = $CleanPath
$BinarySources = Join-Path $MetaRoot "binary_sources.json"
Remove-Item -LiteralPath $BinarySources -Force -ErrorAction SilentlyContinue
$env:PAR_ALPHA_BUILD_INFO = $BuildInfo
$env:PAR_ALPHA_BINARY_SOURCES = $BinarySources
Push-Location $ProjectRoot
try {
    Invoke-Checked "PyInstaller" {
        & $Python -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $BuildRoot `
            (Join-Path $ProjectRoot "PAR_Spectrometer_2.spec")
    }
}
finally {
    Pop-Location
    Remove-Item Env:PAR_ALPHA_BUILD_INFO
    Remove-Item Env:PAR_ALPHA_BINARY_SOURCES
}
if (-not (Test-Path -LiteralPath $BinarySources)) { throw "The spec wrote no binary sources record: $BinarySources" }
Invoke-Checked "Binary sources" { & $Python $RuntimeTool check $BinarySources }

# 6. Release folder: program, offline installer; the tool adds the notes, licences and manifest.
$AppRoot = Join-Path $ReleaseRoot $AppName
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null
Copy-Item (Join-Path $DistRoot $AppName) $AppRoot -Recurse
New-Item -ItemType Directory -Path (Join-Path $AppRoot "redist") -Force | Out-Null
Copy-Item -LiteralPath $Installer -Destination (Join-Path $AppRoot "redist\$InstallerName")
Invoke-Checked "Licences and manifest" {
    & $Python $Tool metadata $AppRoot --toc (Join-Path $BuildRoot "$AppName\PYZ-00.toc") --web $WebRoot `
        --build-info $BuildInfo --webview2 $WebView2Info
}

# 7. Frozen self-test before the archive, so a failed build leaves no deliverable-looking ZIP: service, health,
#    token, page with every script/stylesheet/font it loads, synthetic import, one record (54 metrics, 701 points),
#    tier 1 on a synthetic Modbus TCP gateway on 127.0.0.1 (no serial port, no device; takeover start, a saved
#    record, V1.0.3's lock held then free again, back to tier 0; tier 2 is never entered), stop via
#    POST /api/v0/shutdown with no thread left, Qt version as recorded, the service watching the shell (D-223), WebView2 back end, installer
#    identical to the checked file. The tier-1 steps need V1.0.3's lock: close V1.0.3 on the build computer.
$Exe = Join-Path $AppRoot $Names.exe
if ($SkipSelfTest) {
    Write-Warning "Self-test skipped (-SkipSelfTest): run it before delivering the package."
}
else {
    $Report = Join-Path $MetaRoot "self-test-report.json"
    Remove-Item -LiteralPath $Report -Force -ErrorAction SilentlyContinue
    $Process = Start-Process -FilePath $Exe -ArgumentList @("--alpha-self-test", "`"$Report`"") -Wait -PassThru
    if (-not (Test-Path $Report)) { throw "The self-test wrote no report (exit code $($Process.ExitCode))." }
    Get-Content -LiteralPath $Report -Encoding UTF8
    $Result = Get-Content -LiteralPath $Report -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Process.ExitCode -ne 0 -or -not $Result.passed -or -not $Result.frozen) {
        throw "Alpha self-test failed (exit code $($Process.ExitCode)); see $Report"
    }
    if ($Result.level1 -ne "passed") {
        throw "Alpha self-test did not check tier 1 ($($Result.level1)); close V1.0.3 and build again."
    }
    Write-Host "Alpha self-test passed: $Report"
}

# 8. Frozen window smoke: the real window opens the page, whose scripts must fetch the devices and render the four
#    device buttons; the window then closes by itself (par_shell --smoke). Exit code 3: no WebView2 runtime here.
if ($SkipWindowSmoke) {
    Write-Warning "Window smoke skipped (-SkipWindowSmoke): open the program once before delivering the package."
}
else {
    $SmokeData = Join-Path $MetaRoot "smoke-data"
    Remove-Item -LiteralPath $SmokeData -Recurse -Force -ErrorAction SilentlyContinue
    $Smoke = Start-Process -FilePath $Exe -ArgumentList @("--smoke", "60", "--data-dir", "`"$SmokeData`"") -Wait -PassThru
    if ($Smoke.ExitCode -eq 3) {
        throw "Window smoke: no WebView2 runtime on this computer. Install redist\$InstallerName or pass -SkipWindowSmoke."
    }
    if ($Smoke.ExitCode -ne 0) {
        throw "Window smoke failed (exit code $($Smoke.ExitCode)): the page did not render; see $SmokeData\logs"
    }
    Write-Host "Window smoke passed: the page rendered its device buttons."
}

# 9. Check the folder and write the ZIP and its SHA-256.
Invoke-Checked "Archive" { & $Python $Tool package $AppRoot $ReleaseRoot }
Write-Host "Release package created: $AppRoot"
Write-Host "Deliver $($Names.archive) or the whole $AppName folder; do not copy only the EXE file. NOT FOR RELEASE."
