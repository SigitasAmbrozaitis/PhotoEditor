# Development mode: backend API + UI dev server with hot reload.
#
#   Backend : http://127.0.0.1:8765   (separate window, shows server logs)
#   UI      : http://localhost:5173   (opens in the browser; /api is proxied to the backend)
#
# Ctrl+C stops the UI dev server and the backend.
# Run via scripts\dev.cmd, or: powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

foreach ($tool in 'uv', 'npm') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "'$tool' not found on PATH. Install it (see README) and open a new terminal."
    }
}

if (-not (Test-Path (Join-Path $root 'ui\node_modules'))) {
    Write-Host 'Installing UI dependencies (first run)...'
    npm --prefix (Join-Path $root 'ui') install
}

Write-Host 'Starting backend on http://127.0.0.1:8765 ...'
$backend = Start-Process -PassThru -WorkingDirectory $root -FilePath 'uv' `
    -ArgumentList 'run', 'photoedit', 'ui', '--no-browser'

try {
    Push-Location (Join-Path $root 'ui')
    npm run dev -- --open
}
finally {
    Pop-Location
    if (-not $backend.HasExited) {
        Write-Host 'Stopping backend...'
        # /T kills the whole tree (uv -> python), /F forces it.
        taskkill /PID $backend.Id /T /F | Out-Null
    }
}
