# MCP Server — Admin Reference

## Architecture

The IMDR MCP server (`mcp/server.py`) gives Claude read-only access to the IMDR database via the Model Context Protocol (MCP).

```
Claude Desktop / Claude Code
        │ (stdio)
        ▼
   mcp/server.py  ← runs as subprocess per user
        │
        ▼
   IMDR SQL Server (RDS)
   Windows Auth (Trusted_Connection)
```

Each user runs their own MCP subprocess. The process inherits the logged-in user's Windows credentials — no shared passwords.

## Tools Exposed

| Tool | Purpose | Audit Logged |
|---|---|---|
| `list_tables(schema?)` | Browse available tables | No |
| `describe_table(schema, table)` | Column metadata + row count | No |
| `query(sql, max_rows=500)` | Execute read-only SELECT | Yes |

## Safety Model

The `query` tool enforces read-only access:

1. **Statement must start with** `SELECT` or `WITH`
2. **Blocked keywords** (word-boundary match): `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`, `EXECUTE`, `GRANT`, `REVOKE`, `MERGE`
3. **Blocked patterns**: `--` (comments), `/*` (block comments), `xp_` (extended procs), `sp_` (stored procs)
4. **Row cap**: max 500 rows by default (caller can increase)

Schema/table inputs to `describe_table` are validated with `_validate_column` from `reader.py` (alphanumeric + underscore only).

## Audit Table

**Location**: `[admin].[mcp_query_log]`

**Migration**: `migrations/006_create_admin_mcp_query_log.sql` — run manually in SSMS.

| Column | Type | Description |
|---|---|---|
| `id` | INT IDENTITY | Primary key |
| `sql_text` | NVARCHAR(MAX) | Query text (truncated to 4000 chars) |
| `called_by` | VARCHAR(100) | Windows login name (via `os.getlogin()`) |
| `row_count` | INT | Rows returned |
| `execution_ms` | INT | Execution time |
| `error_message` | NVARCHAR(2000) | Error if query failed |
| `created_at` | DATETIMEOFFSET | Timestamp |
| `updated_at` | DATETIMEOFFSET | Timestamp |

**Useful queries:**

```sql
-- Recent queries by user
SELECT called_by, sql_text, row_count, execution_ms, created_at
FROM [admin].[mcp_query_log]
ORDER BY created_at DESC;

-- Errors in last 24h
SELECT * FROM [admin].[mcp_query_log]
WHERE error_message IS NOT NULL
  AND created_at > DATEADD(DAY, -1, SYSDATETIMEOFFSET());

-- Query volume by user
SELECT called_by, COUNT(*) as queries, AVG(execution_ms) as avg_ms
FROM [admin].[mcp_query_log]
GROUP BY called_by;
```

## Adding New Tools

Add a function to `mcp/server.py` with the `@mcp.tool()` decorator:

```python
@mcp.tool()
def my_new_tool(param: str) -> str:
    """Docstring becomes the tool description Claude sees."""
    # Use _connector.read_engine for reads
    # Use _connector.session() for writes (audit only)
    return "result"
```

Restart Claude Desktop / reload Claude Code to pick up new tools.

## Managing Users

1. User follows `docs/claude_desktop/setup.md` to configure their Claude Desktop
2. Username is auto-detected from Windows login — no manual config needed
3. Monitor usage via `[admin].[mcp_query_log]`
4. To revoke access: user removes the MCP config from their Claude Desktop

## Infrastructure Reuse

The server reuses existing IMDR infrastructure — no duplication:

| Component | Source |
|---|---|
| Connection config | `Settings` from `src/imdr/config/settings.py` |
| Connection pooling | `MSSQLConnector` from `src/imdr/connectors/mssql.py` |
| Input validation | `_validate_column` from `src/imdr/connectors/reader.py` |
| `.env` config | Same `.env` file used by all IMDR pipelines |
