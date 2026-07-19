"""Inject the FluidSender command into the CAM workbench's toolbar.

Technique: write directly into the parameter tree FreeCAD's own
"Customize > Toolbars" dialog uses (``User parameter:BaseApp/Workbench/<wb>/Toolbar``)
rather than hooking ``Workbench.Activated()`` at runtime. This is the same
mechanism the Lattice2 addon uses to inject a toolbar into PartDesign
(see lattice2InjectedToolbars.py in the Lattice2 repository) -- it does not
require the target workbench to have been activated yet, and does not depend
on undocumented ``Gui.getWorkbench().appendToolbar()`` runtime behaviour.

This still relies on CAM's internal workbench identifier ("CAMWorkbench") and
on FreeCAD's toolbar-customization parameter layout, neither of which are a
stable public API -- see the "FreeCAD API stability" note in the project
CLAUDE.md. Callers must guard this in a try/except so a failure here never
blocks FreeCAD startup; the FluidSender workbench (fluidsender_addon/workbench.py)
is the guaranteed fallback entry point if injection fails or the target
workbench identifier changes in a future FreeCAD version.
"""

from __future__ import annotations

import FreeCAD as App

CAM_WORKBENCH = "CAMWorkbench"
GROUP_NAME = "FluidSender"
GROUP_LABEL = "FluidSender"


def _find_toolbar_group(
    workbench: str, name: str, label: str, create: bool = False
) -> tuple[str, str] | None:
    """Find (or allocate) the parameter group for a named toolbar.

    Mirrors Lattice2's ``findToolbar()``: first look for a group already using
    our internal name, then for a "Custom_N" group a user may have created by
    hand through the Customize dialog with a matching label (so we don't
    create a duplicate toolbar), then optionally allocate our own name.
    """
    root = f"User parameter:BaseApp/Workbench/{workbench}/Toolbar"
    pp = App.ParamGet(root)
    if pp.HasGroup(name):
        return root, name
    for i in range(10):
        candidate = f"Custom_{i}"
        if pp.HasGroup(candidate) and pp.GetGroup(candidate).GetString("Name") == label:
            return root, candidate
    if create:
        return root, name
    return None


def inject_cam_toolbar(command_names: list[str]) -> bool:
    """Register our toolbar group in the CAM workbench's persisted layout.

    Safe to call every time FreeCAD starts: only sets the toolbar's default
    visibility ("Active") the first time it's created, so it won't override a
    user who has since hidden it via Customize.

    Returns True if the toolbar group was written, False if it already existed
    unchanged (still success -- just nothing new to do).
    """
    already_registered = _find_toolbar_group(CAM_WORKBENCH, GROUP_NAME, GROUP_LABEL) is not None
    location = _find_toolbar_group(CAM_WORKBENCH, GROUP_NAME, GROUP_LABEL, create=True)
    assert location is not None
    group = App.ParamGet("/".join(location))
    group.SetString("Name", GROUP_LABEL)
    for name in command_names:
        group.SetString(name, "FreeCAD")
    if not already_registered:
        group.SetBool("Active", True)
    return True
