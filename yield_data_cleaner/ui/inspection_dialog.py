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
        self.tabs.addTab(self._build_audit_tab(), "2. Canonical Audit")
        self.tabs.addTab(self._build_boundary_tab(), "3. Field Boundary")
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
        refresh_button = QPushButton("Refresh layers")
        refresh_button.clicked.connect(self._refresh_layers)
        layer_row = QHBoxLayout()
        layer_row.addWidget(self.layer_combo, 1)
        layer_row.addWidget(refresh_button)
        self.file_path = QLineEdit()
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

        inspect_button = QPushButton("Inspect columns and CRS")
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
        return tab

    def _build_audit_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        intro = QLabel(
            "Create the vendor-neutral audit layer from the inspected source and the "
            "reviewed mapping on the first tab. No observations are cleaned or deleted."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        settings = QGroupBox("Canonical audit output")
        form = QFormLayout(settings)
        self.audit_output_folder = QLineEdit()
        self.audit_output_folder.setPlaceholderText("Choose a new or empty run folder")
        browse = QPushButton("Browse...")
        browse.clicked.connect(lambda: self._browse_output_folder(self.audit_output_folder))
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.audit_output_folder, 1)
        folder_row.addWidget(browse)
        self.audit_output_crs = QLineEdit()
        self.audit_output_crs.setPlaceholderText(
            "Optional, for example EPSG:32616; leave blank for automatic local CRS"
        )
        form.addRow("Run folder", folder_row)
        form.addRow("Analysis/output CRS", self.audit_output_crs)
        layout.addWidget(settings)

        run_button = QPushButton("Create canonical audit layer")
        run_button.setObjectName("createCanonicalAuditButton")
        run_button.clicked.connect(self._run_canonical_audit)
        layout.addWidget(run_button)
        self.audit_status = QTextBrowser()
        self.audit_status.setHtml(
            "<h3>Ready after input review</h3>"
            "<p>Inspect the source and review its mapping on the first tab, then choose "
            "a run folder here.</p>"
        )
        layout.addWidget(self.audit_status, 1)
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
        self.boundary_file_path = QLineEdit()
        self.boundary_file_path.setPlaceholderText(
            "Optional polygon file; used instead of the loaded-layer selection"
        )
        self.boundary_browse_button = QPushButton("Browse...")
        self.boundary_browse_button.clicked.connect(self._browse_boundary_file)
        boundary_file_row = QHBoxLayout()
        boundary_file_row.addWidget(self.boundary_file_path, 1)
        boundary_file_row.addWidget(self.boundary_browse_button)

        self.use_inspected_source = QCheckBox("Use the source selected on Input & Mapping")
        self.use_inspected_source.setChecked(True)
        self.boundary_point_combo = QComboBox()
        self.boundary_point_combo.currentIndexChanged.connect(self._refresh_width_fields)
        self.boundary_point_file = QLineEdit()
        self.boundary_point_file.setPlaceholderText(
            "Optional QGIS-readable point file; used instead of the loaded layer"
        )
        self.point_browse_button = QPushButton("Browse...")
        self.point_browse_button.clicked.connect(self._browse_boundary_points)
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

        self.boundary_output_folder = QLineEdit()
        self.boundary_output_folder.setPlaceholderText(
            "Choose a run folder, or leave blank to use the canonical-audit folder"
        )
        output_browse = QPushButton("Browse...")
        output_browse.clicked.connect(
            lambda: self._browse_output_folder(self.boundary_output_folder)
        )
        output_row = QHBoxLayout()
        output_row.addWidget(self.boundary_output_folder, 1)
        output_row.addWidget(output_browse)

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
        form.addRow("Run folder", output_row)
        layout.addWidget(settings)

        run_button = QPushButton("Prepare field boundary")
        run_button.setObjectName("prepareFieldBoundaryButton")
        run_button.clicked.connect(self._run_field_boundary)
        layout.addWidget(run_button)
        self.boundary_status = QTextBrowser()
        self.boundary_status.setHtml(
            "<h3>No boundary prepared</h3>"
            "<p>Select an existing boundary or choose derivation settings above.</p>"
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

    def _update_help(self, index):
        pages = (
            """
            <h2>Input &amp; Mapping</h2>
            <ol>
              <li>Select a point layer already loaded in QGIS, or browse for a local file.</li>
              <li>Click <b>Inspect columns and CRS</b>.</li>
              <li>Confirm crop, units, source CRS, and every proposed column mapping.</li>
              <li>Save the mapping if you expect to use this export format again.</li>
              <li>Continue with the <b>Canonical Audit</b> tab.</li>
            </ol>
            <p><b>Important:</b> Inspection is read-only. A low-confidence CRS or mapping
            must be reviewed before spatial calculations are run.</p>
            """,
            """
            <h2>Canonical Audit</h2>
            <ol>
              <li>Complete Input &amp; Mapping first.</li>
              <li>Choose a new or empty run folder.</li>
              <li>Leave the analysis CRS blank to choose a suitable local projected CRS
              automatically, or enter an explicit EPSG code.</li>
              <li>Click <b>Create canonical audit layer</b>.</li>
            </ol>
            <p>The result preserves source attributes, adds normalized audit fields, and
            records the reviewed mapping and CRS decisions. It does not clean or discard
            observations.</p>
            """,
            """
            <h2>Field Boundary</h2>
            <h3>Existing boundary</h3>
            <p>Select one loaded polygon, or browse for a polygon file. A browsed file
            takes precedence over the loaded-layer selection.</p>
            <h3>Derived boundary</h3>
            <p>Use projected canonical yield points when possible. Confirm the swath-width
            field and fallback width. The default display is Imperial; values are converted
            to meters for processing.</p>
            <p><b>Always inspect a derived boundary on the map.</b> It represents harvested
            extent, not a legal or ownership boundary.</p>
            """,
        )
        self.help_panel.setHtml(pages[index] if 0 <= index < len(pages) else pages[0])

    def _browse_output_folder(self, target):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select yield-cleaning run folder",
            target.text().strip() or self.audit_output_folder.text().strip(),
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
    def _require_available_outputs(paths):
        collisions = [str(path) for path in paths if path.exists()]
        if collisions:
            raise ValueError(
                "The run folder already contains output files. Choose a new folder: "
                + ", ".join(collisions)
            )

    @staticmethod
    def _gpkg_sink_uri(path, layer_name):
        """Build a Processing provider URI for a named GeoPackage layer."""

        safe_path = str(path).replace("\\", "/").replace("'", "''")
        safe_layer = str(layer_name).replace('"', '""')
        return f"ogr:dbname='{safe_path}' table=\"{safe_layer}\" (geom)"

    def _run_canonical_audit(self):
        try:
            if not self.current_columns:
                raise ValueError("Inspect the input and review its mapping first")
            folder_text = self.audit_output_folder.text().strip()
            if not folder_text:
                raise ValueError("Choose a canonical-audit run folder")
            folder = Path(folder_text)
            folder.mkdir(parents=True, exist_ok=True)
            mapping_path = folder / "column_mapping.json"
            report_path = folder / "applied_column_mapping.json"
            manifest_path = folder / "run_manifest.json"
            geopackage_path = folder / "yield_cleaning_results.gpkg"
            self._require_available_outputs(
                (mapping_path, report_path, manifest_path, geopackage_path)
            )
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
            save_mapping_profile(profile, mapping_path)
            source, input_file = self._selected_input_source()
            import processing

            result = processing.run(
                "yield_data_cleaner:create_canonical_audit",
                {
                    "SOURCE": source,
                    "INPUT_FILE": input_file,
                    "MAPPING_PROFILE": str(mapping_path),
                    "CROP": self.crop_combo.currentIndex(),
                    "UNIT_PROFILE": self.units_combo.currentIndex(),
                    "SOURCE_CRS": self.crs_text.text().strip() or None,
                    "OUTPUT_CRS": self.audit_output_crs.text().strip() or None,
                    "MAPPING_REPORT": str(report_path),
                    "RUN_MANIFEST": str(manifest_path),
                    "OUTPUT": self._gpkg_sink_uri(geopackage_path, "canonical_observations"),
                },
            )
            output_uri = str(result.get("OUTPUT") or geopackage_path)
            layer = QgsVectorLayer(output_uri, "Canonical yield audit", "ogr")
            if not layer.isValid():
                layer = QgsVectorLayer(
                    f"{geopackage_path}|layername=canonical_observations",
                    "Canonical yield audit",
                    "ogr",
                )
            if not layer.isValid():
                raise ValueError("The audit completed, but QGIS could not open its output layer")
            QgsProject.instance().addMapLayer(layer)
            self.audit_status.setHtml(
                "<h3>Canonical audit created</h3>"
                f"<p><b>Layer:</b> {html.escape(layer.name())}</p>"
                f"<p><b>Run folder:</b> {html.escape(str(folder))}</p>"
                "<p>Source observations were preserved. Continue to Field Boundary.</p>"
            )
            if not self.boundary_output_folder.text().strip():
                self.boundary_output_folder.setText(str(folder))
            self._refresh_layers()
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))

    def _run_field_boundary(self):
        try:
            folder_text = (
                self.boundary_output_folder.text().strip()
                or self.audit_output_folder.text().strip()
            )
            if not folder_text:
                raise ValueError("Choose a field-boundary run folder")
            folder = Path(folder_text)
            folder.mkdir(parents=True, exist_ok=True)
            provenance_path = folder / "field_boundary_provenance.json"
            geopackage_path = folder / "yield_cleaning_results.gpkg"
            self._require_available_outputs((provenance_path,))
            existing_output = QgsVectorLayer(
                f"{geopackage_path}|layername=field_boundary",
                "Existing field boundary",
                "ogr",
            )
            if existing_output.isValid():
                raise ValueError(
                    "The run folder already contains a field_boundary layer. "
                    "Choose a new folder."
                )

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
                    existing_boundary = QgsProject.instance().mapLayer(
                        self.boundary_layer_ids[index]
                    )
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
                    yield_points = QgsProject.instance().mapLayer(
                        self.boundary_point_layer_ids[index]
                    )

            import processing

            result = processing.run(
                "yield_data_cleaner:prepare_field_boundary",
                {
                    "MODE": self.boundary_mode.currentIndex(),
                    "EXISTING_BOUNDARY": existing_boundary,
                    "YIELD_POINTS": yield_points,
                    "WIDTH_FIELD": self.width_field.currentText().strip() or None,
                    "DEFAULT_WIDTH": self.default_width.value() * 0.3048,
                    "GAP_CLOSING": self.gap_closing.value() * 0.3048,
                    "CONCAVITY": self.concavity.value(),
                    "PROVENANCE": str(provenance_path),
                    "OUTPUT": self._gpkg_sink_uri(geopackage_path, "field_boundary"),
                },
            )
            output_uri = str(result.get("OUTPUT") or geopackage_path)
            layer = QgsVectorLayer(output_uri, "Prepared field boundary", "ogr")
            if not layer.isValid():
                layer = QgsVectorLayer(
                    f"{geopackage_path}|layername=field_boundary",
                    "Prepared field boundary",
                    "ogr",
                )
            if not layer.isValid():
                raise ValueError("Boundary processing completed, but QGIS could not open it")
            QgsProject.instance().addMapLayer(layer)
            review_text = (
                "Visually review this derived operational boundary before accepting it."
                if self.boundary_mode.currentIndex() == 1
                else "The existing boundary was validated and prepared."
            )
            self.boundary_status.setHtml(
                "<h3>Field boundary prepared</h3>"
                f"<p><b>Layer:</b> {html.escape(layer.name())}</p>"
                f"<p><b>Run folder:</b> {html.escape(str(folder))}</p>"
                f"<p>{html.escape(review_text)}</p>"
            )
            self._refresh_layers()
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))

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
