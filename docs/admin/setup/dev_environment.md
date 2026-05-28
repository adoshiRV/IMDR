# Dev Environment Setup

Setting up a local Python environment to develop and run IMDR pipelines.
This is the developer track; for read-only SQL access, see
[vscode_setup.md](vscode_setup.md).

## 1. Enable conda in PowerShell (first time only)

```powershell
C:\ProgramData\anaconda3\Scripts\conda.exe init powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Close and reopen the terminal afterwards.

If `conda` is still not recognised, load it manually for the current session:

```powershell
& "C:\ProgramData\anaconda3\Scripts\conda.exe" "shell.powershell" "hook" |
    Out-String | ?{$_} | Invoke-Expression
```

## 2. Create the `imdr` environment (first time only)

```powershell
cd Z:\Business\Personnel\Arjun\GitHub\IMDR
C:\ProgramData\anaconda3\Scripts\conda.exe env create -f environment.yml -y
```

## 3. Activate

```powershell
conda activate imdr
```

## 4. Configure `.env`

Copy `.env.example` to `.env` at the repo root and fill in the required values
(see `.env.example` for the full key list).

## 5. Run tests and the linter

```powershell
pytest tests/unit -v
ruff check src/ tests/
```
