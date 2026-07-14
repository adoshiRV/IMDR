# IMDR MCPB — Admin Build & Distribution Guide

This directory packages an MCPB (MCP Bundle) that gives Claude Desktop users
**read-only** access to the IMDR database. As of v2.0.0 the server ships as a
**self-contained Windows executable** — target machines need **no Python
install** and no `pip` dependencies.

## What's inside

```
mcpb/
├── manifest.json           # Extension metadata & user config (server.type = binary)
├── server/
│   ├── server.exe          # Frozen MCP server (Python + mcp + sqlalchemy + pyodbc)
│   ├── server.py           # Source for server.exe (edit this, then rebuild)
│   └── requirements.txt    # Runtime deps (for source runs / reference)
├── build_server_exe.ps1    # Rebuilds server.exe from server.py
└── README.md               # This file
```

## Prerequisites

### On each USER's machine
1. **Claude Desktop** installed.
2. **Windows domain-joined** to `RVCAPITALFUNDS` (the extension authenticates
   with the user's own AD identity — `Trusted_Connection=yes`, no passwords).
3. That user's AD account granted **`db_datareader`** on the `IMDR` database.
   > Ask the DBA to add the user (ideally add an **AD group** once and drop
   > users into it) as a SQL login mapped to `db_datareader`. Without this the
   > extension installs but every query fails with a login error.
4. The OS **`SQL Server`** ODBC driver — ships with every Windows install, so
   normally nothing to do.
5. **Network access** to the RDS instance (office network or VPN).

### On the ADMIN build machine (only to rebuild the exe)
- **Python 3.11+** on PATH. The frozen exe is self-contained, so the exact
  version doesn't matter for users.

## Build

### Rebuild the executable (only after editing `server/server.py`)
```powershell
powershell -ExecutionPolicy Bypass -File .\build_server_exe.ps1
```
This creates a throwaway venv, freezes `server.py` into `server/server.exe`
(~27 MB), and copies it into place.

### Repackage the .mcpb
```bash
python -c "import zipfile; z=zipfile.ZipFile('imdr-db.mcpb','w',zipfile.ZIP_DEFLATED); [z.write(f,f) for f in ['manifest.json','README.md','server/server.exe']]; z.close()"
```
`imdr-db.mcpb` is the single file you distribute.

## Distribute to users

Put `imdr-db.mcpb` on a shared location, e.g.
`Z:\Business\Shared\claude_extensions\imdr-db.mcpb`.

> **Antivirus note:** PyInstaller executables are occasionally flagged by
> endpoint AV as "unknown publisher". If rollout is blocked, ask IT to
> allowlist `server.exe` (by hash) or the distribution folder.

## User installation

1. Open Claude Desktop → **Settings** → **Connectors** →
   **Add → Custom → Desktop** → select `imdr-db.mcpb`.
2. Leave **ODBC Driver Name** as `SQL+Server` (the default) unless told
   otherwise.
3. Enable the extension.

### Verify
Ask Claude:
> "List all tables in the fx schema"

## What users can do

- Browse schemas and tables
- Inspect column metadata
- Run SELECT queries (500-row default limit, 30 s timeout)
- All queries are audit-logged to `[admin].[mcp_query_log]`

Users **cannot** modify data — INSERT/UPDATE/DELETE/DDL and dangerous patterns
(comments, `xp_`/`sp_` procs, semicolons) are blocked in-server, and their
`db_datareader`-only SQL login blocks it at the database level too.

## Authentication model (no secrets)

There are **no database credentials anywhere** in this bundle. Connections use
**Windows Integrated Authentication** (`Trusted_Connection=yes`) as the AD
identity of whoever launched Claude Desktop. Read-only is enforced both by that
login's `db_datareader` grant and by `_assert_readonly()` in `server.py`.

## Updating

1. Edit `server/server.py`, bump `version` in `manifest.json`.
2. Run `build_server_exe.ps1`, then repackage the `.mcpb` (commands above).
3. Redistribute; users reinstall via Settings → Connectors.

## Alternative: manual JSON config

If MCPB install isn't available, users can configure manually — see
`docs/admin/setup/claude_desktop/setup.md`.
