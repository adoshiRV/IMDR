# Claude Desktop — IMDR Setup Guide

Connect Claude Desktop to the IMDR database so you can query market data directly in conversation.

## Prerequisites

1. **Claude Desktop** installed — download at [claude.ai/download](https://claude.ai/download)
2. **Anaconda / Miniconda** installed on your machine
3. **Network access** to the RDS instance (VPN or office network)
4. **Windows domain account** — authentication uses your Windows credentials

## Step 1 — Create the Python Environment

Open a terminal and run:

```bash
cd Z:\Business\Personnel\Arjun\GitHub\IMDR\docs\claude_desktop
conda env create -f environment.yml
```

This creates a conda environment called `imdr-mcp` with the minimal dependencies needed.

**Find your Python path** (you'll need it in Step 2):

```bash
conda activate imdr-mcp
where python
```

Copy the path — it will look like `C:\Users\YOUR_USERNAME\.conda\envs\imdr-mcp\python.exe`.

Verify the ODBC driver is available:

```bash
python -c "import pyodbc; print(pyodbc.drivers())"
```

You should see `SQL Server` or `ODBC Driver 17 for SQL Server` in the list.

## Step 2 — Configure Claude Desktop

Open your Claude Desktop config file:

```
C:\Users\<YourUsername>\AppData\Roaming\Claude\claude_desktop_config.json
```

If the file doesn't exist, create it. Paste the following, replacing the placeholders:

```json
{
  "mcpServers": {
    "imdr-db": {
      "command": "C:/Users/YOUR_USERNAME/.conda/envs/imdr-mcp/python.exe",
      "args": [
        "Z:/Business/Personnel/Arjun/GitHub/IMDR/mcp/server.py"
      ],
      "env": {
        "IMDR_MSSQL_HOST": "rv-database-1.ctym72ljvrjq.ap-southeast-1.rds.amazonaws.com",
        "IMDR_MSSQL_DATABASE": "IMDR",
        "IMDR_MSSQL_DRIVER": "SQL+Server"
      }
    }
  }
}
```

**Replace:**
- `YOUR_USERNAME` — your Windows username (from the path in Step 1)

Your Windows login name is automatically captured for audit logging — no manual config needed.

## Step 3 — Restart Claude Desktop

Fully quit Claude Desktop (check system tray) and reopen it. You should see a **hammer icon** in the chat input area — this indicates MCP tools are loaded.

## Step 4 — Verify

Try these prompts in Claude Desktop:

> **"List all tables in the fx schema"**

Claude will call `list_tables("fx")` and show you the available tables.

> **"Describe the fact_ohlc table in fx"**

Claude will show column names, types, and row count.

> **"Show me the last 10 FX vol observations for EURUSD"**

Claude will write and execute a SELECT query against the database.

## What You Can Do

The MCP server gives Claude **read-only** access. Example prompts:

- "What schemas and tables are available in IMDR?"
- "Show me the structure of the rates.fact_observation table"
- "Get the latest 20 EURUSD OHLC bars"
- "What's the average ATM implied vol for USDJPY in the last month?"
- "Compare 10Y sovereign rates for USA vs DEU over the past week"
- "How many vol observations do we have per currency pair?"

Claude cannot modify data — all INSERT, UPDATE, DELETE, and DDL operations are blocked.

## Troubleshooting

### Hammer icon not showing
- Check your JSON for syntax errors — validate at [jsonlint.com](https://jsonlint.com)
- Make sure the `command` path points to your actual Python executable
- Fully quit and restart Claude Desktop (not just close the window)

### Connection error
- Verify you're on the office network or VPN
- Check that your Windows account has access to the IMDR database
- Test directly: `python -c "import pyodbc; conn = pyodbc.connect('DRIVER={SQL Server};SERVER=rv-database-1.ctym72ljvrjq.ap-southeast-1.rds.amazonaws.com;DATABASE=IMDR;Trusted_Connection=yes'); print('OK')"`

### Driver not found
- Run `python -c "import pyodbc; print(pyodbc.drivers())"` to see available drivers
- If you see `ODBC Driver 17 for SQL Server` instead of `SQL Server`, update the `IMDR_MSSQL_DRIVER` env var in your config to `ODBC+Driver+17+for+SQL+Server`

### Query returns an error
- Make sure you're using SELECT queries only
- Use `[schema].[table]` format for table names (e.g., `[fx].[fact_ohlc]`)
- Check column names with `describe_table` first

### Environment issues
- If `conda env create` fails, make sure you can reach `Z:\` drive
- If packages fail to install, try: `conda activate imdr-mcp && pip install mcp sqlalchemy pydantic-settings python-dotenv pyodbc`
