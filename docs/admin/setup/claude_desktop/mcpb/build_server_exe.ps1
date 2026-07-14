<#
    Rebuilds server/server.exe — the self-contained (frozen) IMDR MCP server
    bundled into imdr-db.mcpb for firm-wide Claude Desktop distribution.

    Produces a single ~27 MB Windows x64 executable with Python + mcp +
    sqlalchemy + pyodbc frozen in, so target machines need NO Python install.

    Requirements on the BUILD machine only:
      - Python 3.11+ on PATH (any interpreter; the frozen exe is self-contained)
      - Internet access to install build deps into a throwaway venv

    Usage (from this directory):
      powershell -ExecutionPolicy Bypass -File .\build_server_exe.ps1

    After building, repackage the bundle:
      python -c "import zipfile; z=zipfile.ZipFile('imdr-db.mcpb','w',zipfile.ZIP_DEFLATED); [z.write(f,f) for f in ['manifest.json','README.md','server/server.exe']]; z.close()"
#>
$ErrorActionPreference = "Stop"
$here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv  = Join-Path $env:TEMP "imdr_mcpb_build_venv"
$work  = Join-Path $env:TEMP "imdr_mcpb_build_work"
$src   = Join-Path $here "server\server.py"

Write-Host "== Creating clean build venv ==" -ForegroundColor Cyan
if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
python -m venv $venv
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "== Installing build deps (mcp, sqlalchemy, pyodbc, typer, pyinstaller) ==" -ForegroundColor Cyan
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet mcp sqlalchemy pyodbc typer pyinstaller

Write-Host "== Freezing server.exe ==" -ForegroundColor Cyan
& $py -m PyInstaller --onefile --name server `
    --distpath (Join-Path $work "dist") `
    --workpath (Join-Path $work "build") `
    --specpath $work `
    --collect-all mcp `
    --hidden-import pyodbc `
    --hidden-import sqlalchemy.dialects.mssql.pyodbc `
    $src

$out = Join-Path $work "dist\server.exe"
$dst = Join-Path $here "server\server.exe"
Copy-Item $out $dst -Force
$mb = [math]::Round((Get-Item $dst).Length / 1MB, 1)
Write-Host "== Done: $dst ($mb MB) ==" -ForegroundColor Green
Write-Host "Now repackage imdr-db.mcpb (see header comment)." -ForegroundColor Yellow
