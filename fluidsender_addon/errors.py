"""Typed exceptions mirroring the FluidSender external API's error.code values.

See external-api.md "Error format": every non-2xx response is
``{"error": {"code": ..., "message": ...}}`` with a stable ``code`` meant to be
matched on programmatically.
"""

from __future__ import annotations


class FluidSenderError(Exception):
    """Base class for all errors raised by FluidSenderClient."""

    def __init__(self, message: str, *, code: str | None = None, http_status: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


class UnauthorizedError(FluidSenderError):
    """401 UNAUTHORIZED -- missing/invalid/revoked bearer token."""


class ValidationFailedError(FluidSenderError):
    """400/413 VALIDATION_FAILED -- bad parameters, escaping path, or file too large."""


class StorageFailedError(FluidSenderError):
    """500 STORAGE_FAILED -- server could not write the file/folder to disk."""


class ConnectionFailedError(FluidSenderError):
    """The request never reached the server (DNS, refused, timeout, TLS, ...)."""


_CODE_TO_EXCEPTION: dict[str, type[FluidSenderError]] = {
    "UNAUTHORIZED": UnauthorizedError,
    "VALIDATION_FAILED": ValidationFailedError,
    "STORAGE_FAILED": StorageFailedError,
}


def error_for_code(code: str | None, message: str, http_status: int | None) -> FluidSenderError:
    exception_cls = _CODE_TO_EXCEPTION.get(code or "", FluidSenderError)
    return exception_cls(message, code=code, http_status=http_status)
