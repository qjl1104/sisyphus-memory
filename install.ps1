[CmdletBinding()]
param(
    [string]$OmoHome = $(if ($env:OMO_HOME) { $env:OMO_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.omo' }),
    [switch]$Update
)

$ErrorActionPreference = 'Stop'
$OmoHome = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OmoHome)
New-Item -ItemType Directory -Path $OmoHome -Force | Out-Null

$venvPath = Join-Path $OmoHome 'venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
if (Test-Path -LiteralPath $venvPath) {
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "Existing venv is incomplete: $venvPath. Use -OmoHome to install in another directory."
    }
    Write-Host "Keeping existing Python environment: $venvPath"
} else {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw 'Install Python 3.12 and the Windows Python launcher (py) first.'
    }
    & py -3.12 -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the Python environment.' }
}

& $venvPython -c 'from importlib.util import find_spec; import sys; sys.exit(not all(find_spec(name) for name in sys.argv[1:]))' chromadb sentence_transformers filelock mcp
if ($Update -or $LASTEXITCODE -ne 0) {
    & $venvPython -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed. To retry: & '$venvPython' -m pip install -r '$requirements'"
    }
}

foreach ($file in @('codex_import.py', 'memory_mcp.py', 'memory_tool.py')) {
    $destination = Join-Path $OmoHome $file
    if ($Update -or -not (Test-Path -LiteralPath $destination)) {
        [System.IO.File]::Copy((Join-Path $PSScriptRoot $file), $destination, [bool]$Update)
    }
}

$summaryPath = Join-Path $OmoHome 'memory.md'
if (-not (Test-Path -LiteralPath $summaryPath)) {
    [System.IO.File]::Copy((Join-Path $PSScriptRoot 'examples\memory.template.md'), $summaryPath)
}

Write-Host "Sisyphus memory files: $OmoHome"
Write-Host 'See docs/AGENTS.example.md for assistant integration.'
