"""FreeCAD addon entry point for FluidSender Upload.

Executed by FreeCAD at startup for every addon folder under Mod/. Registers
the FluidSender command and its own always-available workbench (the
guaranteed fallback -- see workbench.py), then best-effort injects the same
command into the CAM workbench's toolbar so it's reachable without switching
workbenches. That injection is not a stable public API (see
toolbar_injection.py's docstring and the "FreeCAD API stability" note in the
project CLAUDE.md), so it's wrapped defensively: a failure there must never
block FreeCAD startup or leave the addon with no way to reach the command.

``Gui`` (and the ``Workbench`` base class used inside workbench.py) is a
pre-bound global in InitGui.py's execution context (see FreeCAD's "Workbench
Creation" documentation) -- ``FreeCAD`` itself is not and must still be
imported explicitly, matching the convention used by e.g. the Lattice2
addon's InitGui.py.
"""

import FreeCAD

try:
    from fluidsender_addon import commands
    from fluidsender_addon.gui.preferences import FluidSenderPreferencesPage
    from fluidsender_addon.workbench import FluidSenderWorkbench

    commands.register_commands()
    Gui.addWorkbench(FluidSenderWorkbench())  # noqa: F821 -- Gui is injected by FreeCAD's loader
    Gui.addPreferencePage(FluidSenderPreferencesPage, "FluidSender")  # noqa: F821
except Exception as exc:
    FreeCAD.Console.PrintError(f"FluidSender: failed to initialize addon: {exc}\n")
else:
    try:
        from fluidsender_addon.toolbar_injection import inject_cam_toolbar

        inject_cam_toolbar(commands.COMMAND_NAMES)
    except Exception as exc:
        FreeCAD.Console.PrintWarning(
            f"FluidSender: could not add a button to the CAM workbench toolbar "
            f"({exc}); use the FluidSender workbench instead.\n"
        )
