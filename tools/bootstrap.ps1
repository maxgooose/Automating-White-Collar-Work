# ============================================================
# Finale Inventory Automation - environment bootstrap
#
# Called by start.bat before the server launches. Idempotent.
#   1. Find a working Python (repairing the common "Python not found"
#      cases: Microsoft Store stub on PATH, PATH not set), installing
#      Python 3.12 silently if the machine has none.
#   2. Find the Tesseract OCR engine, installing it silently if missing
#      (needed by the Receive duplicate-skip feature).
#   3. Install/upgrade pip dependencies when requirements.txt changes.
#   4. Write the resolved Python path to .python_path for start.bat.
#
# Runs under Windows PowerShell 5.1 (preinstalled everywhere), so keep
# the syntax 5.1-compatible.
# ============================================================
$ErrorActionPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072  # enable TLS 1.2 on PS 5.1

$ProjectRoot = Split-Path -Parent $PSScriptRoot   # tools\ -> project root
$PythonPathFile = Join-Path $ProjectRoot '.python_path'
$RequirementsFile = Join-Path $ProjectRoot 'requirements.txt'
$DepsMarkerFile = Join-Path $ProjectRoot '.deps_installed'

function Write-Step($msg) { Write-Host "[bootstrap] $msg" }

# ------------------------------------------------------------
# 1. Python
# ------------------------------------------------------------

function Test-PythonExe($exe) {
    # True only if $exe is a real, working Python 3.9+ (rejects the
    # Microsoft Store stub, which exits non-zero / prints a Store hint).
    if (-not $exe) { return $false }
    if ($exe -like '*\WindowsApps\*') { return $false }
    if (-not (Test-Path $exe)) { return $false }
    try {
        $out = & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $false }
        $parts = "$out".Trim().Split('.')
        $major = [int]$parts[0]; $minor = [int]$parts[1]
        if ($major -lt 3) { return $false }
        if ($major -eq 3 -and $minor -lt 9) { return $false }
        return $true
    } catch {
        return $false
    }
}

function Find-PythonInDirs {
    # Scan standard install dirs, newest version first.
    $roots = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
        'C:\',
        'C:\Program Files'
    )
    $candidates = @()
    foreach ($root in $roots) {
        if (Test-Path $root) {
            $dirs = Get-ChildItem -Path $root -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue
            foreach ($d in $dirs) {
                $num = 0
                if ($d.Name -match 'Python(\d+)') { $num = [int]$Matches[1] }
                $candidates += New-Object psobject -Property @{
                    Exe = (Join-Path $d.FullName 'python.exe'); Ver = $num
                }
            }
        }
    }
    foreach ($c in ($candidates | Sort-Object Ver -Descending)) {
        if (Test-PythonExe $c.Exe) { return $c.Exe }
    }
    return $null
}

function Resolve-Python {
    # a) project venv (existing deployments)
    $venvPy = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
    if (Test-PythonExe $venvPy) {
        Write-Step "Using project venv Python: $venvPy"
        return $venvPy
    }

    # b) py launcher (works even when python.exe is not on PATH)
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $exe = (& py -3 -c "import sys; print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $exe) {
                $exe = "$exe".Trim()
                if (Test-PythonExe $exe) {
                    Write-Step "Using Python via py launcher: $exe"
                    return $exe
                }
            }
        } catch { }
    }

    # c) python on PATH (verified; Store stub is rejected by Test-PythonExe)
    $onPath = Get-Command python -ErrorAction SilentlyContinue
    if ($onPath) {
        if (Test-PythonExe $onPath.Source) {
            Write-Step "Using Python from PATH: $($onPath.Source)"
            return $onPath.Source
        }
        Write-Step "NOTE: 'python' on PATH is not usable (Microsoft Store stub or broken install) - looking elsewhere."
    }

    # d) standard install dirs (installed but never added to PATH)
    $found = Find-PythonInDirs
    if ($found) {
        Write-Step "Using Python found on disk: $found"
        return $found
    }

    # e) nothing on the machine -> install silently
    Write-Step 'Python not found. Installing Python 3.12 (one-time, ~2 min)...'
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    }
    $found = Find-PythonInDirs
    if ($found) {
        Write-Step "Python installed: $found"
        return $found
    }

    # f) winget missing or failed -> python.org installer (per-user, no admin)
    Write-Step 'Downloading Python installer from python.org...'
    $url = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'
    $tmp = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
    try {
        Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
        Write-Step 'Running silent install (per-user)...'
        Start-Process -FilePath $tmp -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1' -Wait
    } catch {
        Write-Step "ERROR: Python download/install failed: $_"
    }
    $found = Find-PythonInDirs
    if ($found) {
        Write-Step "Python installed: $found"
        return $found
    }
    return $null
}

