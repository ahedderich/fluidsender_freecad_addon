"""Client-side mirror of the FluidSender external API's filename/folder rules.

Per external-api.md: "Folder and filename characters: both are restricted to
letters, digits, ``.``, ``_``, and ``-``. Any other character (including ``/``
inside a filename) is replaced with ``_``." The server sanitizes silently
rather than rejecting -- these helpers let the UI preview the sanitized result
before upload, so what the user typed and what lands on the server match.
"""

from __future__ import annotations

import re

_DISALLOWED = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(name: str) -> str:
    """Sanitize a single filename component (no path separators allowed)."""
    return _DISALLOWED.sub("_", name)


def sanitize_folder(path: str) -> str:
    """Sanitize a folder path, treating ``/`` as a segment separator.

    Each segment is sanitized independently with the same character rule as
    a filename; empty segments (leading/trailing/duplicate slashes) are
    dropped so the result matches the server's normalized ``folder`` path.
    """
    segments = [sanitize_filename(segment) for segment in path.split("/") if segment]
    return "/".join(segments)
