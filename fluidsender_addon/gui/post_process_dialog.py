"""Post-process dialog: pick an instance, a destination folder, operations to
include, and a filename, then post-process and upload in one action.

Only importable inside FreeCAD (PySide, FreeCADGui, Path). See
postprocessing.py for how the checked operations become a GCode string.
"""

from __future__ import annotations

import FreeCAD
from PySide import QtCore, QtGui

from ..client import FluidSenderClient
from ..config import InstanceConfig, InstanceStore
from ..errors import FluidSenderError
from ..freecad_prefs import default_instance_store
from ..postprocessing import PostProcessingError, build_gcode
from ..sanitize import sanitize_filename, sanitize_folder
from ..session_state import session_state

_ITEM_TYPE_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


class PostProcessDialog(QtGui.QDialog):
    def __init__(self, job, parent: QtGui.QWidget | None = None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(f"Post Process to FluidSender — {job.Label}")
        self.resize(560, 520)

        self._store: InstanceStore = default_instance_store()
        self._instances: list[InstanceConfig] = self._store.list_instances()
        self._client: FluidSenderClient | None = None
        self._current_folder = session_state.last_folder

        self._build_ui()
        self._on_instance_changed()
        self._update_filename_preview()

    # -- UI construction -----------------------------------------------

    def _build_ui(self) -> None:
        self.instance_combo = QtGui.QComboBox()
        for instance in self._instances:
            self.instance_combo.addItem(instance.label, instance.id)
        last = self._store.get_last_selected()
        if last is not None:
            index = self.instance_combo.findData(last.id)
            if index >= 0:
                self.instance_combo.setCurrentIndex(index)
        self.instance_combo.currentIndexChanged.connect(self._on_instance_changed)

        self.operations_list = QtGui.QListWidget()
        for op in getattr(self.job.Operations, "Group", []):
            item = QtGui.QListWidgetItem(op.Label)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            checked = op.Name not in session_state.last_unchecked_operation_names
            item.setCheckState(
                QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked
            )
            item.setData(QtCore.Qt.ItemDataRole.UserRole, op.Name)
            self.operations_list.addItem(item)
        self.operations_list.itemChanged.connect(self._on_operation_check_changed)

        self.filename_edit = QtGui.QLineEdit(self._default_filename())
        self.filename_edit.textChanged.connect(self._update_filename_preview)
        self.filename_edit.textChanged.connect(self._on_filename_text_changed)
        self.filename_preview = QtGui.QLabel()
        self.filename_preview.setStyleSheet("color: gray;")

        self.folder_path_label = QtGui.QLabel("/")
        self.folder_list = QtGui.QListWidget()
        self.folder_list.itemDoubleClicked.connect(self._on_folder_item_activated)
        up_button = QtGui.QPushButton("Up")
        up_button.clicked.connect(self._go_up)
        new_folder_button = QtGui.QPushButton("New Folder...")
        new_folder_button.clicked.connect(self._create_folder)
        refresh_button = QtGui.QPushButton("Refresh")
        refresh_button.clicked.connect(self._refresh_folder)
        folder_toolbar = QtGui.QHBoxLayout()
        folder_toolbar.addWidget(up_button)
        folder_toolbar.addWidget(new_folder_button)
        folder_toolbar.addWidget(refresh_button)
        folder_toolbar.addStretch(1)

        self.load_checkbox = QtGui.QCheckBox("Load as active job after upload")

        self.status_label = QtGui.QLabel("")
        self.status_label.setWordWrap(True)

        buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.StandardButton.Cancel)
        self.upload_button = buttons.addButton(
            "Post Process && Upload", QtGui.QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.upload_button.clicked.connect(self._on_upload)
        buttons.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(QtGui.QLabel("FluidSender instance"))
        layout.addWidget(self.instance_combo)

        layout.addWidget(QtGui.QLabel("Operations to include"))
        layout.addWidget(self.operations_list, stretch=1)

        layout.addWidget(QtGui.QLabel("Filename"))
        layout.addWidget(self.filename_edit)
        layout.addWidget(self.filename_preview)

        layout.addWidget(QtGui.QLabel("Destination folder"))
        layout.addWidget(self.folder_path_label)
        layout.addWidget(self.folder_list, stretch=1)
        layout.addLayout(folder_toolbar)

        layout.addWidget(self.load_checkbox)
        layout.addWidget(self.status_label)
        layout.addWidget(buttons)

        if not self._instances:
            self.status_label.setText(
                "No FluidSender instances configured. Add one in "
                "Edit > Preferences > FluidSender first."
            )
            self.upload_button.setEnabled(False)

    # -- helpers ---------------------------------------------------------

    def _default_filename(self) -> str:
        return session_state.last_filename or f"{self.job.Label}.nc"

    def _update_filename_preview(self) -> None:
        raw = self.filename_edit.text()
        sanitized = sanitize_filename(raw)
        self.filename_preview.setText(
            "" if sanitized == raw else f"Will be stored as: {sanitized}"
        )

    def _on_filename_text_changed(self, text: str) -> None:
        session_state.last_filename = text

    def _on_operation_check_changed(self, item: QtGui.QListWidgetItem) -> None:
        name = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if item.checkState() == QtCore.Qt.CheckState.Checked:
            session_state.last_unchecked_operation_names.discard(name)
        else:
            session_state.last_unchecked_operation_names.add(name)

    def _set_current_folder(self, folder: str) -> None:
        self._current_folder = folder
        session_state.last_folder = folder

    def _selected_instance(self) -> InstanceConfig | None:
        instance_id = self.instance_combo.currentData()
        if instance_id is None:
            return None
        return self._store.get_instance(instance_id)

    def _on_instance_changed(self) -> None:
        instance = self._selected_instance()
        if instance is None:
            self._client = None
            return
        self._store.set_last_selected_id(instance.id)
        self._client = FluidSenderClient(instance.url, instance.token)
        self._current_folder = session_state.last_folder
        self._refresh_folder()

    # -- remote folder browsing ------------------------------------------

    def _refresh_folder(self) -> None:
        self.folder_path_label.setText(f"/{self._current_folder}")
        self.folder_list.clear()
        if self._client is None:
            return
        try:
            listing = self._client.list_folder(self._current_folder or None)
        except FluidSenderError as exc:
            self.status_label.setText(f"Could not list folder: {exc.message}")
            return
        self.status_label.setText("")
        for folder in listing.folders:
            item = QtGui.QListWidgetItem(f"[folder] {folder.name}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, folder.path)
            item.setData(_ITEM_TYPE_ROLE, "folder")
            self.folder_list.addItem(item)
        for file_entry in listing.files:
            item = QtGui.QListWidgetItem(file_entry.name)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, file_entry.name)
            item.setData(_ITEM_TYPE_ROLE, "file")
            self.folder_list.addItem(item)

    def _on_folder_item_activated(self, item: QtGui.QListWidgetItem) -> None:
        value = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not value:
            return
        if item.data(_ITEM_TYPE_ROLE) == "file":
            self.filename_edit.setText(value)
            return
        self._set_current_folder(value)
        self._refresh_folder()

    def _go_up(self) -> None:
        if "/" in self._current_folder:
            self._set_current_folder(self._current_folder.rsplit("/", 1)[0])
        else:
            self._set_current_folder("")
        self._refresh_folder()

    def _create_folder(self) -> None:
        if self._client is None:
            return
        name, ok = QtGui.QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        target = sanitize_folder(f"{self._current_folder}/{name}" if self._current_folder else name)
        try:
            self._client.create_folder(target)
        except FluidSenderError as exc:
            QtGui.QMessageBox.warning(
                self, "FluidSender", f"Could not create folder: {exc.message}"
            )
            return
        self._refresh_folder()

    # -- upload ------------------------------------------------------------

    def _checked_operation_names(self) -> list[str]:
        names = []
        for i in range(self.operations_list.count()):
            item = self.operations_list.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                names.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
        return names

    def _on_upload(self) -> None:
        if self._client is None:
            QtGui.QMessageBox.warning(self, "FluidSender", "Select a FluidSender instance first.")
            return

        checked_names = self._checked_operation_names()
        if not checked_names:
            QtGui.QMessageBox.warning(self, "FluidSender", "Select at least one operation.")
            return

        filename = sanitize_filename(self.filename_edit.text().strip())
        if not filename:
            QtGui.QMessageBox.warning(self, "FluidSender", "Enter a filename.")
            return

        operations = [op for op in self.job.Operations.Group if op.Name in checked_names]

        self.status_label.setText("Post-processing...")
        QtGui.QApplication.processEvents()
        try:
            gcode = build_gcode(self.job, operations)
        except PostProcessingError as exc:
            self.status_label.setText(f"Post-processing failed: {exc}")
            return

        self.status_label.setText("Uploading...")
        QtGui.QApplication.processEvents()
        try:
            result = self._client.upload(
                gcode.encode("utf-8"),
                filename,
                folder=self._current_folder or None,
                load=self.load_checkbox.isChecked(),
            )
        except FluidSenderError as exc:
            self.status_label.setText(f"Upload failed: {exc.message}")
            FreeCAD.Console.PrintError(f"FluidSender upload failed: {exc.message}\n")
            return

        if result.load is not None and not result.load.ok:
            self.status_label.setText(
                f"File stored at {result.file.path}, but not loaded: "
                f"{result.load.code} — {result.load.message}"
            )
            QtGui.QMessageBox.warning(
                self,
                "FluidSender",
                f"File stored at {result.file.path}.\n\n"
                f"It was NOT loaded as the active job: {result.load.message}",
            )
            return

        FreeCAD.Console.PrintMessage(f"FluidSender: uploaded to {result.file.path}\n")
        self.accept()
