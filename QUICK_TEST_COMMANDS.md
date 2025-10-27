# Quick Test Commands Reference

## Start server on different port (validate env override)
```powershell
# PowerShell
$env:BODAL_PORT = "8080"
python -m services.api.app
# Visit http://127.0.0.1:8080/health → {"ok": true}

# Or inline
$env:BODAL_PORT = "8080"; python -m services.api.app
```

```bash
# Bash/Unix
BODAL_PORT=8080 python -m services.api.app
# Visit http://127.0.0.1:8080/health → {"ok": true}
```

## Check logs contain config banner
```powershell
# PowerShell
Get-Content logs\service.log -Tail 5
# Expect: "Starting Flask on 127.0.0.1:8080 (debug=True) | ARTIFACTS_ROOT=... JOBS_ROOT=... SCHEMA=..."
```

```bash
# Bash/Unix
tail -n 5 logs/service.log
# Expect: "Starting Flask on 127.0.0.1:8080 (debug=True) | ARTIFACTS_ROOT=... JOBS_ROOT=... SCHEMA=..."
```

## Check directories created
```powershell
# PowerShell
Get-ChildItem -Directory | Where-Object { $_.Name -in @('artifacts', 'data', 'logs') }
```

```bash
# Bash/Unix
ls -la artifacts data/jobs logs
```

## Test custom artifacts path
```powershell
# PowerShell
$env:BODAL_ARTIFACTS_ROOT = "custom_path"
python -c "from services.api.config import CONFIG; print(CONFIG.ARTIFACTS_ROOT)"
# Should create and show custom_path/
```

```bash
# Bash/Unix
BODAL_ARTIFACTS_ROOT=custom_path python -c "from services.api.config import CONFIG; print(CONFIG.ARTIFACTS_ROOT)"
# Should create and show custom_path/
```

## Health check test
```powershell
# PowerShell
Invoke-WebRequest -Uri http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
# Should return: {"ok": true}
```

```bash
# Bash/Unix
curl http://127.0.0.1:8000/health
# Should return: {"ok": true}
```

## Run comprehensive acceptance tests
```bash
python test_acceptance.py
# Should show: ✓ ALL ACCEPTANCE TESTS PASSED
```

## Verify .env.example
```bash
cat .env.example
# Should document all BODAL_* environment variables
```
