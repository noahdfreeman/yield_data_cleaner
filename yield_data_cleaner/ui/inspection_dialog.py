# SPDX-License-Identifier: GPL-3.0-or-later
"""First guided vertical slice for input, mapping, and CRS inspection."""

from __future__ import annotations

import html
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes

from ..compat import enum_member
from ..core.column_detection import FIELD_ALIASES, detect_columns
from ..core.crs_service import recognize_crs
from ..core.delimited_text import inspect_delimited_file
from ..core.mapping_profile import MappingProfile, load_mapping_profile, save_mapping_profile
from ..core.run_naming import build_run_stem, next_available_run_folder, run_file_paths
from ..core.settings import PLUGIN_NAME
from ..version import VERSION


class YieldInputInspectionDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or (iface.mainWindow() if iface else None))
        self.iface = iface
        self.layer_ids = []
        self.current_columns = []
        self.current_suggestions = []
        self.current_crs_authid = None
        self.boundary_layer_ids = []
        self.boundary_point_layer_ids = []
        self.setWindowTitle(f"{PLUGIN_NAME} {VERSION} - Guided workflow")
        self.resize(1180, 720)
        self._build_ui()
        self._refresh_layers()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        workspace = QHBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.setObjectName("yieldDataCleanerWorkflowTabs")
        self.tabs.addTab(self._build_input_tab(), "1. Input & Mapping")
        self.tabs.addTab(self._build_boundary_tab(), "2. Field Boundary")
        self.tabs.addTab(self._build_prepare_tab(), "3. Prepare Dataset")
        self.tabs.currentChanged.connect(self._update_help)
        workspace.addWidget(self.tabs, 3)

        help_group = QGroupBox("How to use this tool")
        help_group.setMinimumWidth(300)
        help_layout = QVBoxLayout(help_group)
        self.help_panel = QTextBrowser()
        self.help_panel.setObjectName("yieldDataCleanerHelpPanel")
        self.help_panel.setOpenExternalLinks(False)
        help_layout.addWidget(self.help_panel)
        workspace.addWidget(help_group, 1)
        layout.addLayout(workspace, 1)

        buttons = QDialogButtonBox(enum_member(QDialogButtonBox, "StandardButton", "Close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_help(0)

    def _build_input_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        intro = QLabel(
            "Choose a point layer already loaded in QGIS or browse for a local "
            "yield data file. Inspection is read-only."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        source_group = QGroupBox("Input source")
        source_layout = QFormLayout(source_group)
        self.loaded_radio = QRadioButton("Use a point layer loaded in QGIS")
        self.loaded_radio.setChecked(True)
        self.file_radio = QRadioButton("Browse for a file on this computer")
        self.layer_combo = QComboBox()
        self.layer_combo.currentIndexChanged.connect(self._refresh_suggested_field_name)
        refresh_button = QPushButton("Refresh layers")
        refresh_button.clicked.connect(self._refresh_layers)
        layer_row = QHBoxLayout()
        layer_row.addWidget(self.layer_combo, 1)
        layer_row.addWidget(refresh_button)
        self.file_path = QLineEdit()
        self.file_path.textChanged.connect(self._refresh_suggested_field_name)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_path, 1)
        file_row.addWidget(browse_button)
        source_layout.addRow(self.loaded_radio)
        source_layout.addRow("Loaded layer", layer_row)
        source_layout.addRow(self.file_radio)
        source_layout.addRow("Local file", file_row)
        layout.addWidget(source_group)

        inspect_button = QPushButton("Inspect input")
        inspect_button.clicked.connect(self._inspect)
        layout.addWidget(inspect_button)
        self.results = QTextBrowser()
        self.results.setHtml(
            "<h3>No input inspected</h3>"
            "<p>Column suggestions and CRS evidence will appear here.</p>"
        )
        layout.addWidget(self.results, 1)

        mapping_group = QGroupBox("Review mapping")
        mapping_layout = QVBoxLayout(mapping_group)
        assumptions = QFormLayout()
        self.crop_combo = QComboBox()
        self.crop_combo.addItem("Corn", "corn")
        self.crop_combo.addItem("Soybean", "soybean")
        self.crop_combo.addItem("Wheat", "wheat")
        self.units_combo = QComboBox()
        self.units_combo.addItem("Imperial (default)", "imperial")
        self.units_combo.addItem("Metric", "metric")
        self.crs_text = QLineEdit()
        self.crs_text.setPlaceholderText("Example: EPSG:4326")
        assumptions.addRow("Crop", self.crop_combo)
        assumptions.addRow("Source units", self.units_combo)
        assumptions.addRow("Confirmed source CRS", self.crs_text)
        mapping_layout.addLayout(assumptions)
        self.mapping_table = QTableWidget(len(FIELD_ALIASES), 3)
        self.mapping_table.setHorizontalHeaderLabels(
            ("Canonical field", "Source column", "Evidence")
        )
        self.mapping_table.verticalHeader().setVisible(False)
        resize_contents = enum_member(QHeaderView, "ResizeMode", "ResizeToContents")
        stretch = enum_member(QHeaderView, "ResizeMode", "Stretch")
        self.mapping_table.horizontalHeader().setSectionResizeMode(0, resize_contents)
        self.mapping_table.horizontalHeader().setSectionResizeMode(1, stretch)
        self.mapping_table.horizontalHeader().setSectionResizeMode(2, stretch)
        for row, canonical in enumerate(FIELD_ALIASES):
            item = QTableWidgetItem(canonical)
            item.setFlags(item.flags() & ~enum_member(Qt, "ItemFlag", "ItemIsEditable"))
            self.mapping_table.setItem(row, 0, item)
            self.mapping_table.setCellWidget(row, 1, QComboBox())
            self.mapping_table.setItem(row, 2, QTableWidgetItem("Not inspected"))
        mapping_layout.addWidget(self.mapping_table)
        profile_buttons = QHBoxLayout()
        load_button = QPushButton("Load mapping profile...")
        load_button.clicked.connect(self._load_profile)
        save_button = QPushButton("Save reviewed mapping...")
        save_button.clicked.connect(self._save_profile)
        profile_buttons.addWidget(load_button)
        profile_buttons.addWidget(save_button)
        profile_buttons.addStretch(1)
        mapping_layout.addLayout(profile_buttons)
        layout.addWidget(mapping_group, 2)
        self.input_continue_button = QPushButton("Continue to Field Boundary")
        self.input_continue_button.setObjectName("continueToBoundaryButton")
        self.input_continue_button.setEnabled(False)
        self.input_continue_button.clicked.connect(self._continue_to_boundary)
        layout.addWidget(self.input_continue_button)
        return tab

    def _build_prepare_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        intro = QLabel(
            "Choose where to save the run. The plugin creates a new named folder and "
            "prepares both the yield observations and field boundary without deleting "
            "source records."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        settings = QGroupBox("Dataset name and output")
        form = QFormLayout(settings)
        self.field_name = QLineEdit()
        self.field_name.setPlaceholderText("Automatically suggested from the boundary")
        self.output_parent_folder = QLineEdit()
        self.output_parent_folder.setPlaceholderText(
            "Choose a parent folder, such as Documents or Downloads"
        )
        browse = QPushButton("Browse...")
        browse.clicked.connect(lambda: self._browse_output_folder(self.output_parent_folder))
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.output_parent_folder, 1)
        folder_row.addWidget(browse)
        self.output_crs = QLineEdit()
        self.output_crs.setPlaceholderText(
            "Optional, for example EPSG:32616; leave blank for automatic local CRS"
        )
        self.run_name_preview = QLabel()
        self.run_name_preview.setWordWrap(True)
        form.addRow("Field / boundary name", self.field_name)
        form.addRow("Save inside", folder_row)
        form.addRow("Analysis/output CRS", self.output_crs)
        form.addRow("New run folder", self.run_name_preview)
        layout.addWidget(settings)

        run_button = QPushButton("Create prepared yield dataset")
        run_button.setObjectName("createPreparedDatasetButton")
        run_button.clicked.connect(self._run_prepare_dataset)
        layout.addWidget(run_button)
        self.prepare_status = QTextBrowser()
        self.prepare_status.setHtml(
            "<h3>Complete steps 1 and 2 first</h3>"
            "<p>The output folder and filenames will include the boundary name, crop, "
            "and current date. If that run already exists, a numbered suffix is added.</p>"
        )
        layout.addWidget(self.prepare_status, 1)
        for signal in (
            self.field_name.textChanged,
            self.output_parent_folder.textChanged,
            self.crop_combo.currentIndexChanged,
        ):
            signal.connect(self._update_run_preview)
        self._update_run_preview()
        return tab

    def _build_boundary_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        intro = QLabel(
            "Use one existing polygon boundary or derive an operational harvest extent "
            "from yield points. Derived boundaries always require visual review."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        settings = QGroupBox("Boundary setup")
        form = QFormLayout(settings)
        self.boundary_mode = QComboBox()
        self.boundary_mode.addItems(
            ("Use one existing polygon", "Derive operational extent from yield points")
        )
        self.boundary_mode.currentIndexChanged.connect(self._update_boundary_mode)

        self.boundary_layer_combo = QComboBox()
        self.boundary_layer_combo.currentIndexChanged.connect(self._refresh_suggested_field_name)
        self.boundary_file_path = QLineEdit()
        self.boundary_file_path.setPlaceholderText(
            "Optional polygon file; used instead of the loaded-layer selection"
        )
        self.boundary_browse_button = QPushButton("Browse...")
        self.boundary_browse_button.clicked.connect(self._browse_boundary_file)
        self.boundary_file_path.textChanged.connect(self._refresh_suggested_field_name)
        boundary_file_row = QHBoxLayout()
        boundary_file_row.addWidget(self.boundary_file_path, 1)
        boundary_file_row.addWidget(self.boundary_browse_button)

        self.use_inspected_source = QCheckBox("Use the source selected on Input & Mapping")
        self.use_inspected_source.setChecked(True)
        self.use_inspected_source.toggled.connect(self._refresh_suggested_field_name)
        self.boundary_point_combo = QComboBox()
        self.boundary_point_combo.currentIndexChanged.connect(self._refresh_width_fields)
        self.boundary_point_combo.currentIndexChanged.connect(self._refresh_suggested_field_name)
        self.boundary_point_file = QLineEdit()
        self.boundary_point_file.setPlaceholderText(
            "Optional QGIS-readable point file; used instead of the loaded layer"
        )
        self.point_browse_button = QPushButton("Browse...")
        self.point_browse_button.clicked.connect(self._browse_boundary_points)
        self.boundary_point_file.textChanged.connect(self._refresh_suggested_field_name)
        point_file_row = QHBoxLayout()
        point_file_row.addWidget(self.boundary_point_file, 1)
        point_file_row.addWidget(self.point_browse_button)

        self.width_field = QComboBox()
        self.width_field.setEditable(True)
        self.width_field.addItem("swath_width_m")
        self.default_width = QDoubleSpinBox()
        self.default_width.setRange(0.0, 328.0)
        self.default_width.setDecimals(2)
        self.default_width.setValue(30.0)
        self.default_width.setSuffix(" ft")
        self.gap_closing = QDoubleSpinBox()
        self.gap_closing.setRange(0.0, 328.0)
        self.gap_closing.setDecimals(2)
        self.gap_closing.setValue(3.28)
        self.gap_closing.setSuffix(" ft")
        self.concavity = QDoubleSpinBox()
        self.concavity.setRange(0.0, 1.0)
        self.concavity.setSingleStep(0.05)
        self.concavity.setDecimals(2)
        self.concavity.setValue(0.3)

        form.addRow("Boundary mode", self.boundary_mode)
        form.addRow("Loaded polygon layer", self.boundary_layer_combo)
        form.addRow("Or polygon file", boundary_file_row)
        form.addRow(self.use_inspected_source)
        form.addRow("Loaded yield-point layer", self.boundary_point_combo)
        form.addRow("Or point file", point_file_row)
        form.addRow("Swath-width field", self.width_field)
        form.addRow("Default swath width", self.default_width)
        form.addRow("Gap-closing distance", self.gap_closing)
        form.addRow("Fallback concavity", self.concavity)
        layout.addWidget(settings)

        continue_button = QPushButton("Confirm boundary and continue")
        continue_button.setObjectName("confirmFieldBoundaryButton")
        continue_button.clicked.connect(self._confirm_boundary)
        layout.addWidget(continue_button)
        self.boundary_status = QTextBrowser()
        self.boundary_status.setHtml(
            "<h3>Boundary not confirmed</h3>"
            "<p>Select an existing boundary or choose derivation settings, then continue. "
            "The boundary is written when the prepared dataset is created.</p>"
        )
        layout.addWidget(self.boundary_status, 1)
        self._update_boundary_mode(0)
        return tab

    def _refresh_layers(self):
        selected_point_id = (
            self.layer_ids[self.layer_combo.currentIndex()]
            if self.layer_ids and self.layer_combo.currentIndex() >= 0
            else None
        )
        selected_boundary_id = (
            self.boundary_layer_ids[self.boundary_layer_combo.currentIndex()]
            if self.boundary_layer_ids and self.boundary_layer_combo.currentIndex() >= 0
            else None
        )
        selected_derived_id = (
            self.boundary_point_layer_ids[self.boundary_point_combo.currentIndex()]
            if self.boundary_point_layer_ids and self.boundary_point_combo.currentIndex() >= 0
            else None
        )
        self.layer_combo.clear()
        self.boundary_layer_combo.clear()
        self.boundary_point_combo.clear()
        self.layer_ids = []
        self.boundary_layer_ids = []
        self.boundary_point_layer_ids = []
        point_geometry = enum_member(QgsWkbTypes, "GeometryType", "PointGeometry")
        polygon_geometry = enum_member(QgsWkbTypes, "GeometryType", "PolygonGeometry")
        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
            if geometry_type == point_geometry:
                self.layer_combo.addItem(layer.name())
                self.layer_ids.append(layer.id())
                self.boundary_point_combo.addItem(layer.name())
                self.boundary_point_layer_ids.append(layer.id())
            elif geometry_type == polygon_geometry:
                self.boundary_layer_combo.addItem(layer.name())
                self.boundary_layer_ids.append(layer.id())
        for combo, identifiers, selected in (
            (self.layer_combo, self.layer_ids, selected_point_id),
            (self.boundary_layer_combo, self.boundary_layer_ids, selected_boundary_id),
            (self.boundary_point_combo, self.boundary_point_layer_ids, selected_derived_id),
        ):
            if selected in identifiers:
                combo.setCurrentIndex(identifiers.index(selected))
        self._refresh_width_fields()
        self._refresh_suggested_field_name()

    def _refresh_width_fields(self):
        previous = self.width_field.currentText().strip() or "swath_width_m"
        fields = ["swath_width_m"]
        index = self.boundary_point_combo.currentIndex()
        if 0 <= index < len(self.boundary_point_layer_ids):
            layer = QgsProject.instance().mapLayer(self.boundary_point_layer_ids[index])
            if isinstance(layer, QgsVectorLayer):
                fields.extend(field.name() for field in layer.fields())
        for column in self.current_columns:
            if column not in fields:
                fields.append(column)
        self.width_field.clear()
        self.width_field.addItems(list(dict.fromkeys(fields)))
        found = self.width_field.findText(previous)
        self.width_field.setCurrentIndex(max(0, found))

    def _update_boundary_mode(self, index):
        use_existing = index == 0
        for widget in (
            self.boundary_layer_combo,
            self.boundary_file_path,
            self.boundary_browse_button,
        ):
            widget.setEnabled(use_existing)
        for widget in (
            self.use_inspected_source,
            self.boundary_point_combo,
            self.boundary_point_file,
            self.point_browse_button,
            self.width_field,
            self.default_width,
            self.gap_closing,
            self.concavity,
        ):
            widget.setEnabled(not use_existing)
        self._refresh_suggested_field_name()

    def _update_help(self, index):
        pages = (
            """
            <h2>Input &amp; Mapping</h2>
            <ol>
              <li>Select a point layer already loaded in QGIS, or browse for a local file.</li>
              <li>Click <b>Inspect input</b>.</li>
              <li>Confirm crop, units, source CRS, and every proposed column mapping.</li>
              <li>Save the mapping if you expect to use this export format again.</li>
              <li>Click <b>Continue to Field Boundary</b>.</li>
            </ol>
            <p><b>Important:</b> Inspection is read-only. A low-confidence CRS or mapping
            must be reviewed before spatial calculations are run.</p>
            """,
            """
            <h2>Field Boundary</h2>
            <h3>Existing boundary</h3>
            <p>Select one loaded polygon, or browse for a polygon file. A browsed file
            takes precedence over the loaded-layer selection.</p>
            <h3>Derived boundary</h3>
            <p>Use the inspected yield points when possible. Confirm the swath-width
            field and fallback width. The default display is Imperial; values are converted
            to meters for processing.</p>
            <p>Click <b>Confirm boundary and continue</b>. The boundary will be written with
            the prepared dataset in the final step.</p>
            <p><b>Always inspect a derived boundary on the map.</b> It represents harvested
            extent, not a legal or ownership boundary.</p>
            """,
            """
            <h2>Prepare Dataset</h2>
            <ol>
              <li>Review the suggested field or boundary name.</li>
              <li>Choose a parent output folder. The plugin creates a new run folder.</li>
              <li>Leave the analysis CRS blank for automatic local projection, or enter an
              explicit EPSG code.</li>
              <li>Click <b>Create prepared yield dataset</b>.</li>
            </ol>
            <p>The folder and every main output file use the field name, crop, and date.
            Existing runs are never overwritten; <code>_02</code>, <code>_03</code>, and so
            on are added automatically.</p>
            <p>The prepared observations preserve source attributes and add normalized
            fields. This step prepares data for later cleaning; it does not discard records.</p>
            """,
        )
        self.help_panel.setHtml(pages[index] if 0 <= index < len(pages) else pages[0])

    def _browse_output_folder(self, target):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select parent output folder",
            target.text().strip(),
        )
        if folder:
            target.setText(folder)

    def _browse_boundary_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select an existing field boundary",
            self.boundary_file_path.text(),
            "Polygon data (*.gpkg *.shp *.geojson *.json *.kml);;All files (*.*)",
        )
        if path:
            self.boundary_file_path.setText(path)

    def _browse_boundary_points(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select yield points for boundary derivation",
            self.boundary_point_file.text(),
            "Point data (*.gpkg *.shp *.geojson *.json);;All files (*.*)",
        )
        if path:
            self.boundary_point_file.setText(path)

    def _selected_input_source(self):
        if self.loaded_radio.isChecked():
            index = self.layer_combo.currentIndex()
            if not 0 <= index < len(self.layer_ids):
                raise ValueError("No eligible point layer is selected")
            layer = QgsProject.instance().mapLayer(self.layer_ids[index])
            if layer is None:
                raise ValueError("The selected point layer is no longer available")
            return layer, ""
        path = Path(self.file_path.text().strip())
        if not path.is_file():
            raise ValueError("Select an existing yield data file")
        return None, str(path)

    @staticmethod
    def _gpkg_sink_uri(path, layer_name):
        """Build a Processing provider URI for a named GeoPackage layer."""

        safe_path = str(path).replace("\\", "/").replace("'", "''")
        safe_layer = str(layer_name).replace('"', '""')
        return f"ogr:dbname='{safe_path}' table=\"{safe_layer}\" (geom)"

    def _suggested_field_name(self):
        if self.boundary_mode.currentIndex() == 0:
            boundary_file = self.boundary_file_path.text().strip()
            if boundary_file:
                return Path(boundary_file).stem
            index = self.boundary_layer_combo.currentIndex()
            if 0 <= index < self.boundary_layer_combo.count():
                return self.boundary_layer_combo.itemText(index)
        else:
            point_file = self.boundary_point_file.text().strip()
            if not self.use_inspected_source.isChecked() and point_file:
                return Path(point_file).stem
            if self.loaded_radio.isChecked():
                index = self.layer_combo.currentIndex()
                if 0 <= index < self.layer_combo.count():
                    return self.layer_combo.itemText(index)
            input_file = self.file_path.text().strip()
            if input_file:
                return Path(input_file).stem
            index = self.boundary_point_combo.currentIndex()
            if 0 <= index < self.boundary_point_combo.count():
                return self.boundary_point_combo.itemText(index)
        return "field"

    def _refresh_suggested_field_name(self, *_args):
        if not hasattr(self, "field_name"):
            return
        if not self.field_name.isModified() or not self.field_name.text().strip():
            self.field_name.setText(self._suggested_field_name())
            self.field_name.setModified(False)
        self._update_run_preview()

    def _update_run_preview(self, *_args):
        if not hasattr(self, "run_name_preview"):
            return
        field_name = self.field_name.text().strip() or self._suggested_field_name()
        stem = build_run_stem(field_name, str(self.crop_combo.currentData()))
        parent_text = self.output_parent_folder.text().strip()
        candidate = (
            next_available_run_folder(Path(parent_text), stem) if parent_text else Path(stem)
        )
        self.run_name_preview.setText(str(candidate))

    def _boundary_parameters(self):
        existing_boundary = None
        yield_points = None
        if self.boundary_mode.currentIndex() == 0:
            boundary_file = self.boundary_file_path.text().strip()
            if boundary_file:
                if not Path(boundary_file).is_file():
                    raise ValueError("The selected boundary file does not exist")
                existing_boundary = boundary_file
            else:
                index = self.boundary_layer_combo.currentIndex()
                if not 0 <= index < len(self.boundary_layer_ids):
                    raise ValueError("Select one loaded polygon or browse for a boundary file")
                existing_boundary = QgsProject.instance().mapLayer(self.boundary_layer_ids[index])
                if existing_boundary is None:
                    raise ValueError("The selected boundary layer is no longer available")
        elif self.use_inspected_source.isChecked():
            yield_points, input_file = self._selected_input_source()
            yield_points = yield_points or input_file
        else:
            point_file = self.boundary_point_file.text().strip()
            if point_file:
                if not Path(point_file).is_file():
                    raise ValueError("The selected yield-point file does not exist")
                yield_points = point_file
            else:
                index = self.boundary_point_combo.currentIndex()
                if not 0 <= index < len(self.boundary_point_layer_ids):
                    raise ValueError("Select yield points for boundary derivation")
                yield_points = QgsProject.instance().mapLayer(self.boundary_point_layer_ids[index])
                if yield_points is None:
                    raise ValueError("The selected yield-point layer is no longer available")
        return existing_boundary, yield_points

    def _confirm_boundary(self):
        try:
            self._boundary_parameters()
            self._refresh_suggested_field_name()
            field_name = self.field_name.text().strip() or self._suggested_field_name()
            self.field_name.setText(field_name)
            detail = (
                "The derived boundary will be added to the map for review after the "
                "dataset is created."
                if self.boundary_mode.currentIndex() == 1
                else "The selected boundary will be validated when the dataset is created."
            )
            self.boundary_status.setHtml(
                "<h3>Boundary settings confirmed</h3>"
                f"<p><b>Output name:</b> {html.escape(field_name)}</p>"
                f"<p>{html.escape(detail)}</p>"
            )
            self.tabs.setCurrentIndex(2)
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))

    def _continue_to_boundary(self):
        try:
            if not self.current_columns:
                raise ValueError("Inspect the input before continuing")
            profile = MappingProfile(
                mapping=self._reviewed_mapping(),
                crop_code=str(self.crop_combo.currentData()),
                unit_profile=str(self.units_combo.currentData()),
                source_crs=self.crs_text.text().strip() or None,
                profile_name="guided_workflow_review",
            )
            errors = profile.validate(self.current_columns)
            if errors:
                raise ValueError("Review the column mapping: " + "; ".join(errors))
            self.tabs.setCurrentIndex(1)
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))

    def _run_prepare_dataset(self):
        folder = None
        try:
            if not self.current_columns:
                raise ValueError("Complete Input & Mapping before preparing the dataset")
            existing_boundary, yield_points = self._boundary_parameters()
            parent_text = self.output_parent_folder.text().strip()
            if not parent_text:
                raise ValueError("Choose a parent output folder")
            parent = Path(parent_text)
            parent.mkdir(parents=True, exist_ok=True)
            field_name = self.field_name.text().strip() or self._suggested_field_name()
            stem = build_run_stem(field_name, str(self.crop_combo.currentData()))
            profile = MappingProfile(
                mapping=self._reviewed_mapping(),
                crop_code=str(self.crop_combo.currentData()),
                unit_profile=str(self.units_combo.currentData()),
                source_crs=self.crs_text.text().strip() or None,
                profile_name="guided_workflow",
            )
            errors = profile.validate(self.current_columns)
            if errors:
                raise ValueError("; ".join(errors))
            source, input_file = self._selected_input_source()
            folder = next_available_run_folder(parent, stem)
            folder.mkdir()
            paths = run_file_paths(folder)
            save_mapping_profile(profile, paths["mapping"])
            import processing

            prepared_result = processing.run(
                "yield_data_cleaner:create_canonical_audit",
                {
                    "SOURCE": source,
                    "INPUT_FILE": input_file,
                    "MAPPING_PROFILE": str(paths["mapping"]),
                    "CROP": self.crop_combo.currentIndex(),
                    "UNIT_PROFILE": self.units_combo.currentIndex(),
                    "SOURCE_CRS": self.crs_text.text().strip() or None,
                    "OUTPUT_CRS": self.output_crs.text().strip() or None,
                    "MAPPING_REPORT": str(paths["mapping_report"]),
                    "RUN_MANIFEST": str(paths["manifest"]),
                    "OUTPUT": self._gpkg_sink_uri(paths["geopackage"], "prepared_observations"),
                },
            )
            boundary_result = processing.run(
                "yield_data_cleaner:prepare_field_boundary",
                {
                    "MODE": self.boundary_mode.currentIndex(),
                    "EXISTING_BOUNDARY": existing_boundary,
                    "YIELD_POINTS": yield_points,
                    "WIDTH_FIELD": self.width_field.currentText().strip() or None,
                    "DEFAULT_WIDTH": self.default_width.value() * 0.3048,
                    "GAP_CLOSING": self.gap_closing.value() * 0.3048,
                    "CONCAVITY": self.concavity.value(),
                    "PROVENANCE": str(paths["boundary_provenance"]),
                    "OUTPUT": self._gpkg_sink_uri(paths["geopackage"], "field_boundary"),
                },
            )

            prepared_uri = str(prepared_result.get("OUTPUT") or paths["geopackage"])
            prepared_layer = QgsVectorLayer(prepared_uri, "Prepared yield observations", "ogr")
            if not prepared_layer.isValid():
                prepared_layer = QgsVectorLayer(
                    f"{paths['geopackage']}|layername=prepared_observations",
                    "Prepared yield observations",
                    "ogr",
                )
            boundary_uri = str(boundary_result.get("OUTPUT") or paths["geopackage"])
            boundary_layer = QgsVectorLayer(boundary_uri, "Prepared field boundary", "ogr")
            if not boundary_layer.isValid():
                boundary_layer = QgsVectorLayer(
                    f"{paths['geopackage']}|layername=field_boundary",
                    "Prepared field boundary",
                    "ogr",
                )
            if not prepared_layer.isValid() or not boundary_layer.isValid():
                raise ValueError("The run completed, but QGIS could not open an output layer")
            QgsProject.instance().addMapLayer(boundary_layer)
            QgsProject.instance().addMapLayer(prepared_layer)
            review_text = (
                "Review the derived field boundary on the map before using it."
                if self.boundary_mode.currentIndex() == 1
                else "The selected field boundary was validated and included."
            )
            self.prepare_status.setHtml(
                "<h3>Prepared dataset created</h3>"
                f"<p><b>Run folder:</b> {html.escape(str(folder))}</p>"
                f"<p><b>Yield data:</b> {html.escape(paths['geopackage'].name)}</p>"
                f"<p>{html.escape(review_text)}</p>"
                "<p>No source observations were deleted.</p>"
            )
            self._update_run_preview()
        except Exception as exc:
            partial = (
                f"\n\nA partial run folder was retained for diagnostics:\n{folder}"
                if folder is not None and folder.exists()
                else ""
            )
            QMessageBox.warning(self, PLUGIN_NAME, f"{exc}{partial}")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select yield monitor data",
            self.file_path.text(),
            "Yield and vector data (*.csv *.txt *.tsv *.gpkg *.shp *.geojson);;All files (*.*)",
        )
        if path:
            self.file_path.setText(path)
            self.file_radio.setChecked(True)

    @staticmethod
    def _layer_report(layer):
        columns = [field.name() for field in layer.fields()]
        rows = []
        for index, feature in enumerate(layer.getFeatures()):
            rows.append({name: feature[name] for name in columns})
            if index >= 49:
                break
        suggestions = detect_columns(columns, rows)
        mapping = {item.canonical_field: item.source_column for item in suggestions}
        declared = layer.crs().authid() if layer.crs().isValid() else None
        recognition = None
        if mapping.get("x") and mapping.get("y"):
            recognition = recognize_crs(
                (row.get(mapping["x"]) for row in rows),
                (row.get(mapping["y"]) for row in rows),
                mapping["x"],
                mapping["y"],
                declared,
            )
        elif declared:
            recognition = recognize_crs((), (), declared_authid=declared)
        return columns, rows, suggestions, recognition

    def _inspect(self):
        try:
            if self.loaded_radio.isChecked():
                if not self.layer_ids or self.layer_combo.currentIndex() < 0:
                    raise ValueError("No eligible point layer is loaded in QGIS")
                layer_id = self.layer_ids[self.layer_combo.currentIndex()]
                layer = QgsProject.instance().mapLayer(layer_id)
                if layer is None:
                    raise ValueError("The selected layer is no longer available")
                source_label = layer.name()
                columns, rows, suggestions, recognition = self._layer_report(layer)
            else:
                path = Path(self.file_path.text().strip())
                if path.suffix.lower() in {".csv", ".txt", ".tsv"}:
                    inspection = inspect_delimited_file(path)
                    source_label = str(path)
                    columns = list(inspection.columns)
                    rows = list(inspection.sample_rows)
                    suggestions = list(inspection.mapping_suggestions)
                    mapping = {item.canonical_field: item.source_column for item in suggestions}
                    recognition = None
                    if mapping.get("x") and mapping.get("y"):
                        recognition = recognize_crs(
                            (row.get(mapping["x"]) for row in rows),
                            (row.get(mapping["y"]) for row in rows),
                            mapping["x"],
                            mapping["y"],
                        )
                else:
                    layer = QgsVectorLayer(str(path), path.stem, "ogr")
                    if not layer.isValid():
                        raise ValueError(f"QGIS could not open {path}")
                    source_label = str(path)
                    columns, rows, suggestions, recognition = self._layer_report(layer)
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))
            return

        mapping_rows = (
            "".join(
                "<tr><td><code>{}</code></td><td>{}</td><td>{:.0%}</td><td>{}</td></tr>".format(
                    html.escape(item.canonical_field),
                    html.escape(item.source_column),
                    item.confidence,
                    html.escape(item.reason),
                )
                for item in suggestions
            )
            or '<tr><td colspan="4">No confident column suggestions</td></tr>'
        )
        if recognition is None:
            crs_html = "CRS unresolved; select or confirm it before spatial calculations."
        else:
            crs_html = "{} ({:.0%} confidence). {}{}".format(
                html.escape(recognition.authid or "Unresolved"),
                recognition.confidence,
                html.escape(recognition.reason),
                " User confirmation required." if recognition.requires_confirmation else "",
            )
        self.results.setHtml(
            f"<h3>{html.escape(source_label)}</h3>"
            f"<p><b>{len(columns)}</b> columns; <b>{len(rows)}</b> sample rows inspected. "
            "Input was not modified.</p>"
            f"<h4>CRS</h4><p>{crs_html}</p>"
            "<h4>Suggested mappings</h4><table border='1' cellspacing='0' cellpadding='5'>"
            "<tr><th>Canonical field</th><th>Source column</th>"
            "<th>Confidence</th><th>Evidence</th></tr>"
            f"{mapping_rows}</table>"
        )
        self.current_columns = list(columns)
        self.current_suggestions = list(suggestions)
        self.current_crs_authid = recognition.authid if recognition is not None else None
        if self.current_crs_authid:
            self.crs_text.setText(self.current_crs_authid)
        self._populate_mapping_table()
        self._refresh_width_fields()
        self.input_continue_button.setEnabled(True)

    def _populate_mapping_table(self, selected_mapping=None):
        selected_mapping = selected_mapping or {
            item.canonical_field: item.source_column for item in self.current_suggestions
        }
        evidence = {item.canonical_field: item for item in self.current_suggestions}
        for row, canonical in enumerate(FIELD_ALIASES):
            combo = self.mapping_table.cellWidget(row, 1)
            combo.clear()
            combo.addItem("(not mapped)", "")
            for column in self.current_columns:
                combo.addItem(column, column)
            selected = selected_mapping.get(canonical, "")
            selected_index = combo.findData(selected)
            combo.setCurrentIndex(max(0, selected_index))
            suggestion = evidence.get(canonical)
            if suggestion is None:
                text = "No automatic suggestion"
            else:
                review = " — review" if suggestion.confidence < 0.9 else ""
                text = f"{suggestion.confidence:.0%}: {suggestion.reason}{review}"
            self.mapping_table.setItem(row, 2, QTableWidgetItem(text))

    def _reviewed_mapping(self):
        mapping = {}
        for row, canonical in enumerate(FIELD_ALIASES):
            combo = self.mapping_table.cellWidget(row, 1)
            source_column = combo.currentData()
            if source_column:
                mapping[canonical] = str(source_column)
        return mapping

    def _save_profile(self):
        if not self.current_columns:
            QMessageBox.warning(self, PLUGIN_NAME, "Inspect an input before saving its mapping")
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Save yield column mapping",
            "yield_column_mapping.json",
            "JSON files (*.json)",
        )
        if not destination:
            return
        profile = MappingProfile(
            mapping=self._reviewed_mapping(),
            crop_code=str(self.crop_combo.currentData()),
            unit_profile=str(self.units_combo.currentData()),
            source_crs=self.crs_text.text().strip() or None,
            profile_name=Path(destination).stem,
        )
        errors = profile.validate(self.current_columns)
        if errors:
            QMessageBox.warning(self, PLUGIN_NAME, "\n".join(errors))
            return
        try:
            save_mapping_profile(profile, destination)
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))
            return
        QMessageBox.information(self, PLUGIN_NAME, f"Mapping profile saved to {destination}")

    def _load_profile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load yield column mapping",
            "",
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            profile = load_mapping_profile(path)
            errors = profile.validate(self.current_columns) if self.current_columns else []
            if errors:
                raise ValueError("; ".join(errors))
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))
            return
        crop_index = self.crop_combo.findData(profile.crop_code)
        units_index = self.units_combo.findData(profile.unit_profile)
        self.crop_combo.setCurrentIndex(max(0, crop_index))
        self.units_combo.setCurrentIndex(max(0, units_index))
        self.crs_text.setText(profile.source_crs or "")
        if self.current_columns:
            self._populate_mapping_table(profile.mapping)
