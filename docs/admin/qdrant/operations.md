# Qdrant — operations

## Service lifecycle

```powershell
Get-Service Qdrant                  # status
Start-Service Qdrant
Stop-Service Qdrant
Restart-Service Qdrant
```

Or via NSSM (lets you tail stdout/stderr in one shot):

```powershell
& "C:\IMDR_LOCAL\nssm\nssm.exe" status  Qdrant
& "C:\IMDR_LOCAL\nssm\nssm.exe" start   Qdrant
& "C:\IMDR_LOCAL\nssm\nssm.exe" stop    Qdrant
& "C:\IMDR_LOCAL\nssm\nssm.exe" restart Qdrant
```

## Health check

```powershell
Invoke-WebRequest http://127.0.0.1:6333/ | Select-Object -Expand Content
```

Or from Python:

```python
from imdr.connectors.qdrant import is_alive
assert is_alive()
```

## Logs

The installer wires NSSM to redirect Qdrant stdout/stderr to files under
the data dir (rotated at 10 MB to stop them growing unbounded):

```
C:\IMDR_LOCAL\qdrant\qdrant.log       (stdout)
C:\IMDR_LOCAL\qdrant\qdrant.err.log   (stderr)
```

Tail the latest:

```powershell
Get-Content C:\IMDR_LOCAL\qdrant\qdrant.log -Tail 50 -Wait
```

NSSM service-control events (start/stop/crash) also show up in the
Windows Event Log:

```powershell
Get-EventLog -LogName Application -Source Qdrant -Newest 20
```

## Pushing a config change

Source of truth: `config/qdrant/production.yaml` (tracked in repo).
After editing it:

```powershell
# Re-run the installer — copies repo config to ProgramData and restarts.
powershell -ExecutionPolicy Bypass -File scripts\admin\install_qdrant.ps1
```

The installer is idempotent: it skips the download/extract steps once
the binaries are in place, so subsequent runs are quick.

## Backup

Two layers:

1. **File-level.** `C:\IMDR_LOCAL\qdrant\storage\` is just files. With
   Qdrant stopped, copy the dir to a backup location (Z: share is
   fine; the cost of a slow restore beats the risk of a hot copy).
2. **Qdrant snapshots.** Per-collection, point-in-time. Created via
   the API:

   ```python
   from imdr.connectors.qdrant import get_qdrant_client
   c = get_qdrant_client()
   c.create_snapshot(collection_name="research_gemini_embedding_2_3072d")
   ```

   Snapshots land in `C:\IMDR_LOCAL\qdrant\snapshots\<collection>\` and
   can be downloaded via the API or restored to a different machine.

## Reset (last resort)

Qdrant is the only place vectors live, but vectors are *derivative* —
every chunk's text + model is in MSSQL (`research.fact_chunk` plus
`research.dim_embedding_model`). A full Qdrant reset is therefore safe;
it just means re-embedding every chunk via the active provider
(Voyage / Gemini) and writing the vectors back into a fresh collection:

```powershell
Stop-Service Qdrant
Remove-Item -Recurse -Force "C:\IMDR_LOCAL\qdrant\storage"
New-Item   -ItemType Directory "C:\IMDR_LOCAL\qdrant\storage" | Out-Null
Start-Service Qdrant

python -m imdr.connectors.qdrant_schema apply
# Re-embed reports back into the empty collection:
python playground/research/reembed_report.py <report_id> [<report_id> ...]
```

The re-embed will cost provider API spend — pre-validate scope before
running over thousands of reports.
