"""Wires InstanceStore up to FreeCAD's real (plaintext) preference storage.

Only importable inside FreeCAD's bundled interpreter -- kept separate from
config.py so config.py itself stays testable outside FreeCAD.
"""

from __future__ import annotations

import FreeCAD

from .config import InstanceStore

PREFERENCES_ROOT = "User parameter:BaseApp/Preferences/Mod/FluidSender"


def default_instance_store() -> InstanceStore:
    root = FreeCAD.ParamGet(PREFERENCES_ROOT)
    return InstanceStore(root)
