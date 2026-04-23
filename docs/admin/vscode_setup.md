# IMDR Read-Only Access via VS Code

Setup guide for a **read-only user** who wants to query IMDR tables from VS Code using the Microsoft **SQL Server (mssql)** extension. You run SQL directly from the editor — Claude Code can be used separately to help draft queries, but the connection to the database is purely through the SQL extension.

---

## 1. Prerequisites

Get these in place first — ideally with help from the DBA / ops:

| Requirement | Detail |
|---|---|
| Windows domain account | Authentication is Windows-only (`Trusted_Connection=yes`). No DB username/password. |
| `db_datareader` on the `IMDR` database | DBA grants this to your Windows login. Only `SELECT` is allowed. |
| Network access to `rv-database-1.ctym72ljvrjq.ap-southeast-1.rds.amazonaws.com:1433` | Office network or VPN. |
| VS Code | `code --version` works. |
| ODBC Driver 17 for SQL Server (or `SQL Server` legacy driver) | Usually preinstalled on Windows. Install from Microsoft if missing. |

> **Hard rules** (see `MEMORY.md`): only ever connect to the `IMDR` database. Never run any DDL or write statements — read-only permissions will block these anyway, but do not try.

---

## 2. Install the SQL Server Extension

Open VS Code → Extensions panel → search for **SQL Server (mssql)** by **Microsoft** → **Install**.

After install, a new **SQL Server** icon appears in the Activity Bar (left sidebar).

---

## 3. Confirm the Network Path (Optional Sanity Check)

Before configuring the extension, verify you can reach the host from your machine:

```powershell
Test-NetConnection -ComputerName rv-database-1.ctym72ljvrjq.ap-southeast-1.rds.amazonaws.com -Port 1433
```

`TcpTestSucceeded : True` means the firewall / VPN is fine. If it's `False`, fix the network before moving on — nothing else will work.

---

## 4. Add the IMDR Connection

1. Click the **SQL Server** icon in the Activity Bar.
2. Click **Add Connection** (the `+` at the top of the panel).
3. Fill in each prompt as it appears:

| Prompt | Value |
|---|---|
| Server name | `rv-database-1.ctym72ljvrjq.ap-southeast-1.rds.amazonaws.com` |
| Database name | `IMDR` |
| Authentication type | **Integrated** (Windows Authentication) |
| Encrypt | **Mandatory** |
| Trust server certificate | **Yes** (RDS serves its own cert) |
| Profile name | `IMDR` |

4. Click **Connect**. The tree should expand and show the schemas (`audit`, `calendar`, `commodities`, `equity`, `fx`, `rates`, …).

If the connection fails, see [Troubleshooting](#6-troubleshooting) below.

---

## 5. Run Your First Query

1. Open a new file: `Ctrl+N`.
2. Change the language to **SQL**: bottom-right of the window, click the language label → pick `SQL`.
3. Paste a query — for example:

   ```sql
   SELECT TOP 10 *
   FROM [fx].[fact_vol]
   ORDER BY obs_date DESC;
   ```

4. Run it: `Ctrl+Shift+E` (or right-click → **Execute Query**).
5. Results appear in a panel below. Right-click the result grid to **Save as CSV / JSON / Excel**.

### Knowing the Schema

To figure out what's queryable:

- **Live schema**: expand the tree in the SQL Server sidebar — every schema, table, view, and column is listed. Right-click a table → **Select Top 1000** to get a starter query.
- **Documentation**:
  - [docs/fx/](../fx/) — FX fact + dim tables
  - [docs/rates/](../rates/) — rates curves, swaption vol, skew
  - [docs/commodities/](../commodities/) — Citi commodity tables
  - [docs/equity/](../equity/) — equity index levels + vol
  - [docs/admin/schema_conventions.md](schema_conventions.md) — naming rules (`fact_` / `dim_`, FKs, timestamps)

### SQL Conventions to Keep in Mind

- Fact tables are `fact_…`; dimensions are `dim_…`.
- All timestamps are `DATETIMEOFFSET` — filter with `>= '2026-01-01'`; SQL Server will convert.
- Facts join to dims on integer IDs (`pair_id`, `curve_id`, `market_id`, …), not string codes.
- Always bracket names: `[schema].[table]` works even for reserved words.

### Using Claude Code to Help Write Queries

Claude Code has no direct connection to the database in this setup — use it as a SQL drafting assistant:

1. Open Claude Code alongside your SQL file.
2. Ask something like *"write a SQL query for IMDR that returns the last 30 days of EURUSD ATM vol from fx.fact_vol, joining to fx.dim_currency_pair on pair_id."*
3. Paste Claude's SQL into your `.sql` file and run it with `Ctrl+Shift+E`.
4. If you hit an error, share the error text and Claude's SQL back with Claude to iterate.

Claude won't know the exact columns unless you tell it — paste the output of `EXEC sp_help '[fx].[fact_vol]'` or right-click → **Script Table As → SELECT** to give it real column names.

---

## 6. Troubleshooting

### `Login failed for user …`
Your Windows account has no login on `IMDR`. Ask the DBA to grant `db_datareader`.

### `A network-related or instance-specific error occurred`
You're not on the VPN / office network, or the host is unreachable. Re-run the `Test-NetConnection` check in Step 3.

### `The certificate chain was issued by an authority that is not trusted`
Set **Trust server certificate = Yes** on the connection. RDS uses its own self-signed cert — this is expected.

### `Data source name not found and no default driver specified`
No ODBC driver installed. Install **ODBC Driver 17 for SQL Server** from Microsoft's site.

### Query runs but returns no rows
- Check timestamp filters — IMDR timestamps are `DATETIMEOFFSET`, so a bare date like `'2026-01-01'` is midnight UTC.
- Check you're joining on the right ID — facts reference dims by integer ID, not string code.
- Right-click the table in the sidebar → **Select Top 1000** to confirm the table actually has data.

### Write statement blocked
Expected — your login only has `db_datareader`. Use a different account if you need write access, and only for tables you own.

### Want to change the connection later
SQL Server panel → right-click the profile → **Edit Connection Profile** or **Remove Connection Profile**.

---

## 7. Where to Go Next

- Browse the schema tree in the SQL Server sidebar first — it's the quickest way to find what exists.
- For ad-hoc exploration, right-click a table → **Select Top 1000** and modify from there.
- Save reusable queries as `.sql` files anywhere on your machine; VS Code will keep the mssql connection attached when you reopen them.
- For schema documentation beyond what's in the sidebar, see the per-domain docs listed above.
