"""HTTP client for the FluidSender external API (see external-api.md).

Deliberately stdlib-only (``urllib.request``) and free of FreeCAD/Qt imports so
it can be unit tested with plain pytest -- see the project CLAUDE.md's note
that FreeCAD's ``requests`` availability isn't guaranteed across
distributions, and FreeCAD's own Addon Manager uses ``urllib.request`` for the
same reason.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .errors import ConnectionFailedError, FluidSenderError, error_for_code

DEFAULT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class FileInfo:
    path: str
    size: int
    uploaded_at: int


@dataclass(frozen=True)
class LoadResult:
    ok: bool
    code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class UploadResult:
    ok: bool
    file: FileInfo
    load: LoadResult | None = None


@dataclass(frozen=True)
class FolderEntry:
    name: str
    path: str
    child_count: int


@dataclass(frozen=True)
class FileEntry:
    name: str
    path: str
    size: int
    uploaded_at: int
    is_nc: bool
    last_execution: object | None
    total_successful: int
    total_failed: int


@dataclass(frozen=True)
class FolderListing:
    folders: list[FolderEntry]
    files: list[FileEntry]


def _encode_multipart(
    fields: dict[str, str], file_field: tuple[str, str, bytes]
) -> tuple[bytes, str]:
    """Build a multipart/form-data body. Returns (body, content_type)."""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    file_name, content_type, content = file_field
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
    )
    parts.append(content)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class FluidSenderClient:
    def __init__(self, base_url: str, token: str, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _open(self, req: urllib_request.Request) -> tuple[int, bytes]:
        try:
            with urllib_request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib_error.HTTPError as exc:
            return exc.code, exc.read()
        except urllib_error.URLError as exc:
            raise ConnectionFailedError(
                f"Could not reach FluidSender server at {self.base_url}: {exc.reason}"
            ) from exc

    def _parse_or_raise(self, status: int, body: bytes) -> dict[str, Any]:
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            if status >= 400:
                raise FluidSenderError(
                    f"Unexpected non-JSON error response (HTTP {status})", http_status=status
                ) from exc
            raise FluidSenderError(
                f"Unexpected non-JSON response (HTTP {status})", http_status=status
            ) from exc

        if status >= 400 or not data.get("ok", True):
            err = data.get("error", {})
            raise error_for_code(
                err.get("code"), err.get("message", f"HTTP {status}"), http_status=status
            )
        return data

    def upload(
        self,
        content: bytes,
        filename: str,
        folder: str | None = None,
        load: bool = False,
    ) -> UploadResult:
        fields: dict[str, str] = {"filename": filename}
        if folder:
            fields["folder"] = folder
        if load:
            fields["load"] = "true"

        body, content_type = _encode_multipart(fields, (filename, "text/plain", content))
        req = urllib_request.Request(
            f"{self.base_url}/api/external/v1/upload",
            data=body,
            method="POST",
            headers={**self._headers(), "Content-Type": content_type},
        )
        status, raw = self._open(req)
        data = self._parse_or_raise(status, raw)

        file_data = data["file"]
        load_data = data.get("load")
        return UploadResult(
            ok=data["ok"],
            file=FileInfo(
                path=file_data["path"], size=file_data["size"], uploaded_at=file_data["uploadedAt"]
            ),
            load=(
                LoadResult(
                    ok=load_data["ok"], code=load_data.get("code"), message=load_data.get("message")
                )
                if load_data is not None
                else None
            ),
        )

    def list_folder(self, folder: str | None = None) -> FolderListing:
        url = f"{self.base_url}/api/external/v1/folders"
        if folder:
            from urllib.parse import quote

            url = f"{url}?folder={quote(folder)}"
        req = urllib_request.Request(url, method="GET", headers=self._headers())
        status, raw = self._open(req)
        data = self._parse_or_raise(status, raw)

        return FolderListing(
            folders=[
                FolderEntry(name=f["name"], path=f["path"], child_count=f["childCount"])
                for f in data.get("folders", [])
            ],
            files=[
                FileEntry(
                    name=f["name"],
                    path=f["path"],
                    size=f["size"],
                    uploaded_at=f["uploadedAt"],
                    is_nc=f["isNc"],
                    last_execution=f.get("lastExecution"),
                    total_successful=f["totalSuccessful"],
                    total_failed=f["totalFailed"],
                )
                for f in data.get("files", [])
            ],
        )

    def create_folder(self, folder: str) -> str:
        body = json.dumps({"folder": folder}).encode("utf-8")
        req = urllib_request.Request(
            f"{self.base_url}/api/external/v1/folders",
            data=body,
            method="POST",
            headers={**self._headers(), "Content-Type": "application/json"},
        )
        status, raw = self._open(req)
        data = self._parse_or_raise(status, raw)
        return str(data["folder"])
