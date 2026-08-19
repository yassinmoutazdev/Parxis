# Praxis Launcher - PowerShell implementation
#
# run.bat hands off to this script immediately. This is where all the real
# work happens: checking prerequisites, installing dependencies, running
# migrations, and starting the backend + frontend as hidden background
# processes. Nothing here opens a visible console window.
#
# While things are starting up, a small local status page is shown in the
# browser (logs\praxis-status.html) so there's never dead silence - it
# auto-refreshes and swaps itself for the real app once both servers report
# healthy, or shows a plain-language error with a log excerpt if something
# goes wrong.
#
# Usage (normally invoked by run.bat / stop.bat, not run directly):
#   powershell -File run.ps1 -Action Start
#   powershell -File run.ps1 -Action Stop

param(
    [ValidateSet('Start', 'Stop')]
    [string]$Action = 'Start'
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

$ScriptDir   = $PSScriptRoot
$RepoRoot    = Split-Path -Parent $ScriptDir
$BackendDir  = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$LogsDir     = Join-Path $RepoRoot 'logs'

$BackendPidFile  = Join-Path $LogsDir 'backend.pid'
$FrontendPidFile = Join-Path $LogsDir 'frontend.pid'
$LauncherLog     = Join-Path $LogsDir 'launcher.log'
$StatusPage      = Join-Path $LogsDir 'praxis-status.html'

$HealthUrl   = 'http://127.0.0.1:8000/health'
$FrontendUrl = 'http://localhost:5173'

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Log {
    param([string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $LauncherLog -Value $line -ErrorAction SilentlyContinue
}

function HtmlEncode {
    param([string]$Text)
    if ([string]::IsNullOrEmpty($Text)) { return '' }
    return [System.Net.WebUtility]::HtmlEncode($Text)
}

function Get-LogTail {
    param([string]$Path, [int]$Lines = 20)
    if (Test-Path $Path) {
        $content = Get-Content -Path $Path -Tail $Lines -ErrorAction SilentlyContinue
        if ($content) {
            return (HtmlEncode ($content -join "`n"))
        }
    }
    return '(no output captured yet)'
}

function Resolve-Tool {
    param([string[]]$Names)
    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd }
    }
    return $null
}

function Test-HttpOk {
    param([string]$Url, [int]$TimeoutSec = 2)
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400)
    } catch {
        return $false
    }
}

# Runs a native command and writes its output to a log file as plain text.
#
# Deliberately not using `*> $log` / `2>&1 > $log` here: PowerShell captures
# a native command's stderr lines as ErrorRecord objects, and when those get
# written to a file it renders each one as a multi-line block ("uv.exe :
# <message>" followed by "At run.ps1:NNN ... CategoryInfo ...
# FullyQualifiedErrorId : NativeCommandError"). uv and alembic both write
# their normal progress output to stderr, so every log ended up dominated by
# that boilerplate even on success - which also buries genuine errors,
# making them look like more of the same noise instead of standing out.
# Pulling `.Exception.Message` out of each ErrorRecord gives the real line
# uv/alembic actually printed, same as running it directly in a terminal.
function Invoke-Logged {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$LogFile
    )

    $rawOutput = & $FilePath @ArgumentList 2>&1
    $exitCode = $LASTEXITCODE

    $lines = $rawOutput | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            $_.Exception.Message
        } else {
            $_.ToString()
        }
    }
    Set-Content -Path $LogFile -Value $lines -Encoding UTF8

    return $exitCode
}

# A corrupted/truncated .venv entry-point stub (e.g. a partially-written
# alembic.exe - typically from antivirus real-time scanning locking a
# freshly-created .exe mid-write, or the previous backend process still
# holding files open because it was force-killed rather than stopped
# cleanly) fails with this exact, unambiguous signature: something tried to
# read the compiled .exe as Python source and hit its binary header.
# Deliberately narrow so this can never mask an unrelated real failure -
# only this precise text triggers the one-time rebuild-and-retry below.
function Test-CorruptedVenvSignature {
    param([string]$LogFile)
    if (-not (Test-Path $LogFile)) { return $false }
    $content = Get-Content -Path $LogFile -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $false }
    return ($content -match 'cannot contain null bytes')
}

