import io
import json
from email.message import Message
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from fluidsender_addon.client import FluidSenderClient
from fluidsender_addon.errors import (
    ConnectionFailedError,
    UnauthorizedError,
    ValidationFailedError,
)


def _fake_response(status: int, body: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def _fake_http_error(status: int, body: dict[str, Any]) -> HTTPError:
    return HTTPError(
        url="http://example.test",
        code=status,
        msg="error",
        hdrs=Message(),
        fp=io.BytesIO(json.dumps(body).encode("utf-8")),
    )


@pytest.fixture
def client() -> FluidSenderClient:
    return FluidSenderClient("http://fluidsender.local:3000", "fst_token")


def test_upload_success(client: FluidSenderClient) -> None:
    body = {"ok": True, "file": {"path": "jobs/panels/part1.nc", "size": 123, "uploadedAt": 42}}
    with patch("fluidsender_addon.client.urllib_request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response(200, body)
        result = client.upload(b"G0 X0\n", "part1.nc", folder="jobs/panels")

    assert result.ok is True
    assert result.file.path == "jobs/panels/part1.nc"
    assert result.file.size == 123
    assert result.load is None

    sent_request = mock_urlopen.call_args[0][0]
    assert sent_request.full_url == "http://fluidsender.local:3000/api/external/v1/upload"
    assert sent_request.get_header("Authorization") == "Bearer fst_token"
    assert sent_request.get_header("Content-type").startswith("multipart/form-data; boundary=")
    assert b"part1.nc" in sent_request.data
    assert b"G0 X0" in sent_request.data


def test_upload_with_load_reports_partial_failure(client: FluidSenderClient) -> None:
    body = {
        "ok": True,
        "file": {"path": "jobs/panels/part1.nc", "size": 123, "uploadedAt": 42},
        "load": {"ok": False, "code": "FORBIDDEN", "message": "Token lacks Allow Load"},
    }
    with patch("fluidsender_addon.client.urllib_request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response(200, body)
        result = client.upload(b"G0 X0\n", "part1.nc", load=True)

    assert result.ok is True
    assert result.load is not None
    assert result.load.ok is False
    assert result.load.code == "FORBIDDEN"


def test_upload_unauthorized_raises(client: FluidSenderClient) -> None:
    error_body = {"error": {"code": "UNAUTHORIZED", "message": "Missing token"}}
    with patch("fluidsender_addon.client.urllib_request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _fake_http_error(401, error_body)
        with pytest.raises(UnauthorizedError) as excinfo:
            client.upload(b"G0 X0\n", "part1.nc")

    assert excinfo.value.code == "UNAUTHORIZED"
    assert excinfo.value.http_status == 401


def test_upload_validation_failed_raises(client: FluidSenderClient) -> None:
    error_body = {"error": {"code": "VALIDATION_FAILED", "message": "File over 100 MB"}}
    with patch("fluidsender_addon.client.urllib_request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _fake_http_error(413, error_body)
        with pytest.raises(ValidationFailedError):
            client.upload(b"G0 X0\n", "part1.nc")


def test_connection_error_wrapped(client: FluidSenderClient) -> None:
    with patch("fluidsender_addon.client.urllib_request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = URLError("connection refused")
        with pytest.raises(ConnectionFailedError):
            client.upload(b"G0 X0\n", "part1.nc")


def test_list_folder(client: FluidSenderClient) -> None:
    body = {
        "ok": True,
        "folders": [
            {"type": "folder", "name": "archive", "path": "jobs/panels/archive", "childCount": 4}
        ],
        "files": [
            {
                "type": "file",
                "name": "part1.nc",
                "path": "jobs/panels/part1.nc",
                "size": 48213,
                "uploadedAt": 1737310000000,
                "isNc": True,
                "lastExecution": None,
                "totalSuccessful": 0,
                "totalFailed": 0,
            }
        ],
    }
    with patch("fluidsender_addon.client.urllib_request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response(200, body)
        listing = client.list_folder("jobs/panels")

    assert len(listing.folders) == 1
    assert listing.folders[0].path == "jobs/panels/archive"
    assert len(listing.files) == 1
    assert listing.files[0].name == "part1.nc"

    sent_request = mock_urlopen.call_args[0][0]
    assert sent_request.full_url == (
        "http://fluidsender.local:3000/api/external/v1/folders?folder=jobs/panels"
    )


def test_list_folder_empty_defaults(client: FluidSenderClient) -> None:
    body = {"ok": True, "folders": [], "files": []}
    with patch("fluidsender_addon.client.urllib_request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response(200, body)
        listing = client.list_folder()

    assert listing.folders == []
    assert listing.files == []
    sent_request = mock_urlopen.call_args[0][0]
    assert sent_request.full_url == "http://fluidsender.local:3000/api/external/v1/folders"


def test_create_folder(client: FluidSenderClient) -> None:
    body = {"ok": True, "folder": "jobs/panels/archive"}
    with patch("fluidsender_addon.client.urllib_request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _fake_response(200, body)
        result = client.create_folder("jobs/panels/archive")

    assert result == "jobs/panels/archive"
    sent_request = mock_urlopen.call_args[0][0]
    assert sent_request.get_header("Content-type") == "application/json"
    assert json.loads(sent_request.data) == {"folder": "jobs/panels/archive"}
