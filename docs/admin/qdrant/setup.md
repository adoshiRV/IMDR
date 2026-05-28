# Qdrant — first-time setup

Idempotent. Re-running the installer is the supported way to push
config edits and to recover from a corrupted install.

## Prereqs

- Windows 10 / 11 with admin rights on this box.
- The IMDR repo checked out (the installer reads `config\qdrant\production.yaml` from it).
- PowerShell 5.1+ (built in).
- Outbound HTTPS to GitHub (qdrant binary + web UI) and nssm.cc (NSSM zip).

## Install

From an **elevated** PowerShell:

```powershell
cd Z:\Business\Personnel\Arjun\GitHub\IMDR
powershell -ExecutionPolicy Bypass -File scripts\admin\install_qdrant.ps1
```

The installer:

1. Verifies it's elevated.
2. Downloads three archives to `%TEMP%\imdr-qdrant-install\`:
   - `qdrant-x86_64-pc-windows-msvc.zip` (v1.18.0) — server binary.
   - `nssm-2.24.zip` — service wrapper. Falls back to nssm.cc's CI build URL if the primary release endpoint is 503.
   - `dist-qdrant.zip` (qdrant-web-ui) — dashboard assets. The Windows qdrant binary doesn't bundle these; the dashboard 404s without them.
3. Extracts:
   - `qdrant.exe` → `C:\IMDR_LOCAL\qdrant\qdrant.exe`
   - `nssm.exe`   → `C:\IMDR_LOCAL\nssm\nssm.exe`
   - web UI       → `C:\IMDR_LOCAL\qdrant\static\` (qdrant looks for `./static` relative to AppDirectory)
4. Creates `C:\IMDR_LOCAL\qdrant\storage\` and `C:\IMDR_LOCAL\qdrant\snapshots\`.
5. Copies `config\qdrant\production.yaml` → `C:\ProgramData\Qdrant\config.yaml`.
6. Registers the `Qdrant` Windows Service via NSSM with:
   - `AppDirectory` = `C:\IMDR_LOCAL\qdrant` (so `./static` resolves).
   - `AppParameters` = `--config-path "C:\ProgramData\Qdrant\config.yaml"`.
   - `Start` = `SERVICE_AUTO_START` (boots on system start).
   - `AppStdout` / `AppStderr` → `qdrant.log` / `qdrant.err.log` in the data root, rotated at 10 MB.
7. Starts the service and pings `http://127.0.0.1:6333/`.

On success it prints the next steps:

```powershell
python -m imdr.connectors.qdrant_schema apply        # create collections
python playground\research\test_qdrant_e2e.py        # round-trip test (ANZ)
```

### Running from outside the repo

If you've copied the `.ps1` somewhere off-repo (e.g. `C:\install_qdrant.ps1`),
pass the repo's config path explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File C:\install_qdrant.ps1 `
  -RepoConfig "Z:\Business\Personnel\Arjun\GitHub\IMDR\config\qdrant\production.yaml"
```

## Verify

```powershell
Get-Service Qdrant                                  # Status: Running
Invoke-WebRequest http://127.0.0.1:6333/ | Select-Object -Expand Content
```

The HTTP root returns a JSON banner with the Qdrant version.

The dashboard lives at <http://127.0.0.1:6333/dashboard>.

## Uninstall

```powershell
& "C:\IMDR_LOCAL\nssm\nssm.exe" stop Qdrant
& "C:\IMDR_LOCAL\nssm\nssm.exe" remove Qdrant confirm
Remove-Item -Recurse -Force "C:\IMDR_LOCAL\qdrant"
Remove-Item -Recurse -Force "C:\IMDR_LOCAL\nssm"
Remove-Item -Recurse -Force "C:\ProgramData\Qdrant"
# Data dir lives under C:\IMDR_LOCAL\qdrant\storage — included in the
# Remove-Item above. To keep the vectors and only uninstall the binary,
# move storage\ and snapshots\ aside before running this block.
```
