# Linear MCP — Project Management from Claude Code

> **Scope: personal / user-only.** This is not a shared team tool. Each user wires Linear into their own Claude Code via user-scope config (`~/.claude.json`). Do not commit a Linear MCP entry to the project-level `.mcp.json`.

Connects Linear (issues, projects, cycles) to Claude Code as an MCP server so issues can be read and edited from inside Claude sessions.

## Architecture

```
Claude Code (VS Code / CLI)
        │ (HTTP streaming)
        ▼
   mcp.linear.app/mcp   ← Linear-hosted, OAuth-authenticated
        │
        ▼
   Linear workspace (per user)
```

- **Transport**: streamable HTTP (remote). No local process.
- **Auth**: Browser OAuth on first tool call. No API token in config.
- **Owner**: Linear. They version and maintain the server.
- **Scope**: user-level — applies to every Claude Code session for that Windows user.

> The legacy `/sse` endpoint was deprecated by Linear on 2026-04-08. If you wired this up before that date, see [Migrating from `/sse`](#migrating-from-sse) below.

## Setup

### One-time install

Edit `C:\Users\{user}\.claude.json` and add a top-level `mcpServers.linear` entry:

```json
"mcpServers": {
  "linear": {
    "type": "http",
    "url": "https://mcp.linear.app/mcp"
  }
}
```

If `mcpServers` already exists at the top level, add `linear` alongside any existing entries — do not edit the per-project `projects.{path}.mcpServers` blocks (those are project-scoped and meant for shared MCPs like `imdr-db`).

Equivalent CLI form:

```powershell
claude mcp add --transport http linear https://mcp.linear.app/mcp --scope user
```

### First-use OAuth

1. Restart Claude Code (close and reopen the VS Code window, or reload the extension).
2. Trigger any Linear tool from a session, e.g. *"list my Linear teams"*.
3. A browser window opens — log in to Linear and approve access.
4. The token is cached by Claude Code; subsequent calls are silent.

## Verifying the connection

After restart, available tools appear under the `mcp__linear__*` namespace. Quick checks:

- *"list my Linear teams"*
- *"show issues in my current cycle"*
- *"what projects are in the {team} team"*

If the tools don't appear, check `~/.claude.json` parses as valid JSON and that the `mcpServers` block is at the **top level** (not nested inside `projects`).

## Why user-scope only

- The OAuth token lands in Claude Code's per-user cache; sharing the MCP config doesn't share access.
- Each engineer needs their own Linear account anyway.
- Project-level `.mcp.json` is committed — anything there is broadcast to everyone who clones the repo. Linear has no business there.

## Relationship to `imdr-db` MCP

Unrelated. `imdr-db` (see [mcp.md](mcp.md)) is a local stdio MCP for read-only SQL Server access, configured at project scope. Linear MCP is a remote SSE MCP for project management, configured at user scope. They coexist with no overlap.

## Migrating from `/sse`

If `~/.claude.json` still has `"type": "sse"` / `"url": "https://mcp.linear.app/sse"`, the server will refuse writes with a `Tool call rejected as a pre-removal deprecation signal` error (reads may still appear to work). Replace the entry with the `http` / `/mcp` form above, restart Claude Code, and re-authorize when the browser prompt opens. No data migration is needed — this is purely a transport change.

## Rollback

Remove the `linear` entry (or the whole top-level `mcpServers` block if it only contained `linear`) from `~/.claude.json` and restart Claude Code. To revoke OAuth on Linear's side: Linear → Settings → API → revoke the Claude Code connection.

## Change log

- **2026-05-26** — migrated from deprecated `/sse` transport to `/mcp` (streamable HTTP). Linear retired `/sse` on 2026-04-08; writes started returning a deprecation rejection. Workspace: IMDR team (`6d060c2a-484b-4d8f-8328-e01f07c64f54`).
