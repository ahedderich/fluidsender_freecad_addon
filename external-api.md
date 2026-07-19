# FluidSender External API

A small HTTP API for third-party tools (e.g. a CAM post-processor) to store GCode files
on a FluidSender server and, optionally, load them as the active job — without needing
any FluidSender source code knowledge.

This API is separate from the browser UI and from FluidSender's session login
(`auth.enabled`). It has its own authentication (a bearer token, see below) and is
scoped to exactly three endpoints: upload a file, list a folder, create a folder.
It cannot manage users, change settings, control the machine directly, or do anything
outside the `uploads/` file tree.

## Authentication

Every request must include an `Authorization` header with a bearer token:

```
Authorization: Bearer fst_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Generate a token in the FluidSender UI under **Settings → Authentication → Generate API
Token**. The raw token is shown **exactly once**, at creation time — FluidSender only
ever stores a one-way hash of it. If you lose it, revoke it and generate a new one.

A token can optionally be granted **Allow Load**. Without it, the token can store and
browse files but the `load` option on the upload endpoint will always fail with
`FORBIDDEN` — this lets you issue a token to a tool you trust to send files, without
also letting it start the machine.

Requests without a valid token receive `401` with `error.code: "UNAUTHORIZED"`.

## Base URL

All endpoints are relative to your FluidSender server, e.g. `http://<host>:<port>/api/external/v1/...`.
There is no CORS configuration for this API — it's meant to be called server-to-server
or from a desktop application (like a CAM tool), not from a browser page on another origin.

## Error format

Any failure (validation, storage, auth) responds with a non-2xx HTTP status and this
JSON body:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "A human-readable description of what went wrong"
  }
}
```

| Code | Typical HTTP status | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing/invalid/revoked bearer token |
| `VALIDATION_FAILED` | 400 / 413 | Missing or malformed parameters, path escapes the uploads folder, file over 100 MB |
| `STORAGE_FAILED` | 500 | Could not write the file or create the folder on disk |

`code` is stable and meant to be matched on programmatically; `message` is for logs/humans
and may change wording over time.

The **upload** endpoint has one more layer: if you ask it to also load the file, the load
outcome is reported separately inside the (still-200) response body, not as an HTTP error —
see below.

## 1. Upload a file — `POST /api/external/v1/upload`

`multipart/form-data` with these parts:

| Field | Required | Description |
|---|---|---|
| `file` | yes | The file contents. |
| `folder` | no | Folder path to store into, e.g. `"jobs/panels"`. Defaults to the uploads root. Created automatically if it doesn't exist. |
| `filename` | no | Name to store the file as. Falls back to the uploaded file's own filename if omitted. |
| `load` | no | Send the literal string `"true"` to also load the file as the active job after storing it. Anything else (or omitted) means "just store it". |

**Folder and filename characters:** both are restricted to letters, digits, `.`, `_`,
and `-`. Any other character (including `/` inside a filename) is replaced with `_`.
Build the exact path you want segment-by-segment in `folder` rather than relying on
unusual characters surviving.

**Overwrite behavior:** storing to the same `folder` + `filename` as an existing file
**overwrites it in place**. There is no versioning or renaming-on-conflict. Overwriting
resets that file's stored stats (last execution result, success/fail counts) — the file
is treated as new content, even if the name is unchanged.

### Success response — `200`

```json
{
  "ok": true,
  "file": { "path": "jobs/panels/part1.nc", "size": 48213, "uploadedAt": 1737310000000 }
}
```

`file.path` is the path you'll use in later calls (e.g. as `folder` for a subsequent
listing). `uploadedAt` is a millisecond epoch timestamp.

### With `load: "true"`

The response gains a `load` object. The file is **always stored first**, regardless of
whether the load step succeeds — check `load.ok` independently of the top-level `ok`:

```json
{
  "ok": true,
  "file": { "path": "jobs/panels/part1.nc", "size": 48213, "uploadedAt": 1737310000000 },
  "load": { "ok": true }
}
```

If loading didn't happen, `load.ok` is `false` and `load.code` explains why. The file
is still stored on disk either way.

```json
{
  "ok": true,
  "file": { "path": "jobs/panels/part1.nc", "size": 48213, "uploadedAt": 1737310000000 },
  "load": {
    "ok": false,
    "code": "JOB_BUSY",
    "message": "Cannot load a job while one is running. Pause or cancel first."
  }
}
```

| `load.code` | Meaning |
|---|---|
| `FORBIDDEN` | This token doesn't have "Allow Load" enabled. |
| `JOB_BUSY` | A job is currently running/pausing/stopping on the server — matches the same rule the browser UI enforces (you can't swap the active file mid-job). |
| `LOAD_FAILED` | The file was stored, but FluidSender couldn't load it (e.g. GCode analysis failed). `load.message` has the underlying reason. |

### curl example

```bash
curl -X POST "http://fluidsender.local:3000/api/external/v1/upload" \
  -H "Authorization: Bearer fst_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -F "folder=jobs/panels" \
  -F "filename=part1.nc" \
  -F "load=true" \
  -F "file=@/path/to/part1.nc"
