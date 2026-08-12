# SPDX-License-Identifier: GPL-3.0-or-later
"""First guided vertical slice for input, mapping, and CRS inspection."""

from __future__ import annotations

import html
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextBrowser,
    QVBoxLayout,
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
        self.setWindowTitle(f"{PLUGIN_NAME} {VERSION} - Input inspection")
        self.resize(780, 650)
        self._build_ui()
        self._refresh_layers()

    def _build_ui(self):
        layout = QVBoxLayout(self)
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
        audit_button = QPushButton("Open canonical audit tool...")
        audit_button.clicked.connect(self._open_audit_tool)
        boundary_button = QPushButton("Open boundary tool...")
        boundary_button.clicked.connect(self._open_boundary_tool)
        profile_buttons.addWidget(load_button)
        profile_buttons.addWidget(save_button)
        profile_buttons.addStretch(1)
        profile_buttons.addWidget(boundary_button)
        profile_buttons.addWidget(audit_button)
        mapping_layout.addLayout(profile_buttons)
        layout.addWidget(mapping_group, 2)

        buttons = QDialogButtonBox(enum_member(QDialogButtonBox, "StandardButton", "Close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_layers(self):
        self.layer_combo.clear()
        self.layer_ids = []
        point_geometry = enum_member(QgsWkbTypes, "GeometryType", "PointGeometry")
        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            if QgsWkbTypes.geometryType(layer.wkbType()) != point_geometry:
                continue
            self.layer_combo.addItem(layer.name())
            self.layer_ids.append(layer.id())

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

    def _open_audit_tool(self):
        if self.iface is None:
            QMessageBox.information(
                self,
                PLUGIN_NAME,
                "Open Processing Toolbox > Yield Data Cleaner > "
                "Create canonical yield audit layer.",
            )
            return
        try:
            import processing

            processing.execAlgorithmDialog("yield_data_cleaner:create_canonical_audit", {})
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))

    def _open_boundary_tool(self):
        if self.iface is None:
            QMessageBox.information(
                self,
                PLUGIN_NAME,
                "Open Processing Toolbox > Yield Data Cleaner > Prepare field boundary.",
            )
            return
        try:
            import processing

            processing.execAlgorithmDialog("yield_data_cleaner:prepare_field_boundary", {})
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))