# backend/.venv and frontend/node_modules both nest deep enough that a repo
# cloned into an already-long path (nested OneDrive/Documents folders, etc.)
# can hit Windows' legacy 260-character path limit during install. When it
# happens, uv/npm surface it as a raw, cryptic line buried in the log tail -
# this just recognizes that line and adds a plain-language explanation
# rather than leaving the user to decode a Win32 error code on their own.
function Test-LongPathSignature {
    param([string]$LogFile)
    if (-not (Test-Path $LogFile)) { return $false }
    $content = Get-Content -Path $LogFile -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $false }
    return ($content -match 'ENAMETOOLONG' -or $content -match 'PathTooLongException' -or `
            $content -match 'The specified path, file name, or both are too long' -or `
            $content -match 'path too long')
}

function Get-LongPathHint {
    return '<p><strong>This may be a Windows path-length limit.</strong> If Praxis is cloned somewhere deeply nested (e.g. inside several layers of OneDrive or Documents folders), try moving the whole folder somewhere shorter, like <code>C:\Praxis</code>, and run <code>run.bat</code> again.</p>'
}

# Writes logs\praxis-status.html. This is the only feedback mechanism the
# user sees while everything is hidden, so every exit path (success,
# missing prerequisite, failed install, timeout, unexpected error) routes
# through here with a plain-language message.
function Set-StatusPage {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('working', 'ready', 'error')]
        [string]$State,
        [string]$Heading = '',
        [string]$Body = '',
        [string]$RedirectUrl = ''
    )

    $refreshTag = ''
    if ($State -eq 'working') {
        $refreshTag = '<meta http-equiv="refresh" content="2">'
    } elseif ($State -eq 'ready' -and $RedirectUrl) {
        $refreshTag = '<meta http-equiv="refresh" content="0;url=' + $RedirectUrl + '">'
    }

    # Single-quoted here-string on purpose: the body of this template is
    # never interpolated by PowerShell, so nothing in it (CSS braces, `$`,
    # backticks) can accidentally break the script. Values are substituted
    # afterwards with plain .Replace() calls.
    $template = @'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
