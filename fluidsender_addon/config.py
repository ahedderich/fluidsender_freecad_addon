"""Storage for configured FluidSender instances.

Kept free of FreeCAD imports so it's testable with plain pytest: the actual
parameter tree is accessed through the minimal ``ParameterGroup`` duck-typed
interface below, which FreeCAD's own ``ParameterGrp`` objects (returned by
``FreeCAD.ParamGet(...)``) already satisfy (GetString/SetString/GetBool/
SetBool/GetGroups/GetGroup/RemGroup/HasGroup). See freecad_prefs.py for the
thin factory that wires this up to real FreeCAD preferences -- preferences
there are plaintext (``user.cfg``), so tokens are not encrypted at rest; the
preferences UI should say so explicitly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


class ParameterGroup(Protocol):
    def GetString(self, key: str, default: str = "") -> str: ...
    def SetString(self, key: str, value: str) -> None: ...
    def GetGroups(self) -> list[str]: ...
    def GetGroup(self, name: str) -> ParameterGroup: ...
    def RemGroup(self, name: str) -> None: ...
    def HasGroup(self, name: str) -> bool: ...


@dataclass
class InstanceConfig:
    id: str
    label: str
    url: str
    token: str


def new_instance_id() -> str:
    return uuid.uuid4().hex


class InstanceStore:
    """Reads/writes the list of configured FluidSender instances and which
    one was last selected, under a single root ParameterGroup."""

    _INSTANCES_GROUP = "Instances"
    _LAST_SELECTED_KEY = "LastSelectedInstanceId"

    def __init__(self, root: ParameterGroup):
        self._root = root

    def list_instances(self) -> list[InstanceConfig]:
        instances_group = self._root.GetGroup(self._INSTANCES_GROUP)
        instances = []
        for instance_id in instances_group.GetGroups():
            group = instances_group.GetGroup(instance_id)
            instances.append(
                InstanceConfig(
                    id=instance_id,
                    label=group.GetString("Label", ""),
                    url=group.GetString("Url", ""),
                    token=group.GetString("Token", ""),
                )
            )
        return instances

    def get_instance(self, instance_id: str) -> InstanceConfig | None:
        for instance in self.list_instances():
            if instance.id == instance_id:
                return instance
        return None

    def save_instance(self, instance: InstanceConfig) -> None:
        group = self._root.GetGroup(self._INSTANCES_GROUP).GetGroup(instance.id)
        group.SetString("Label", instance.label)
        group.SetString("Url", instance.url)
        group.SetString("Token", instance.token)

    def delete_instance(self, instance_id: str) -> None:
        self._root.GetGroup(self._INSTANCES_GROUP).RemGroup(instance_id)
        if self.get_last_selected_id() == instance_id:
            self.set_last_selected_id(None)

    def get_last_selected_id(self) -> str | None:
        value = self._root.GetString(self._LAST_SELECTED_KEY, "")
        return value or None

    def set_last_selected_id(self, instance_id: str | None) -> None:
        self._root.SetString(self._LAST_SELECTED_KEY, instance_id or "")

    def get_last_selected(self) -> InstanceConfig | None:
        """Returns None both when nothing was ever selected and when the
        previously selected instance has since been deleted -- callers should
        fall back to "no selection" (e.g. first item, or a prompt) either way."""
        instance_id = self.get_last_selected_id()
        if instance_id is None:
            return None
        return self.get_instance(instance_id)
