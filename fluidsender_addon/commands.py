"""Registers the FluidSender FreeCAD command(s)."""

from __future__ import annotations

import FreeCAD
import FreeCADGui
from PathScripts import PathUtils

POST_AND_SEND_COMMAND = "FluidSender_PostAndSend"
COMMAND_NAMES = [POST_AND_SEND_COMMAND]


class PostAndSendCommand:
    def GetResources(self) -> dict:
        return {
            "Pixmap": "fluidsender",
            "MenuText": "Post Process && Send to FluidSender",
            "ToolTip": (
                "Post-process the selected CAM Job's operations and upload "
                "the resulting GCode to a FluidSender server"
            ),
        }

    def IsActive(self) -> bool:
        selection = FreeCADGui.Selection.getSelection()
        if not selection:
            return False
        return PathUtils.findParentJob(selection[0]) is not None

    def Activated(self) -> None:
        selection = FreeCADGui.Selection.getSelection()
        job = PathUtils.findParentJob(selection[0]) if selection else None
        if job is None:
            FreeCAD.Console.PrintError(
                "FluidSender: select a CAM Job (or one of its operations) first.\n"
            )
            return

        from .gui.post_process_dialog import PostProcessDialog

        dialog = PostProcessDialog(job, parent=FreeCADGui.getMainWindow())
        dialog.exec_()


def register_commands() -> None:
    if POST_AND_SEND_COMMAND not in FreeCADGui.listCommands():
        FreeCADGui.addCommand(POST_AND_SEND_COMMAND, PostAndSendCommand())
