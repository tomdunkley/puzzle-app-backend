# Builds the Lambda deployment package without Docker.
#
# `sam build` without --use-container installs dependencies using the local
# interpreter, which on this Windows machine would fetch win_amd64 wheels --
# incompatible with the Lambda Linux runtime. Instead we pip-install straight
# from PyPI targeting manylinux/cp312 wheels into ./.build, then copy the app
# source alongside them. `sam build` is left with nothing to do but copy this
# folder verbatim (no requirements.txt lives inside .build itself).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$buildDir = Join-Path $root ".build"

Remove-Item -Recurse -Force $buildDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $buildDir | Out-Null

& (Join-Path $root ".venv\Scripts\python.exe") -m pip install `
    -r (Join-Path $root "requirements.txt") `
    --platform manylinux2014_x86_64 `
    --implementation cp `
    --python-version 3.12 `
    --only-binary=:all: `
    --target $buildDir `
    --no-user

Copy-Item -Recurse (Join-Path $root "app") $buildDir

Write-Host "Built Lambda package at $buildDir"
