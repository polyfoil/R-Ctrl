#Requires -Version 5.1
<#
  Build one-folder Windows widget bundle (PyInstaller) in an isolated venv.

  Output (gitignored):
    dist\R-Ctrl-Whisperer\
    dist\R-Ctrl-Whisperer-win64.zip
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== R-Ctrl Whisperer widget build ==" -ForegroundColor Cyan

$Venv = Join-Path $Root ".venv-build"
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "Creating build venv at .venv-build ..."
    python -m venv $Venv
}

& $Py -m pip install -q --upgrade pip
& $Py -m pip install -q -r requirements_widget.txt -r packaging/requirements-build.txt

& $Py -m PyInstaller packaging/rctrl_widget.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$OutDir = Join-Path $Root "dist\R-Ctrl-Whisperer"
if (-not (Test-Path (Join-Path $OutDir "R-Ctrl-Whisperer.exe"))) {
    throw "Build failed: exe not found in $OutDir"
}

Copy-Item -Force (Join-Path $Root "packaging\Start-R-Ctrl-Whisperer.bat") $OutDir
Copy-Item -Force (Join-Path $Root "packaging\RELEASE-README.txt") $OutDir

$Zip = Join-Path $Root "dist\R-Ctrl-Whisperer-win64.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Start-Sleep -Seconds 2
$Stage = Join-Path $env:TEMP ("rctrl-whisperer-" + [guid]::NewGuid().ToString())
Copy-Item -Recurse -Force $OutDir $Stage
# Never ship machine-local settings or dictation history in the release zip.
foreach ($localOnly in @("config.json", "inbox.json")) {
    $p = Join-Path $Stage $localOnly
    if (Test-Path $p) { Remove-Item $p -Force }
}
try {
    Compress-Archive -Path $Stage -DestinationPath $Zip -CompressionLevel Optimal
} finally {
    Remove-Item -Recurse -Force $Stage -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Folder: $OutDir"
Write-Host "  Zip:    $Zip"
Write-Host "  Attach the zip to a GitHub Release (do not commit the zip)."
