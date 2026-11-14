<#
.SYNOPSIS
  One entry point for Windows (PowerShell or cmd). Use run.cmd to avoid execution-policy prompts.

.EXAMPLE
  .\run.cmd setup              # check tools, create .env, Python venv, npm install
  .\run.cmd up                 # start the app with Docker Compose -> http://localhost:3000
  .\run.cmd test               # backend + AI + frontend tests
  .\run.cmd pipeline simulate  # any scripts/pipeline.sh stage, run through Git Bash (not WSL)
  .\run.cmd bash scripts/tf.sh local validate   # any repo script through Git Bash
  .\run.cmd down               # stop the app
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)][string]$Command = "help",
  [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest = @()
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Info($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "[ ok ] $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "[fail] $msg" -ForegroundColor Red; exit 1 }

function Find-GitBash {
  # `bash` on PATH is often the WSL launcher (fails without a Linux distro) - always use Git Bash.
  $candidates = @()
  $git = Get-Command git -ErrorAction SilentlyContinue
  if ($git) { $candidates += (Join-Path (Split-Path (Split-Path $git.Source)) "bin\bash.exe") }
  $candidates += "$env:ProgramFiles\Git\bin\bash.exe", "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
                 "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
  foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
  Fail "Git Bash not found. Install Git for Windows: https://git-scm.com/download/win"
}

function Invoke-Native([string]$exe, [string[]]$arguments) {
  & $exe @arguments
  if ($LASTEXITCODE -ne 0) { Fail "$exe $($arguments -join ' ') exited with $LASTEXITCODE" }
}

function Get-Python {
  foreach ($name in "py", "python") {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notmatch "WindowsApps") { return $name }
  }
  Fail "Python 3.11+ not found. Install from https://www.python.org/downloads/ (tick 'Add to PATH')."
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

switch ($Command) {
  "setup" {
    Info "Checking prerequisites"
    foreach ($tool in "git", "docker", "node", "npm") {
      if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail "'$tool' is not installed (see README section 5)" }
    }
    docker info --format "{{.ServerVersion}}" *> $null
    if ($LASTEXITCODE -ne 0) { Fail "Docker is installed but not running - start Docker Desktop" }
    $bash = Find-GitBash
    Ok "git, docker, node, npm, Git Bash ($bash)"

    if (-not (Test-Path .env)) { Copy-Item .env.example .env; Ok "created .env from .env.example (local-only defaults)" }
    else { Ok ".env already exists" }

    if (-not (Test-Path $VenvPython)) {
      Info "Creating Python virtual environment (.venv)"
      $py = Get-Python
      if ($py -eq "py") { Invoke-Native py @("-3", "-m", "venv", ".venv") } else { Invoke-Native python @("-m", "venv", ".venv") }
    }
    Info "Installing Python dependencies"
    Invoke-Native $VenvPython @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
    Invoke-Native $VenvPython @("-m", "pip", "install", "--quiet", "--timeout", "120",
      "-r", "backend/requirements-dev.txt", "-r", "ai/requirements-dev.txt")
    Ok "Python dependencies installed"

    Info "Installing frontend dependencies (npm ci)"
    Push-Location frontend
    try { Invoke-Native npm @("ci", "--no-audit", "--no-fund") } finally { Pop-Location }
    Ok "setup complete - next: .\run.cmd up"
  }

  "up" {
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
    Info "Starting postgres, backend and frontend (first run builds the images)"
    Invoke-Native docker @("compose", "up", "-d", "--build", "--wait")
    Ok "Idea Board:  http://localhost:3000"
    Ok "Pipelines:   http://localhost:3000/pipelines"
    Ok "API docs:    http://localhost:8000/docs"
  }

  "down" { Invoke-Native docker @("compose", "down") }

  "test" {
    if (-not (Test-Path $VenvPython)) { Fail "run .\run.cmd setup first" }
    Info "Backend tests";  Push-Location backend;  try { Invoke-Native $VenvPython @("-m", "pytest") } finally { Pop-Location }
    Info "AI tooling tests"; Push-Location ai;    try { Invoke-Native $VenvPython @("-m", "pytest") } finally { Pop-Location }
    Info "Frontend lint, unit tests and build"
    Push-Location frontend
    try { Invoke-Native npm @("run", "lint"); Invoke-Native npm @("test"); Invoke-Native npm @("run", "build") } finally { Pop-Location }
    Ok "all tests passed"
  }

  "pipeline" {
    $bash = Find-GitBash
    & $bash scripts/pipeline.sh @Rest
    exit $LASTEXITCODE
  }

  "bash" {
    $bash = Find-GitBash
    & $bash @Rest
    exit $LASTEXITCODE
  }

  default {
    Write-Host @"
Usage: .\run.cmd <command>

  setup                 check tools, create .env, .venv (Python deps) and node_modules
  up                    start the app (Docker Compose)  -> http://localhost:3000
  down                  stop the app
  test                  backend + AI + frontend tests
  pipeline [stage]      run scripts/pipeline.sh through Git Bash, e.g. 'pipeline simulate', 'pipeline lint-test'
  bash <script> [args]  run any repo script through Git Bash, e.g. 'bash scripts/tf.sh local validate'
"@
    exit 0
  }
}
