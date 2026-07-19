"""Bridge between checked CAM operations and FreeCAD's Path post-processor.

Filtering to a subset of operations turns out to have no single API that
works across FreeCAD versions -- two approaches were tried and confirmed
against a real FreeCAD 1.1.1 install (2026-07-19) before landing on this one:

1. Passing ``{"job": job, "operations": operations}`` into
   ``PostProcessorFactory.get_post_processor()`` -- the same trick FreeCAD's
   own "Post Process Selected" command (``Path/Post/Command.py``,
   ``CommandPathPostSelected``) uses on the ``main`` branch. On 1.1.1 this
   hits an upstream ordering bug in ``PostProcessor.__init__``: it resolves
   ``self._machine`` from ``self._job`` *before* unwrapping the dict into the
   real Job, and later fails with ``AttributeError: 'dict' object has no
   attribute 'Fixtures'``.
2. Constructing with the plain Job (avoiding bug 1) and then setting
   ``postprocessor._operations`` directly. This avoids the crash, but is
   silently a no-op on 1.1.1: its actual installed ``PostProcessor._buildPostList()``
   (confirmed by reading the real installed source via FreeCAD's Python
   console) always does ``for obj in self._job.Operations.Group:`` in every
   ``OrderOutputBy`` branch (Fixture/Tool/Operation) and never reads
   ``self._operations`` at all -- there is no ``Path.Post.PostList`` module on
   1.1.1 either, so that's a ``main``-branch-only mechanism.

Since every ordering branch of ``_buildPostList()`` reads operations through
``self._job.Operations.Group``, the version-independent fix is to not filter
via any postprocessor-internal attribute at all, and instead wrap the real
Job behind a thin proxy that overrides just ``.Operations.Group`` to return
the filtered list, forwarding every other attribute (``.Fixtures``,
``.OrderOutputBy``, ``.PostProcessorArgs``, ``.SplitOutput``,
``.PostProcessorOutputFile``, ``.Stock``, ``.SetupSheet``, ``.Machine`` if
present, ...) straight through to the real Job. We still also set
``postprocessor._operations`` as a harmless, cost-free extra in case a future
FreeCAD version (or the ``main``-branch ``Path.Post.PostList`` refactor, once
it ships) reads that instead.

CAM's post-processor internals have already had breaking changes across
versions (FreeCAD#26006, "Custom post processors fail in v1.2"); re-verify
this module against whatever FreeCAD version the addon actually runs under,
per the "FreeCAD API stability" note in the project CLAUDE.md.

Known limitation, shared with FreeCAD's own CommandPathPostSelected: the
post-processor name is always resolved from ``job.PostProcessor`` (the
pre-1.2 "legacy" flow). Jobs using the newer Machine-based flow (``job.Machine``
set) may not resolve correctly here -- upstream's own "Post Process Selected"
command has the same gap on ``main``, it does not special-case that flow either.
"""

from __future__ import annotations

import Path
from Path.Post.Processor import PostProcessorFactory


class PostProcessingError(Exception):
    """Raised for any failure turning selected operations into GCode text."""


class _FilteredOperationsGroup:
    """Duck-types Job.Operations, but with a filtered .Group list."""

    def __init__(self, real_operations, filtered_group: list):
        self._real_operations = real_operations
        self.Group = filtered_group

    def __getattr__(self, name):
        return getattr(self._real_operations, name)


class _FilteredJobProxy:
    """Wraps a real CAM Job so `.Operations.Group` yields only `operations`.

    Every other attribute is forwarded to the real Job unchanged. See the
    module docstring for why this is the version-independent way to restrict
    which operations a FreeCAD Path postprocessor includes.
    """

    def __init__(self, real_job, operations: list):
        self._real_job = real_job
        self.Operations = _FilteredOperationsGroup(real_job.Operations, operations)

    def __getattr__(self, name):
        return getattr(self._real_job, name)


def _resolve_post_processor_name(job) -> str:
    name = job.PostProcessor or Path.Preferences.defaultPostProcessor()
    if not name:
        raise PostProcessingError(
            f'Job "{job.Label}" has no post processor assigned, and no default '
            "post processor is configured in FreeCAD's CAM preferences."
        )
    return name


def build_gcode(job, operations: list) -> str:
    """Post-process only `operations` (a subset of job.Operations.Group) and
    return the combined GCode text -- nothing is written to disk here."""
    if not operations:
        raise PostProcessingError("No operations selected.")

    postprocessor_name = _resolve_post_processor_name(job)
    proxy_job = _FilteredJobProxy(job, operations)

    postprocessor = PostProcessorFactory.get_post_processor(proxy_job, postprocessor_name)
    if isinstance(postprocessor, Exception):
        raise PostProcessingError(str(postprocessor)) from postprocessor

    # Harmless on versions that don't read it; see module docstring.
    postprocessor._operations = operations

    try:
        post_data = postprocessor.export()
    except Exception as exc:
        raise PostProcessingError(
            f"Post processor '{postprocessor_name}' failed: {exc}"
        ) from exc

    if not post_data:
        raise PostProcessingError(f"Post processor '{postprocessor_name}' produced no output.")

    sections = [gcode for _subpart, gcode in post_data if gcode is not None]
    if not sections:
        raise PostProcessingError(f"Post processor '{postprocessor_name}' produced no GCode.")

    return "\n".join(sections)
