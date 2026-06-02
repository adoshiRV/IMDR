# BBG Terminal — Python Setup (`imdrbbg` env)

One-time install for the four Bloomberg Terminal users (DS / RM / RW / SP) and
the shared terminal account. Lets a user run Python scripts in
[`bloomberg/`](../../../../bloomberg/) against their logged-in Terminal.

This is **separate** from:

- The `imdr` dev env in [dev_environment.md](../../setup/dev_environment.md) — that's the full developer stack.
- The VS Code mssql setup in [vscode_setup.md](../../setup/vscode_setup.md) — that's read-only DB access.
- The R BBG pipeline at `Z:\...\BBG\` — that runs on these same PCs but in R, not Python.

## What gets installed

A slim conda env named **`imdrbbg`** with:

| Package          | Why                                                         |
| ---------------- | ----------------------------------------------------------- |
| `python`         | 3.11                                                        |
| `blpapi`         | Bloomberg Desktop API (pip, Bloomberg's private index)      |
| `pyarrow`        | Parquet output for production jobs                          |
| `pyyaml`         | Reserved for future config formats                          |
| `jinja2`         | HTML email templates (refresh summary mail)                 |
| `python-dotenv`  | Load `.env` (for `IMDR_EMAIL_TO`, etc.)                     |
| `pywin32`        | Outlook COM automation (sends the refresh summary email)    |

## Prerequisites

1. **Bloomberg Terminal** is installed and you can log into it on this PC.
2. **Anaconda / Miniconda** is installed. (Same conda the R pipeline / IMDR dev users have.)
3. **`Z:\` is mapped** and you can see `Z:\Business\Personnel\Arjun\GitHub\IMDR\`.

## One-time install

Open PowerShell and run:

```powershell
# 1. Enable conda in PowerShell (skip if already done)
& "C:\ProgramData\anaconda3\Scripts\conda.exe" init powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# Close and reopen PowerShell after this.

# 2. Create the env (pulls blpapi from Bloomberg's private index)
conda env create -f Z:\Business\Personnel\Arjun\GitHub\IMDR\bloomberg\environment.yml

# 3. Verify
conda activate imdrbbg
python -c "import blpapi; print('blpapi', blpapi.__version__)"
```

If the `blpapi` import works you're done. If pip can't reach
`blpapi.bloomberg.com`, see [Troubleshooting](#troubleshooting).

## Daily use

Open PowerShell on a PC with a logged-in Terminal:

```powershell
conda activate imdrbbg

# 1. Smoke test (first time, or after re-install) — no email
python Z:\Business\Personnel\Arjun\GitHub\IMDR\bloomberg\smoke_test.py --user dsuri

# 2. Refresh — the real driver. Reads bloomberg/tickers.csv, sends summary email.
python Z:\Business\Personnel\Arjun\GitHub\IMDR\bloomberg\refresh.py --user dsuri --schedule hourly

# Useful flags:
#   --dry-run    parse tickers.csv, print what would be pulled, exit. No BBG call.
#   --no-email   skip the summary email even if IMDR_EMAIL_ENABLED=true.
```

Substitute your user folder: `adoshi`, `dsuri`, `rmahadevan`, `rwu`, `spanda`, or
`shared_term` (default for smoke test).

### Three cadences

| Mode | When | Command | How it's triggered |
| --- | --- | --- | --- |
| **Daily** | Once a day after market close | `--schedule daily` | Windows Task Scheduler |
| **Hourly** | Every hour during market hours | `--schedule hourly` | Windows Task Scheduler |
| **Snapshot** | On-demand — you hit refresh | `--schedule snapshot` | Manually, or a desktop shortcut |

**Daily** and **Hourly** pull only rows tagged with that exact `schedule` in
`bloomberg/tickers.csv`. **Snapshot** pulls **every enabled row for the user**
(daily + hourly + snapshot-tagged) — it's the "refresh everything I care
about, now" mode. Rows tagged `schedule=snapshot` are pulled *only* on
manual snapshot runs.

## Email summary

After every `refresh.py` run, an HTML email with the full snapshot table
is sent via Outlook COM. Recipient comes from the repo `.env`:

```
IMDR_EMAIL_ENABLED=true
IMDR_EMAIL_TO=arjun@rvcapital.com;ops@rvcapital.com
```

If `IMDR_EMAIL_ENABLED=false` or `IMDR_EMAIL_TO` is empty, the run completes
normally and just skips the email (best-effort).

Subject line:
`[IMDR] Bloomberg Terminal — Daily|Hourly|Snapshot Refresh OK|PARTIAL|FAIL | {user} | n_ok/n_total tickers | YYYY-MM-DD HH:MM UTC`

You **do not need to clone the repo** — everything runs straight from `Z:\`.
When Arjun pushes new BBG scripts, they appear under
`Z:\...\IMDR\bloomberg\{user}\` automatically.

## Where output lands

```
Z:\Business\Personnel\Arjun\GitHub\IMDR\data\bloomberg\{user}\
    smoke_test_YYYYMMDD_HHMM.csv
    bbg_<job>_YYYYMMDD_HHMM.parquet     # future production jobs
```

This path is already gitignored (`data/*`). An IMDR-side watcher reads from
here and appends to the database — your scripts never touch the DB directly.

## Troubleshooting

### `conda: command not found`
Conda isn't on `PATH`. Run step 1 of the install or call the full path:
`C:\ProgramData\anaconda3\Scripts\conda.exe`.

### `pip install blpapi` fails with `No matching distribution`
Bloomberg's private index is unreachable. Possible causes:
- Network proxy blocking `blpapi.bloomberg.com`. Ask IT to allow it.
- Fall back to the bundled C++ SDK path: install `blpapi_cpp` from the
  Bloomberg Customer Support portal, set `BLPAPI_ROOT`, and retry.

### Script reports `could not start a session at localhost:8194`
- The Bloomberg Terminal isn't running or no one is logged in.
- Or `bbcomm.exe` isn't listening — restart the Terminal.
- Test from R the same way you'd test the existing pipeline:
  `Rblpapi::blpConnect(host="localhost", port=8194L)` should succeed first.

### Script runs but the CSV doesn't appear
Check you have **write access** to
`Z:\Business\Personnel\Arjun\GitHub\IMDR\data\bloomberg\`. The R pipeline
writes elsewhere on `Z:\` so write access is likely there — but the IMDR
subtree is a different ACL. Tell Arjun if it's blocked.

### Environment update later
When `environment.yml` changes (new deps), refresh in place:

```powershell
conda env update -f Z:\Business\Personnel\Arjun\GitHub\IMDR\bloomberg\environment.yml --prune
```
