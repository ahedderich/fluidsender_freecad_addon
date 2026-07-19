"""FluidSender preferences page: add/edit/remove target instances.

Only importable inside FreeCAD (PySide, FreeCADGui). FreeCAD's auto-generated
preference pages (declarative .ui forms) have no widget for "a repeating list
of records", so this is a hand-built QWidget page instead -- see the
"Config (custom PreferencePage...)" section of the project CLAUDE.md.

Registration (called once from InitGui.py)::

    import FreeCADGui
    from fluidsender_addon.gui.preferences import FluidSenderPreferencesPage
    FreeCADGui.addPreferencePage(FluidSenderPreferencesPage, "FluidSender")

FreeCAD calls ``loadSettings()``/``saveSettings()`` on instances of the
registered class; see freecad.github.io/DevelopersHandbook -- "Handling
Preferences". Instance edits here are written immediately through
InstanceStore rather than batched until the dialog's OK/Apply, since the
Add/Edit/Remove buttons each represent a complete, already-confirmed action.
"""

from __future__ import annotations

from PySide import QtCore, QtGui

from ..config import InstanceConfig, InstanceStore, new_instance_id
from ..freecad_prefs import default_instance_store


class InstanceEditDialog(QtGui.QDialog):
    def __init__(self, parent: QtGui.QWidget | None = None, instance: InstanceConfig | None = None):
        super().__init__(parent)
        self.setWindowTitle("FluidSender Instance")

        self.label_edit = QtGui.QLineEdit(instance.label if instance else "")
        self.url_edit = QtGui.QLineEdit(instance.url if instance else "")
        self.url_edit.setPlaceholderText("http://fluidsender.local:3000")
        self.token_edit = QtGui.QLineEdit(instance.token if instance else "")
        self.token_edit.setEchoMode(QtGui.QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("fst_...")

        form = QtGui.QFormLayout()
        form.addRow("Label", self.label_edit)
        form.addRow("URL", self.url_edit)
        form.addRow("API token", self.token_edit)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.StandardButton.Ok | QtGui.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self.label_edit.text().strip():
            QtGui.QMessageBox.warning(self, "FluidSender", "Label cannot be empty.")
            return
        if not self.url_edit.text().strip():
            QtGui.QMessageBox.warning(self, "FluidSender", "URL cannot be empty.")
            return
        self.accept()

    def result_values(self) -> tuple[str, str, str]:
        return (
            self.label_edit.text().strip(),
            self.url_edit.text().strip().rstrip("/"),
            self.token_edit.text().strip(),
        )


class FluidSenderPreferencesPage:
    def __init__(self) -> None:
        self._store: InstanceStore = default_instance_store()

        self.form = QtGui.QWidget()

        warning = QtGui.QLabel(
            "API tokens are stored in FreeCAD's preferences file in plain text "
            "(not encrypted). Only use tokens you're comfortable having readable "
            "on this machine."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #a35a00;")

        self.instance_list = QtGui.QListWidget()
        self.instance_list.itemDoubleClicked.connect(self._edit_selected)

        add_button = QtGui.QPushButton("Add...")
        edit_button = QtGui.QPushButton("Edit...")
        remove_button = QtGui.QPushButton("Remove")
        add_button.clicked.connect(self._add_instance)
        edit_button.clicked.connect(self._edit_selected)
        remove_button.clicked.connect(self._remove_selected)

        button_row = QtGui.QHBoxLayout()
        button_row.addWidget(add_button)
        button_row.addWidget(edit_button)
        button_row.addWidget(remove_button)
        button_row.addStretch(1)

        layout = QtGui.QVBoxLayout(self.form)
        layout.addWidget(warning)
        layout.addWidget(self.instance_list)
        layout.addLayout(button_row)

        self._reload_list()

    def _reload_list(self) -> None:
        self.instance_list.clear()
        for instance in self._store.list_instances():
            item = QtGui.QListWidgetItem(f"{instance.label}  —  {instance.url}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, instance.id)
            self.instance_list.addItem(item)

    def _selected_instance_id(self) -> str | None:
        item = self.instance_list.currentItem()
        if item is None:
            return None
        return item.data(QtCore.Qt.ItemDataRole.UserRole)

    def _add_instance(self) -> None:
        dialog = InstanceEditDialog(self.form)
        if dialog.exec_() != QtGui.QDialog.DialogCode.Accepted:
            return
        label, url, token = dialog.result_values()
        self._store.save_instance(
            InstanceConfig(id=new_instance_id(), label=label, url=url, token=token)
        )
        self._reload_list()

    def _edit_selected(self) -> None:
        instance_id = self._selected_instance_id()
        if instance_id is None:
            return
        instance = self._store.get_instance(instance_id)
        if instance is None:
            return
        dialog = InstanceEditDialog(self.form, instance=instance)
        if dialog.exec_() != QtGui.QDialog.DialogCode.Accepted:
            return
        label, url, token = dialog.result_values()
        self._store.save_instance(InstanceConfig(id=instance_id, label=label, url=url, token=token))
        self._reload_list()

    def _remove_selected(self) -> None:
        instance_id = self._selected_instance_id()
        if instance_id is None:
            return
        instance = self._store.get_instance(instance_id)
        label = instance.label if instance else instance_id
        confirm = QtGui.QMessageBox.question(
            self.form,
            "FluidSender",
            f'Remove instance "{label}"?',
        )
        if confirm != QtGui.QMessageBox.StandardButton.Yes:
            return
        self._store.delete_instance(instance_id)
        self._reload_list()

    def loadSettings(self) -> None:
        self._reload_list()

    def saveSettings(self) -> None:
        pass