__REFRESH__
<title>Praxis</title>
<style>
  /* Colors match frontend/tailwind.config.js exactly, so this page looks
     like part of the app rather than a generic browser popup. */
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
         background:#262624; color:#E8E6DC;
         display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }
  .card { max-width:520px; padding:32px 36px; border-radius:12px; background:#30302E;
          border:1px solid #3C3B37; box-shadow:0 4px 24px rgba(0,0,0,0.35); text-align:center; }
  h1 { font-size:20px; margin:0 0 12px; color:#E8E6DC; }
  p { font-size:14px; line-height:1.6; color:#ACA99F; margin:6px 0; text-align:left; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#E0825A;
         margin-right:6px; animation:pulse 1.2s infinite ease-in-out; }
  @keyframes pulse { 0% { opacity:0.3 } 50% { opacity:1 } 100% { opacity:0.3 } }
  code { background:#262624; border:1px solid #3C3B37; color:#F0997B; padding:1px 6px; border-radius:4px; font-size:12px; }
  pre { text-align:left; background:#262624; border:1px solid #3C3B37; color:#ACA99F; padding:10px 12px;
        border-radius:8px; font-size:11px; white-space:pre-wrap; word-break:break-word; max-height:220px; overflow:auto; }
  .state-error h1 { color:#EDA37E; }
</style>
</head>
<body>
  <div class="card __STATECLASS__">
    <h1>__HEADING__</h1>
    __BODY__
  </div>
</body>
</html>
'@

    $html = $template.Replace('__REFRESH__', $refreshTag)
    $html = $html.Replace('__STATECLASS__', ('state-' + $State))
    $html = $html.Replace('__HEADING__', $Heading)
    $html = $html.Replace('__BODY__', $Body)

    Set-Content -Path $StatusPage -Value $html -Encoding UTF8
}

function Open-StatusPage {
    Start-Process -FilePath $StatusPage | Out-Null
}

# Kills a process (and its children, e.g. npm.cmd -> node.exe) tracked via
# a PID file written when it was started. taskkill /T handles the
# uv -> uvicorn / npm -> node parent-child relationship in one shot.
#
# ExpectedNames guards against PID reuse: PID files can outlive the process
# they named (deleted, crashed, or the machine rebooted and Windows recycled
# the number for something unrelated). Before killing anything, the process
# currently holding that PID is checked against the name(s) we'd expect to
# have started (e.g. 'uv' for the backend, 'cmd' for the frontend, since
# that's what Start-Process actually launched). A mismatch means the PID
# file is stale and pointing at an unrelated process, so it's left alone.
function Stop-TrackedProcess {
    param([string]$PidFile, [string]$Label, [string[]]$ExpectedNames = @())

    if (-not (Test-Path $PidFile)) {
        return $false
    }

    $trackedId = Get-Content -Path $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue

    if ([string]::IsNullOrWhiteSpace($trackedId)) {
        return $false
    }

    $proc = Get-Process -Id $trackedId -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Log "$Label (PID $trackedId) was not running."
        return $false
    }

    if ($ExpectedNames.Count -gt 0 -and ($ExpectedNames -notcontains $proc.ProcessName)) {
        Write-Log "$Label (PID $trackedId) is now process '$($proc.ProcessName)', not one of [$($ExpectedNames -join ', ')] - PID was reused, leaving it alone."
        return $false
    }

    & taskkill /PID $trackedId /T /F 2>$null | Out-Null
    Write-Log "Stopped $Label (PID $trackedId)."
    return $true
}

# ---------------------------------------------------------------------------
# Stop action
# ---------------------------------------------------------------------------

if ($Action -eq 'Stop') {
    Write-Log '--- Stop requested ---'
    $stoppedBackend = Stop-TrackedProcess -PidFile $BackendPidFile -Label 'backend' -ExpectedNames @('uv')
    $stoppedFrontend = Stop-TrackedProcess -PidFile $FrontendPidFile -Label 'frontend' -ExpectedNames @('cmd')
    if (-not $stoppedBackend -and -not $stoppedFrontend) {
        Write-Log 'Nothing was running.'
    }
    exit 0
}

# ---------------------------------------------------------------------------
# Start action
# ---------------------------------------------------------------------------

# Single-instance guard: a named, machine-wide mutex so two near-simultaneous
# launches (double-click twice, or a launch while one is still starting up)
# can't both fall through the "already healthy?" check below and each start
# their own backend/frontend against the same ports. The second launcher
# just waits briefly for the first to finish starting, then re-checks health
# and reopens the browser instead of starting a duplicate set of servers.
$launchMutex = New-Object System.Threading.Mutex($false, 'Global\PraxisLauncherSingleInstance')
$ownsMutex = $false
try {
    $ownsMutex = $launchMutex.WaitOne(0)
} catch [System.Threading.AbandonedMutexException] {
    # A previous launcher crashed while holding it - the mutex is still
    # valid and now ours; treat it the same as a clean acquire.
    $ownsMutex = $true
}

if (-not $ownsMutex) {
    Write-Log 'Another launch is already in progress - waiting for it instead of starting a second one.'
    try {
        $ownsMutex = $launchMutex.WaitOne(120000)
    } catch [System.Threading.AbandonedMutexException] {
        $ownsMutex = $true
    }
    if ((Test-HttpOk $HealthUrl) -and (Test-HttpOk $FrontendUrl)) {
        Write-Log 'Other launch finished successfully - opening browser.'
        Start-Process -FilePath $FrontendUrl | Out-Null
        if ($ownsMutex) { $launchMutex.ReleaseMutex() | Out-Null }
        exit 0
    }
    if (-not $ownsMutex) {
        Write-Log 'Timed out waiting for the other launch to finish.'
        Set-StatusPage -State 'error' -Heading 'Praxis is already starting' -Body (
            '<p>Another Praxis launch appears to be stuck. Run <code>scripts\stop.bat</code>, then try again.</p>'
        )
        exit 1
    }
    # We now own the mutex but the other launch didn't leave things healthy
    # (crashed, or genuinely failed) - fall through and start fresh below.
}

try {
    Write-Log '--- Praxis launcher starting ---'

    # Already running (e.g. double-clicked again)? Just reopen the app.
    if ((Test-HttpOk $HealthUrl) -and (Test-HttpOk $FrontendUrl)) {
        Write-Log 'Already running - opening browser.'
        Start-Process -FilePath $FrontendUrl | Out-Null
        exit 0
    }

    # Not (fully) healthy, and we hold the single-instance lock, so any
    # leftover tracked backend/frontend from a previous unclean shutdown
    # (crash, killed frontend but not backend, etc.) is stale. Clear it out
    # now, before starting anything new, so the PID files always describe
    # the process this run actually started - never a stray orphan.
    Stop-TrackedProcess -PidFile $BackendPidFile -Label 'stale backend' -ExpectedNames @('uv') | Out-Null
    Stop-TrackedProcess -PidFile $FrontendPidFile -Label 'stale frontend' -ExpectedNames @('cmd') | Out-Null

    # Show the "starting up" page immediately so there is no dead silence
    # while dependencies install on a first run.
    Set-StatusPage -State 'working' -Heading 'Starting Praxis...' -Body (
        '<p><span class="dot"></span>Just a moment - this page will switch to the app on its own.</p>' +
        '<p>Usually a few seconds. Occasionally longer. No need to do anything, just wait.</p>'
    )
    Open-StatusPage

    if (-not (Test-Path (Join-Path $BackendDir 'pyproject.toml'))) {
        Write-Log 'FAILED: backend\pyproject.toml not found - repo layout looks wrong.'
        Set-StatusPage -State 'error' -Heading 'Praxis could not start' -Body (
            '<p>Expected to find <code>backend\pyproject.toml</code> under <code>' + (HtmlEncode $RepoRoot) + '</code>.</p>' +
            '<p>Make sure this script still lives at <code>scripts\run.bat</code> inside the Praxis folder, and that nothing was moved or renamed.</p>'
        )
        exit 1
    }
    if (-not (Test-Path (Join-Path $FrontendDir 'package.json'))) {
        Write-Log 'FAILED: frontend\package.json not found - repo layout looks wrong.'
        Set-StatusPage -State 'error' -Heading 'Praxis could not start' -Body (
            '<p>Expected to find <code>frontend\package.json</code> but it is missing.</p>'
        )
        exit 1
    }

    $uv = Resolve-Tool -Names @('uv')
    $node = Resolve-Tool -Names @('node')
    $npm = Resolve-Tool -Names @('npm.cmd', 'npm')

    if (-not $uv) {
        Write-Log 'FAILED: uv not found on PATH.'
        Set-StatusPage -State 'error' -Heading 'Missing requirement: uv' -Body (
            '<p><code>uv</code> was not found on this system.</p>' +
            '<p>Install it from <code>https://github.com/astral-sh/uv</code>, then double-click run.bat again.</p>'
        )
        exit 1
    }
    if (-not $node -or -not $npm) {
        Write-Log 'FAILED: Node.js/npm not found on PATH.'
        Set-StatusPage -State 'error' -Heading 'Missing requirement: Node.js' -Body (
            '<p>Node.js (and npm) was not found on this system.</p>' +
            '<p>Install it from <code>https://nodejs.org/</code>, then double-click run.bat again.</p>'
        )
        exit 1
    }

    # --- Backend dependencies + migrations ---
    # Runs at most twice: if either step fails with the exact "corrupted
    # .venv entry-point" signature (see Test-CorruptedVenvSignature), the
    # .venv is rebuilt from scratch once and the same two steps are retried.
    # Any other kind of failure exits immediately on the first attempt -
    # this never masks a real error, it only recovers from one specific,
    # unambiguous local-environment corruption pattern.
    $backendSetupLog = Join-Path $LogsDir 'setup-backend.log'
    $migrateLog = Join-Path $LogsDir 'migrate.log'
    $venvRebuilt = $false
    $backendReady2 = $false

    for ($attemptNum = 1; $attemptNum -le 2; $attemptNum++) {
        Write-Log 'Running uv sync...'
        Push-Location $BackendDir
        try {
            $uvSyncExit = Invoke-Logged -FilePath $uv.Source -ArgumentList @('sync') -LogFile $backendSetupLog
        } finally {
            Pop-Location
        }

        if ($uvSyncExit -ne 0) {
            if (-not $venvRebuilt -and (Test-CorruptedVenvSignature $backendSetupLog)) {
                Write-Log 'uv sync hit a corrupted .venv entry-point stub - rebuilding .venv and retrying once.'
                Remove-Item -Path (Join-Path $BackendDir '.venv') -Recurse -Force -ErrorAction SilentlyContinue
                $venvRebuilt = $true
                continue
            }
            Write-Log "FAILED: uv sync exited with code $uvSyncExit. See $backendSetupLog"
            $hint = if (Test-LongPathSignature $backendSetupLog) { Get-LongPathHint } else { '' }
            Set-StatusPage -State 'error' -Heading 'Backend setup failed' -Body (
                '<p><code>uv sync</code> failed. Last lines of the log:</p>' +
                '<pre>' + (Get-LogTail $backendSetupLog 25) + '</pre>' +
                $hint +
                '<p>Full log: <code>' + (HtmlEncode $backendSetupLog) + '</code></p>'
            )
            exit 1
        }

        Write-Log 'Running alembic upgrade head...'
        Push-Location $BackendDir
        try {
            $migrateExit = Invoke-Logged -FilePath $uv.Source -ArgumentList @('run', 'alembic', 'upgrade', 'head') -LogFile $migrateLog
        } finally {
            Pop-Location
        }

        if ($migrateExit -ne 0) {
            if (-not $venvRebuilt -and (Test-CorruptedVenvSignature $migrateLog)) {
                Write-Log 'alembic hit a corrupted .venv entry-point stub - rebuilding .venv and retrying once.'
                Remove-Item -Path (Join-Path $BackendDir '.venv') -Recurse -Force -ErrorAction SilentlyContinue
                $venvRebuilt = $true
                continue
            }
            Write-Log "FAILED: alembic upgrade head exited with code $migrateExit. See $migrateLog"
            $hint = if (Test-LongPathSignature $migrateLog) { Get-LongPathHint } else { '' }
            Set-StatusPage -State 'error' -Heading 'Database migration failed' -Body (
                '<p><code>alembic upgrade head</code> failed. Last lines of the log:</p>' +
                '<pre>' + (Get-LogTail $migrateLog 25) + '</pre>' +
                $hint +
                '<p>Full log: <code>' + (HtmlEncode $migrateLog) + '</code></p>'
            )
            exit 1
        }

        $backendReady2 = $true
        break
    }

    if (-not $backendReady2) {
        # Both attempts failed and the second one was not a clean success -
        # the loop above already wrote a status page and exited for every
        # normal failure path, so reaching here means the retry itself was
        # exhausted without success. Guard clause for safety.
        Write-Log 'FAILED: backend setup did not succeed after retry.'
        Set-StatusPage -State 'error' -Heading 'Backend setup failed' -Body (
            '<p>Backend setup did not succeed even after rebuilding <code>.venv</code>.</p>' +
            '<p>Logs: <code>' + (HtmlEncode $backendSetupLog) + '</code> and <code>' + (HtmlEncode $migrateLog) + '</code></p>'
        )
        exit 1
    }

    # --- Frontend dependencies ---
    # A bare "does node_modules exist" check is not enough: it says nothing
    # about whether that folder actually matches the current
    # package-lock.json. That mismatch is exactly what happens after a
    # `git pull` that adds/bumps a dependency, or (previously) on a fresh
    # clone of this repo, since frontend/node_modules used to be committed
    # and could silently drift out of sync with package.json. Skipping
    # `npm install` in that case leaves a partially-installed app that
    # fails confusingly deep inside Vite instead of here, with a clear
    # message.
    #
    # So: install whenever node_modules is missing, OR whenever the hash of
    # package-lock.json has changed since the last successful install. The
    # hash is cached in node_modules\.install-stamp, written only after
    # `npm install` succeeds, so a failed/interrupted install is correctly
    # retried next run instead of being treated as done.
    $frontendNodeModules = Join-Path $FrontendDir 'node_modules'
    $packageLockPath = Join-Path $FrontendDir 'package-lock.json'
    $installStampPath = Join-Path $frontendNodeModules '.install-stamp'

    $currentLockHash = $null
    if (Test-Path $packageLockPath) {
        $currentLockHash = (Get-FileHash -Path $packageLockPath -Algorithm SHA256).Hash
    }

    $needsInstall = $true
    if ((Test-Path $frontendNodeModules) -and (Test-Path $installStampPath) -and $currentLockHash) {
        $stampHash = (Get-Content -Path $installStampPath -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($stampHash -eq $currentLockHash) {
            $needsInstall = $false
        }
    }

    if ($needsInstall) {
        Write-Log 'Running npm install...'
        $frontendSetupLog = Join-Path $LogsDir 'setup-frontend.log'
        Push-Location $FrontendDir
        try {
            $npmInstallExit = Invoke-Logged -FilePath $npm.Source -ArgumentList @('install') -LogFile $frontendSetupLog
        } finally {
            Pop-Location
        }
        if ($npmInstallExit -ne 0) {
            Write-Log "FAILED: npm install exited with code $npmInstallExit. See $frontendSetupLog"
            $hint = if (Test-LongPathSignature $frontendSetupLog) { Get-LongPathHint } else { '' }
            Set-StatusPage -State 'error' -Heading 'Frontend setup failed' -Body (
                '<p><code>npm install</code> failed. Last lines of the log:</p>' +
                '<pre>' + (Get-LogTail $frontendSetupLog 25) + '</pre>' +
                $hint +
                '<p>Full log: <code>' + (HtmlEncode $frontendSetupLog) + '</code></p>'
            )
            exit 1
        }
        if ($currentLockHash) {
            Set-Content -Path $installStampPath -Value $currentLockHash -Encoding ascii
        }
    }

    # --- Start backend (hidden, detached, survives this script exiting) ---
    Write-Log 'Starting backend (uvicorn)...'
    $backendOut = Join-Path $LogsDir 'backend.out.log'
    $backendErr = Join-Path $LogsDir 'backend.err.log'
    $backendProc = Start-Process -FilePath $uv.Source `
        -ArgumentList @('run', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') `
        -WorkingDirectory $BackendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -PassThru
    Set-Content -Path $BackendPidFile -Value $backendProc.Id -Encoding ascii

    # --- Start frontend (hidden, detached) ---
    # npm on Windows is npm.cmd, not a real .exe. Launching a .cmd directly
    # via Start-Process with output redirection is unreliable (it needs a
    # true PE executable), so it is routed through cmd.exe /c instead -
    # cmd.exe resolves npm.cmd normally, and taskkill /T later still cleans
    # up the resulting node.exe child correctly. uv is a real executable
    # and does not need this.
    Write-Log 'Starting frontend (vite)...'
    $frontendOut = Join-Path $LogsDir 'frontend.out.log'
    $frontendErr = Join-Path $LogsDir 'frontend.err.log'
    $frontendProc = Start-Process -FilePath 'cmd.exe' `
        -ArgumentList @('/c', 'npm', 'run', 'dev') `
        -WorkingDirectory $FrontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr `
        -PassThru
    Set-Content -Path $FrontendPidFile -Value $frontendProc.Id -Encoding ascii

    # --- Wait for both to report healthy ---
    Write-Log 'Waiting for backend and frontend to become healthy...'
    $maxAttempts = 90
    $attempt = 0
    $backendReady = $false
    $frontendReady = $false

    while ($attempt -lt $maxAttempts -and (-not $backendReady -or -not $frontendReady)) {
        Start-Sleep -Seconds 2
        $attempt++
        if (-not $backendReady) { $backendReady = Test-HttpOk $HealthUrl }
        if (-not $frontendReady) { $frontendReady = Test-HttpOk $FrontendUrl }
    }

    if ($backendReady -and $frontendReady) {
        Write-Log 'Both servers ready.'
        Set-StatusPage -State 'ready' -Heading 'Praxis is ready' -Body '<p>Opening the app...</p>' -RedirectUrl $FrontendUrl
        exit 0
    }

    Write-Log ('Timed out waiting for servers. backend={0} frontend={1}' -f $backendReady, $frontendReady)
    $bodyParts = New-Object System.Collections.Generic.List[string]
    if (-not $backendReady) {
        $bodyParts.Add('<p><strong>Backend</strong> never responded on <code>' + (HtmlEncode $HealthUrl) + '</code>.</p>')
        $bodyParts.Add('<pre>' + (Get-LogTail $backendErr 20) + '</pre>')
    }
    if (-not $frontendReady) {
        $bodyParts.Add('<p><strong>Frontend</strong> never responded on <code>' + (HtmlEncode $FrontendUrl) + '</code>.</p>')
        $bodyParts.Add('<pre>' + (Get-LogTail $frontendErr 20) + '</pre>')
        # With strictPort set in vite.config.ts, a "port already in use" fatal
        # error is expected to land in frontend.err.log above - but Vite's
        # own port-selection messages go to stdout, so that is surfaced too
        # in case anything relevant landed there instead.
        $frontendOutTail = Get-LogTail $frontendOut 10
        if ($frontendOutTail -and $frontendOutTail.Trim()) {
            $bodyParts.Add('<pre>' + $frontendOutTail + '</pre>')
        }
    }
    $bodyParts.Add('<p>Full logs are in <code>' + (HtmlEncode $LogsDir) + '</code>. Run <code>scripts\stop.bat</code> before trying again.</p>')
    Set-StatusPage -State 'error' -Heading 'Praxis is taking too long to start' -Body ($bodyParts -join "`n")
    exit 1
}
catch {
    $errorMessage = $_.Exception.Message
    Write-Log ('FATAL: ' + $errorMessage)
    try {
        Set-StatusPage -State 'error' -Heading 'Praxis hit an unexpected error' -Body (
            '<p>' + (HtmlEncode $errorMessage) + '</p>' +
            '<p>Details were written to <code>' + (HtmlEncode $LauncherLog) + '</code>.</p>'
        )
    } catch {
        # If even writing the status page fails, there is nothing more we
        # can surface to the user without a console - the log file is the
        # last resort at that point.
    }
    exit 1
}