```

### Python example

```python
import requests

resp = requests.post(
    "http://fluidsender.local:3000/api/external/v1/upload",
    headers={"Authorization": "Bearer fst_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"},
    data={"folder": "jobs/panels", "filename": "part1.nc", "load": "true"},
    files={"file": ("part1.nc", open("part1.nc", "rb"), "text/plain")},
    timeout=30,
)
resp.raise_for_status()
body = resp.json()
if not body.get("load", {}).get("ok", True):
    print("Stored but not loaded:", body["load"]["code"], body["load"]["message"])
```

## 2. List a folder — `GET /api/external/v1/folders`

Query parameter `folder` (optional, defaults to the uploads root) — lists the immediate
contents of that folder (not recursive). Use this to build a folder picker so a user can
choose where an upload should go.

```
GET /api/external/v1/folders?folder=jobs/panels
```

### Response — `200`

```json
{
  "ok": true,
  "folders": [
    { "type": "folder", "name": "archive", "path": "jobs/panels/archive", "childCount": 4 }
  ],
  "files": [
    {
      "type": "file",
      "name": "part1.nc",
      "path": "jobs/panels/part1.nc",
      "size": 48213,
      "uploadedAt": 1737310000000,
      "isNc": true,
      "lastExecution": null,
      "totalSuccessful": 0,
      "totalFailed": 0
    }
  ]
}
```

Listing a folder that doesn't exist returns empty `folders`/`files` arrays rather than
an error.

### curl example

```bash
curl "http://fluidsender.local:3000/api/external/v1/folders?folder=jobs/panels" \
  -H "Authorization: Bearer fst_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

## 3. Create a folder — `POST /api/external/v1/folders`

JSON body:

```json
{ "folder": "jobs/panels/archive" }
```

Creates the folder (and any missing parent folders) if it doesn't already exist; no
error if it already does.

### Response — `200`

```json
{ "ok": true, "folder": "jobs/panels/archive" }
```

`folder` in the response is the sanitized path actually created — compare it against
what you sent if you need to confirm no characters were stripped.

### curl example

```bash
curl -X POST "http://fluidsender.local:3000/api/external/v1/folders" \
  -H "Authorization: Bearer fst_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"folder": "jobs/panels/archive"}'
```

## Typical integration flow

1. Call `GET /api/external/v1/folders` (starting with no `folder`, i.e. the root) to let
   the user browse/pick a destination, following `folders[].path` to descend.
2. Optionally call `POST /api/external/v1/folders` if the user wants to create a new
   folder from within that picker.
3. Call `POST /api/external/v1/upload` with the chosen `folder`, a `filename`, and
   `load: "true"` if the tool should also start the job immediately.
