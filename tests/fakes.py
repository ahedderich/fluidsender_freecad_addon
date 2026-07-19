"""In-memory stand-in for FreeCAD's ParameterGrp, satisfying config.ParameterGroup."""

from __future__ import annotations


class FakeParameterGroup:
    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._groups: dict[str, FakeParameterGroup] = {}

    def GetString(self, key: str, default: str = "") -> str:
        return self._strings.get(key, default)

    def SetString(self, key: str, value: str) -> None:
        self._strings[key] = value

    def GetGroups(self) -> list[str]:
        return list(self._groups.keys())

    def GetGroup(self, name: str) -> FakeParameterGroup:
        return self._groups.setdefault(name, FakeParameterGroup())

    def RemGroup(self, name: str) -> None:
        self._groups.pop(name, None)

    def HasGroup(self, name: str) -> bool:
        return name in self._groups
