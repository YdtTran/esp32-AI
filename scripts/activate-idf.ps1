# Dot-source: . .\scripts\activate-idf.ps1 [-UseInstallerProfile]
[CmdletBinding()]
param([switch]$UseInstallerProfile)

$idfPreviousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = 'Stop'
try {
    $idfPaths = @{
        IDF_PATH = 'E:\esp\.espressif\v6.1\esp-idf'
        IDF_TOOLS_PATH = 'C:\Espressif\tools'
        IDF_PYTHON_ENV_PATH = 'C:\Espressif\tools\python\v6.1\venv'
    }
    foreach ($idfEntry in $idfPaths.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $idfEntry.Value -PathType Container)) {
            throw "Missing $($idfEntry.Key): $($idfEntry.Value). Restore/check the confirmed installation; do not install another SDK."
        }
        Set-Item -Path "Env:$($idfEntry.Key)" -Value $idfEntry.Value
    }
    $idfPython = Join-Path $env:IDF_PYTHON_ENV_PATH 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $idfPython -PathType Leaf)) {
        throw "Missing existing Python executable: $idfPython. Check the confirmed v6.1 environment."
    }
    # Ensure export.ps1 uses the confirmed Python, not another PATH interpreter.
    $env:PATH = "$(Split-Path -Parent $idfPython);$env:PATH"
    $env:PYTHONUTF8 = '1'
    $idfActivation = Join-Path $env:IDF_PATH 'export.ps1'
    if ($UseInstallerProfile) {
        $idfActivation = Join-Path $env:IDF_TOOLS_PATH 'Microsoft.v6.1.PowerShell_profile.ps1'
    }
    if (-not (Test-Path -LiteralPath $idfActivation -PathType Leaf)) {
        throw "Missing activation script: $idfActivation. Check the existing Espressif installation."
    }
    if ($UseInstallerProfile) {
        . $idfActivation
    } else {
        & $idfActivation
    }
    foreach ($idfEntry in $idfPaths.GetEnumerator()) {
        if ([Environment]::GetEnvironmentVariable($idfEntry.Key) -ne $idfEntry.Value) {
            throw "Activation changed $($idfEntry.Key) away from the confirmed path."
        }
    }
    if (-not (Get-Command idf.py -ErrorAction SilentlyContinue)) {
        throw 'idf.py is unavailable after activation.'
    }
    $idfVersionOutput = idf.py --version 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $idfVersionOutput.Trim() -ne 'ESP-IDF v6.1') {
        throw "Expected ESP-IDF v6.1; command returned: $idfVersionOutput"
    }
    foreach ($idfTool in 'xtensa-esp-elf-gcc', 'riscv32-esp-elf-gcc', 'cmake', 'ninja') {
        $idfToolCommand = Get-Command $idfTool -ErrorAction SilentlyContinue
        if (-not $idfToolCommand) { throw "Missing tool: $idfTool. Check the existing tool installation." }
        & $idfTool --version | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Tool verification failed: $idfTool" }
        Write-Host "$idfTool available: $($idfToolCommand.Source)"
    }
    Write-Host $idfVersionOutput.Trim()
    Write-Host "Activated using $idfActivation. No chip target selected."
} catch {
    throw "ESP-IDF initialization failed: $($_.Exception.Message) For the verified flat installer layout, use '. .\scripts\activate-idf.ps1 -UseInstallerProfile'. Do not reinstall/upgrade ESP-IDF without approval."
} finally {
    $ErrorActionPreference = $idfPreviousErrorPreference
}

