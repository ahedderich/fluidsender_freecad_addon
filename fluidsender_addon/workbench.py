"""Minimal, always-available FluidSender workbench.

Guaranteed fallback entry point for FluidSender_PostAndSend in case the
best-effort CAM toolbar injection (toolbar_injection.py) fails or breaks
against a future FreeCAD/CAM version -- see the "FreeCAD API stability" note
in the project CLAUDE.md. Selecting this workbench always makes the command
reachable via its own toolbar/menu, independent of CAM internals.
"""

from __future__ import annotations

import os

import FreeCADGui

from . import commands

_ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(_ADDON_ROOT, "Resources", "icons", "fluidsender.svg")


class FluidSenderWorkbench(FreeCADGui.Workbench):
    MenuText = "FluidSender"
    ToolTip = "Upload CAM post-processor output to a FluidSender server"
    Icon = ICON_PATH

    def Initialize(self) -> None:
        commands.register_commands()
        self.appendToolbar("FluidSender", commands.COMMAND_NAMES)
        self.appendMenu("FluidSender", commands.COMMAND_NAMES)

    def Activated(self) -> None:
        pass

    def Deactivated(self) -> None:
        pass

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"
