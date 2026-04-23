# SFTP Downloads (Scaffold — Not Implemented)

Intended for vendors that drop files on an SFTP endpoint for pickup.

## Current status

`src/imdr/vendors/acquirers/sftp.py` has a placeholder `SFtpAcquirer` that raises `NotImplementedError`.

## Expected design

- Spec declares `host`, `port`, `remote_dir`, `filename_glob`, `output_dir`, `credentials_prefix`.
- Acquirer uses `paramiko.SSHClient` + `SFTPClient` (new dependency when implemented). Credentials resolved via `get_vendor_credentials(prefix)`.
- Listing: `sftp.listdir_attr(remote_dir)` → filter by glob + mtime since last run.
- Download: `sftp.get(remote_path, local_path)` for each match.
- Raise `DownloadFailed` on partial/total failures; map paramiko errors to existing `VendorError` subclasses.

## Idempotency consideration

SFTP vendors often leave files in place indefinitely. Track what's been processed — either via a state file in `{output_dir}/.processed` or by timestamping archived files and checking archives before re-download.

## When to implement

When the first SFTP feed lands. Add `paramiko` to dependencies at that point.
