# API Usage Guide

This guide provides cURL examples for interacting with the BodalAI API.

## 1. Create a Job (POST /jobs)

Submit a TRP payload to create a new rendering job.

### A) Valid Free Tier Job
```bash
curl -sS -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d @examples/trp/trp_free_valid.json | jq
```

**Expected Response (201 Created):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "links": {
    "self": "/jobs/550e8400-e29b-41d4-a716-446655440000",
    "artifacts": "/artifacts/550e8400-e29b-41d4-a716-446655440000/"
  }
}
```

### B) Error: Non-JSON Body
```bash
curl -sS -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: text/plain" \
  --data-binary "not-json" | jq
```

**Expected Response (415 Unsupported Media Type):**
```json
{
  "error": "json required",
  "code": "UNSUPPORTED_MEDIA_TYPE"
}
```

### C) Error: Missing user_tier
```bash
curl -sS -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"goal": "render an intro"}' | jq
```

**Expected Response (400 Bad Request):**
```json
{
  "error": "missing 'user_tier' in TRP",
  "code": "BAD_REQUEST"
}
```

## 2. Poll Job Status (GET /jobs/<job_id>)

Check the status of a job and retrieve artifact links.

### A) Poll Status
```bash
JOB_ID=<paste uuid>
curl -sS -X GET http://127.0.0.1:8000/jobs/$JOB_ID | jq
```

**Expected Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "project_id": null,
  "tier": "free",
  "created_ts": 1732377000.0,
  "started_ts": 1732377005.0,
  "finished_ts": null,
  "error": null,
  "artifacts": {},
  "links": {
    "self": "/jobs/550e8400-e29b-41d4-a716-446655440000"
  }
}
```
*Note: Once the job succeeds, `status` will be "succeeded" and `artifacts` will contain links to the generated files.*

## 3. Download Artifacts (GET /artifacts/<job_id>/<filename>)

Stream generated artifacts directly.

### A) Download Video
```bash
JOB_ID=<uuid>
curl -sS -o out.mp4 http://127.0.0.1:8000/artifacts/$JOB_ID/out.mp4
```

### B) Download Thumbnail
```bash
curl -sS -o out.jpg http://127.0.0.1:8000/artifacts/$JOB_ID/out.jpg
```

### C) Fetch Metadata
```bash
curl -sS http://127.0.0.1:8000/artifacts/$JOB_ID/meta.json | jq
```

### D) Fetch Logs
```bash
curl -sS http://127.0.0.1:8000/artifacts/$JOB_ID/run.log
```

### E) Error Examples
**Invalid UUID:**
```bash
curl -sS http://127.0.0.1:8000/artifacts/not-a-uuid/out.mp4 | jq
# -> 400 {"error":"invalid job_id","code":"BAD_REQUEST"}
```

**Invalid Filename:**
```bash
curl -sS http://127.0.0.1:8000/artifacts/$JOB_ID/foo.mp4 | jq
# -> 400 {"error":"invalid filename","code":"BAD_REQUEST"}
```
