# `/config` Endpoint Documentation

## Purpose

The `/config` endpoint provides a **debug-only** inspection view of the active service configuration. It's designed to help developers and operators troubleshoot configuration issues without needing shell access to the container or server.

## Use Cases for BodalAI Project

### 1. **Container Debugging** 🐳
When running the service in Docker/Kubernetes:
```bash
# Check if environment variables are correctly passed
curl http://pod-ip:8000/config

# Verify mounted volumes are accessible
# Response shows if schema/orchestrator files exist
```

**Example scenario**: You deployed to Kubernetes with a custom `BODAL_ARTIFACTS_ROOT=/mnt/storage` but renders are failing. Hit `/config` to verify:
- The path was applied correctly
- The directory exists and is writable
- Schema and orchestrator files are accessible

### 2. **Environment Validation** ⚙️
Quickly verify configuration without parsing logs:
```bash
# Development
curl http://localhost:8000/config

# Returns:
# {
#   "server": {"host": "127.0.0.1", "port": 8000, "debug": true},
#   "paths": {...},
#   "runtime": {"concurrency": 1},
#   "files_exist": {"schema": true, "orchestrator": true, ...}
# }
```

**Example scenario**: CI/CD pipeline wants to verify the test instance is using correct paths before running integration tests.

### 3. **File Existence Checks** 📂
The endpoint includes `files_exist` section:
```json
{
  "files_exist": {
    "schema": true,
    "orchestrator": true,
    "logo": false  // ⚠️ Watermark logo missing!
  }
}
```

**Example scenario**: Job failures with cryptic "file not found" errors. Check `/config` to see which files are missing without SSHing into the server.

### 4. **Path Resolution Debugging** 🔍
See exactly how relative paths resolved:
```json
{
  "paths": {
    "artifacts_root": "/app/artifacts",  // Not /artifacts!
    "jobs_root": "/app/data/jobs",
    "schema_path": "/app/schemas/trp.schema.json"
  }
}
```

**Example scenario**: Volume mounts in Docker aren't working. `/config` shows the service is looking at `/app/artifacts` but your volume is mounted at `/artifacts`.

### 5. **Runtime Configuration Inspection** 🔧
Verify runtime settings without restarting:
```json
{
  "runtime": {
    "concurrency": 4  // Phase-2 scaling enabled
  },
  "server": {
    "debug": false,  // Production mode
    "port": 5000
  }
}
```

**Example scenario**: After deploying Phase-2 with multiple workers, verify `BODAL_CONCURRENCY=4` was actually applied.

### 6. **Load Balancer / Health Check Integration** 🏥
Some load balancers support "deep health checks":
```bash
# Custom health check script
#!/bin/bash
response=$(curl -s http://localhost:8000/config)
concurrency=$(echo $response | jq -r '.runtime.concurrency')
if [ "$concurrency" -eq 4 ]; then
  exit 0  # Healthy
else
  exit 1  # Wrong config, remove from pool
fi
```

**Example scenario**: Canary deployments where you want to verify new instances have the correct configuration before routing traffic.

## Security Model

### Debug Mode Only (403 in Production)
```bash
# Development (BODAL_DEBUG=true)
GET /config → 200 OK + config JSON

# Production (BODAL_DEBUG=false)
GET /config → 403 Forbidden
{
  "error": "Config endpoint only available in debug mode",
  "hint": "Set BODAL_DEBUG=true to enable"
}
```

**Rationale**:
- ✅ **Development**: Full visibility for troubleshooting
- ✅ **Staging**: Can enable debug mode temporarily for investigation
- ✅ **Production**: Disabled by default to prevent information disclosure

### What's Exposed (Debug Mode)
- ✅ Host/port (already visible via network)
- ✅ File paths (relative to app, no secrets)
- ✅ Runtime settings (concurrency)
- ✅ File existence booleans (schema, orchestrator, logo)

### What's NOT Exposed
- ❌ Environment variables
- ❌ API keys or secrets
- ❌ Database credentials
- ❌ File contents
- ❌ User data

## Example Workflows

### Workflow 1: New Deployment Verification
```bash
# 1. Deploy service
kubectl apply -f deployment.yaml

# 2. Port-forward for debugging
kubectl port-forward svc/bodalai 8000:8000

# 3. Check configuration
curl http://localhost:8000/config | jq

# 4. Verify:
#    - All files_exist = true
#    - Paths match expected values
#    - Concurrency is correct
```

### Workflow 2: Troubleshooting Job Failures
```bash
# Job failing with "schema not found"
curl http://service:8000/config | jq '.files_exist.schema'
# Returns: false ❌

# Check what path it's looking for
curl http://service:8000/config | jq '.paths.schema_path'
# Returns: "/wrong/path/trp.schema.json"

# Fix: Update BODAL_SCHEMA_PATH environment variable
```

### Workflow 3: Performance Tuning (Phase-2)
```bash
# Check current concurrency
curl http://localhost:8000/config | jq '.runtime.concurrency'
# Returns: 1

# Update to 4 workers
export BODAL_CONCURRENCY=4
python -m services.api.app

# Verify change applied
curl http://localhost:8000/config | jq '.runtime.concurrency'
# Returns: 4 ✓
```

## Comparison with `/health`

| Feature | `/health` | `/config` |
|---------|-----------|-----------|
| Purpose | Service availability | Configuration inspection |
| Always available | ✅ Yes | ❌ Debug mode only |
| Load balancer use | ✅ Yes | ❌ No |
| Returns | `{"ok": true}` | Full config object |
| Security | Public | Debug-only |

## Implementation Notes

### Response Structure
```typescript
{
  server: {
    host: string,
    port: number,
    debug: boolean
  },
  paths: {
    artifacts_root: string,
    jobs_root: string,
    logs_root: string,
    schema_path: string,
    orchestrator: string,
    logo_default: string
  },
  runtime: {
    concurrency: number
  },
  files_exist: {
    schema: boolean,
    orchestrator: boolean,
    logo: boolean
  }
}
```

### Error Response (Production)
```json
{
  "error": "Config endpoint only available in debug mode",
  "hint": "Set BODAL_DEBUG=true to enable"
}
```

## Future Enhancements (Optional)

1. **Config Diff**: Show what's default vs. overridden
2. **Validation Status**: Include config validation warnings
3. **Last Updated**: Timestamp of config load
4. **Git Info**: Commit hash, branch (for deployment tracking)

## Recommendation

**Yes, implement `/config` endpoint** ✅

**Reasons**:
1. Minimal code (already implemented, ~40 lines)
2. High value for debugging containers
3. Secure (debug-only with 403 in production)
4. No performance impact (simple JSON response)
5. Standard practice (many services have similar endpoints)
6. Helps with Phase-2 scaling (verify concurrency settings)

**When to use**:
- Development: Always enabled
- Staging: Enable for troubleshooting
- Production: Disabled by default, enable temporarily if needed
