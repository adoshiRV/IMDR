# IMDR MCPB — Admin Build & Distribution Guide

This directory contains an MCPB (MCP Bundle) package for distributing
read-only IMDR database access to Claude Desktop users.

## What's inside

```
mcpb/
├── manifest.json           # Extension metadata & user config
├── server/
│   ├── server.py           # Self-contained MCP server (no IMDR source dependency)
│   └── requirements.txt    # Python dependencies
└── README.md               # This file
```

## Prerequisites (admin build machine)

1. Node.js 18+ installed
2. Install the MCPB CLI:
   ```bash
   npm install -g @anthropic-ai/mcpb
   ```

## Build the .mcpb file

From this directory:

```bash
cd docs/claude_desktop/mcpb
mcpb pack .
```

This produces `imdr-db.mcpb` — the single file you distribute.

### Validate before distributing

```bash
mcpb validate .
```

## Distribute to users

Send `imdr-db.mcpb` to users via:
- Shared network drive (e.g. `Z:\Business\Shared\claude_extensions\`)
- Email attachment
- Internal download portal

## User installation

Users need:
1. **Claude Desktop** installed
2. **Python 3.11+** with `pyodbc`, `sqlalchemy`, and `mcp` packages
3. **Network access** to the RDS instance (VPN or office network)
4. **Windows domain account** for database authentication

### Install the extension

1. Open Claude Desktop → **Settings** → **Extensions**
2. Click **Install Extension…** → select `imdr-db.mcpb`
3. When prompted for **IMDR_MSSQL_DRIVER**, enter the ODBC driver name:
   - Most machines: `SQL+Server` (the default)
   - If you have ODBC Driver 17 installed: `ODBC+Driver+17+for+SQL+Server`
   - To check: `python -c "import pyodbc; print(pyodbc.drivers())"`
4. Restart Claude Desktop

### Verify

Look for the **hammer icon** in the chat input. Try:
> "List all tables in the fx schema"

## What users can do

- Browse schemas and tables
- Inspect column metadata
- Run SELECT queries (500 row default limit, 30s timeout)
- All queries are audit-logged to `[admin].[mcp_query_log]`

Users **cannot** modify data — INSERT, UPDATE, DELETE, DDL, and dangerous
patterns (comments, xp_/sp_ procs) are all blocked.

## Updating

To release a new version:
1. Edit `server/server.py` and bump `version` in `manifest.json`
2. Run `mcpb pack .` to rebuild
3. Redistribute the new `.mcpb` file
4. Users reinstall via Settings → Extensions

## Alternative: manual JSON config

If MCPB installation isn't available, users can still configure manually.
See `docs/claude_desktop/setup.md` for the step-by-step guide.
