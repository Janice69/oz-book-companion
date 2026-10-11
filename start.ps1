$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' split_passages.py
if ($LASTEXITCODE -ne 0) { throw 'Book preparation failed.' }
Write-Host 'Open http://127.0.0.1:8000 in your browser. First run downloads the local AI models.'
& '.\.venv\Scripts\python.exe' -m uvicorn app:app --host 127.0.0.1 --port 8000
