param(
    [string]$Python = "",
    [string]$EnvDir = ".venv",
    [switch]$SkipInstall
)
$ErrorActionPreference = "Stop"
$bootstrapArgs = @("-X", "utf8", (Join-Path $PSScriptRoot "bootstrap.py"), "--env-dir", $EnvDir)
if ($SkipInstall) { $bootstrapArgs += "--skip-install" }
if (-not $Python) {
    foreach ($candidate in @("python", "py")) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            $probeArgs = @("-c", "import sys; print(sys.executable if sys.version_info[:2] == (3,12) else '')")
            if ($candidate -eq "py") { $probeArgs = @("-3.12") + $probeArgs }
            $foundPython = & $candidate @probeArgs 2>$null
            if ($LASTEXITCODE -eq 0 -and $foundPython) { $Python = "$foundPython".Trim(); break }
        }
    }
}
if (-not $Python) { throw "Install Python 3.12 or activate a Python 3.12 Anaconda environment; then rerun with -Python." }
& $Python @bootstrapArgs
exit $LASTEXITCODE