# ------------------------------------------------------------
# 2. Tesseract OCR engine
# ------------------------------------------------------------

function Find-Tesseract {
    if ($env:TESSERACT_CMD -and (Test-Path $env:TESSERACT_CMD)) { return $env:TESSERACT_CMD }
    $cmd = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $dirs = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Tesseract-OCR'),
        'C:\Program Files\Tesseract-OCR',
        'C:\Program Files (x86)\Tesseract-OCR'
    )
    foreach ($d in $dirs) {
        $exe = Join-Path $d 'tesseract.exe'
        if (Test-Path $exe) { return $exe }
    }
    return $null
}

function Ensure-Tesseract {
    $found = Find-Tesseract
    if ($found) {
        Write-Step "Tesseract OCR: $found"
        return
    }

    Write-Step 'Tesseract OCR not found. Installing (needed to auto-skip duplicate barcodes)...'
    Write-Step '(If a User Account Control prompt appears, click Yes.)'
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    }
    $found = Find-Tesseract
    if (-not $found) {
        # winget missing or failed -> direct download of the UB-Mannheim installer
        $url = 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe'
        $tmp = Join-Path $env:TEMP 'tesseract-setup.exe'
        try {
            Write-Step 'Downloading Tesseract installer...'
            Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
            Start-Process -FilePath $tmp -ArgumentList '/S' -Wait
        } catch {
            Write-Step "Tesseract download/install failed: $_"
        }
        $found = Find-Tesseract
    }

    if ($found) {
        Write-Step "Tesseract OCR installed: $found"
    } else {
        Write-Step 'WARNING: Tesseract could not be installed. The app still works,'
        Write-Step '         but duplicate barcodes will STOP a Receive run instead of'
        Write-Step '         being skipped. Install manually: https://github.com/UB-Mannheim/tesseract/wiki'
    }
}

# ------------------------------------------------------------
# 3. pip dependencies (re-run whenever requirements.txt changes)
# ------------------------------------------------------------

function Ensure-Dependencies($py) {
    $hash = (Get-FileHash -Path $RequirementsFile -Algorithm SHA256).Hash
    $stored = ''
    if (Test-Path $DepsMarkerFile) {
        $stored = (Get-Content $DepsMarkerFile -Raw -ErrorAction SilentlyContinue)
        if ($stored) { $stored = $stored.Trim() }
    }
    if ($stored -eq $hash) {
        Write-Step 'Dependencies up to date.'
        return $true
    }

    Write-Step 'Installing Python dependencies...'
    & $py -m pip install -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) {
        if ($py -like '*\venv\*') {
            Write-Step 'ERROR: pip install failed inside venv.'
            return $false
        }
        Write-Step 'Retrying with --user...'
        & $py -m pip install --user -r $RequirementsFile
        if ($LASTEXITCODE -ne 0) {
            Write-Step 'ERROR: pip install failed.'
            return $false
        }
    }
    Set-Content -Path $DepsMarkerFile -Value $hash -Encoding Ascii
    Write-Step 'Dependencies installed.'
    return $true
}

# ------------------------------------------------------------
# Run
# ------------------------------------------------------------

$python = Resolve-Python
if (-not $python) {
    Write-Step 'ERROR: No working Python and automatic install failed.'
    Write-Step 'Install Python 3.12 manually from https://www.python.org/downloads/'
    Write-Step '(check "Add Python to PATH"), then run start.bat again.'
    exit 1
}

Ensure-Tesseract

if (-not (Ensure-Dependencies $python)) {
    exit 1
}

# Hand the resolved interpreter to start.bat. ANSI ("Default") encoding so
# cmd's `set /p` reads the path correctly.
Set-Content -Path $PythonPathFile -Value $python -Encoding Default -NoNewline

Write-Step 'Environment ready.'
exit 0
