"""In-process memory of the last folder/filename/operation-selection used in
the post-process dialog, so reopening it within the same FreeCAD session
prefills them for quickly re-uploading to the same target.

Deliberately NOT backed by FreeCAD's ParamGet-based InstanceStore (see
config.py/freecad_prefs.py) -- that persists to disk across FreeCAD restarts,
which this explicitly should not. Plain Python, no FreeCAD/Qt import, so it's
testable; global/non-scoped by design (one remembered folder, filename, and
operation selection for the whole session, not per-instance or per-Job).

`last_unchecked_operation_names` stores the *excluded* names, not the checked
ones, so an operation the dialog has never seen before (a new op, or a
different Job's op that happens to share a name) defaults to checked --
matching the dialog's original default-all-checked behavior -- rather than
silently defaulting to excluded. Because this is name-matched and non-scoped,
switching to a Job that reuses an operation name (e.g. "Profile") from a
previous Job will carry over that name's checked state; this is the explicit
trade-off of "global, not per-Job" memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DialogSessionState:
    last_folder: str = ""
    last_filename: str | None = None
    last_unchecked_operation_names: set[str] = field(default_factory=set)


session_state = DialogSessionState()
