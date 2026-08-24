# Artifacts

Python analysis commonly produces files rather than only text: plots, CSV, XLSX, JSON, PDF, HTML and reports.

## Phase 1 flow

```text
Python
  ↓
workspace file
  ↓
execution result detects added/changed file
  ↓
artifact metadata
  ↓
get_file_url
  ↓
HTTP retrieval
```

Artifact metadata includes path, size and MIME type.

Phase 1 uses deterministic HMAC-signed URLs. Later profiles should use opaque and/or expiring URLs and enforce user/workspace authorization independently of Python execution.

## Important boundary

Python writes ordinary workspace files. The MCP server owns authorization and HTTP retrieval. Python code must not be responsible for serving artifacts.
