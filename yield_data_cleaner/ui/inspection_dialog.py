# SPDX-License-Identifier: GPL-3.0-or-later
"""First guided vertical slice for input, mapping, and CRS inspection."""

from __future__ import annotations

import html
import math
from pathlib import Path

from qgis.PyQt.QtCore import QUrl, Qt
from qgis.PyQt.QtGui import QColor, QDesktopServices, QGuiApplication
from qgis.PyQt.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
    QgsWkbTypes,
)

try:
    from qgis.gui import (
        QgsMapCanvas,
        QgsMapTool,
        QgsMapToolPan,
        QgsMapToolZoom,
        QgsRubberBand,
        QgsVertexMarker,
    )
except ImportError:
    QgsMapCanvas = None
    QgsMapTool = object
    QgsVertexMarker = None
    QgsMapToolPan = None
    QgsMapToolZoom = None
    QgsRubberBand = None

from ..boundaries.derivation import fill_polygon_holes, simplify_boundary_geometry
from ..compat import enum_member, qgis_field_type
from ..core.column_detection import FIELD_ALIASES, detect_columns
from ..core.crop_profiles import available_crops, crop_profile, detect_crop_code
from ..core.crs_service import recognize_crs
from ..core.delimited_text import inspect_delimited_file
from ..core.filter_engine import run_cleaning_filters
from ..core.mapping_profile import MappingProfile, load_mapping_profile, save_mapping_profile
from ..core.pass_reconstruction import reconstruct_passes
from ..core.recipe import CleaningRecipe, default_recipe_for_crop
from ..core.run_naming import build_run_stem, next_available_run_folder, run_file_paths
from ..core.run_package import write_run_package
from ..core.settings import PLUGIN_NAME
from ..core.units import (
    bushels_per_acre_to_kg_per_hectare,
    kg_per_hectare_to_bushels_per_acre,
    mph_to_m_per_s,
    m_per_s_to_mph,
)
from ..exporters.adapt_standard import export_adapt_standard_package
from .map_styling import (
    get_layer_graduated_legend_items,
    style_layer_for_display,
    style_layer_with_attribute_and_ramp,
)
from ..version import VERSION

CANONICAL_FIELD_DISPLAY_LABELS = {
    "yield_dry_mass_area": "Dry Yield (bu/ac Volumetric / kg/ha)",
    "yield_wet_mass_area": "Wet Yield (bu/ac Volumetric / kg/ha)",
    "mass_flow_wet": "Mass Flow Rate Wet (lb/s or kg/s)",
    "mass_flow_dry": "Mass Flow Rate Dry (lb/s or kg/s)",
    "moisture_pct": "Grain Moisture (%)",
    "speed_m_s": "Ground Speed (mph or m/s)",
    "swath_width_m": "Swath / Header Width (ft or m)",
    "distance_m": "Distance (ft or m)",
    "duration_s": "Duration (s)",
    "heading_deg": "Track / Heading (deg)",
    "header_engaged": "Header Engaged / Work State",
    "elevation_m": "Elevation (ft or m)",
    "crop_code": "Crop / Product Name",
    "machine_id": "Machine / Combine ID",
    "source_pass_id": "Pass Number / ID",
    "timestamp_utc": "Date & Time (UTC)",
    "date": "Harvest Date",
    "time": "Harvest Time",
    "x": "Longitude / Easting (X)",
    "y": "Latitude / Northing (Y)",
    "source_sequence": "Source Sequence / ID",
}

CANONICAL_FIELD_UNITS = {
    "yield_dry_mass_area": [
        ("bu/ac (Volume)", "bu/ac"),
        ("kg/ha (Mass)", "kg/ha"),
        ("tonne/ha (Mass)", "tonne/ha"),
        ("lb/ac (Mass)", "lb/ac"),
    ],
    "yield_wet_mass_area": [
        ("bu/ac (Volume)", "bu/ac"),
        ("kg/ha (Mass)", "kg/ha"),
        ("tonne/ha (Mass)", "tonne/ha"),
        ("lb/ac (Mass)", "lb/ac"),
    ],
    "moisture_pct": [
        ("% (Percentage)", "%"),
        ("fraction (0.0-1.0)", "fraction"),
    ],
    "swath_width_m": [
        ("ft (Feet)", "ft"),
        ("in (Inches)", "in"),
        ("m (Meters)", "m"),
        ("cm (Centimeters)", "cm"),
        ("rows (30 in / row)", "rows_30in"),
    ],
    "speed_m_s": [
        ("mph (Miles/hr)", "mph"),
        ("km/h (Kilometers/hr)", "km/h"),
        ("m/s (Meters/sec)", "m/s"),
        ("ft/s (Feet/sec)", "ft/s"),
    ],
    "elevation_m": [
        ("ft (Feet)", "ft"),
        ("m (Meters)", "m"),
    ],
    "test_weight": [
        ("lb/bu (Imperial)", "lb/bu"),
        ("kg/hL (Metric)", "kg/hL"),
        ("kg/m³", "kg/m3"),
    ],
    "temperature_c": [
        ("°F (Fahrenheit)", "F"),
        ("°C (Celsius)", "C"),
    ],
    "time_seconds": [
        ("seconds", "s"),
        ("minutes", "min"),
        ("hours", "hr"),
    ],
    "timestamp": [
        ("ISO / Auto", "auto"),
        ("Epoch seconds", "epoch_s"),
        ("Epoch ms", "epoch_ms"),
    ],
    "heading_deg": [
        ("degrees (0 - 360°)", "deg"),
        ("radians", "rad"),
    ],
    "pass_number": [
        ("integer", "int"),
    ],
    "source_sequence": [
        ("integer", "int"),
    ],
    "crop_code": [
        ("text / name / id", "text"),
    ],
    "x": [
        ("degrees / coords", "coord"),
    ],
    "y": [
        ("degrees / coords", "coord"),
    ],
}


def _extract_representative_samples(values_list):
    """Extract an informative, representative summary of sample values from a dataset column."""
    cleaned = []
    for v in values_list:
        if v is None:
            continue
        s = str(v).strip()
        if s == "" or s.lower() in {"null", "none", "nan"}:
            continue
        cleaned.append(s)

    if not cleaned:
        return "—"

    # Try numeric conversion
    numeric_vals = []
    for s in cleaned:
        try:
            num = float(s)
            if not math.isnan(num) and not math.isinf(num):
                numeric_vals.append(num)
        except (ValueError, TypeError):
            pass

    if len(numeric_vals) >= len(cleaned) * 0.7 and len(numeric_vals) >= 2:
        min_v = min(numeric_vals)
        max_v = max(numeric_vals)
        non_zero = [v for v in numeric_vals if abs(v) > 1e-5]
        active_nums = non_zero if len(non_zero) >= 2 else numeric_vals
        active_nums.sort()

        n = len(active_nums)
        if n <= 4:
            sample_pts = active_nums
        else:
            pct_indices = [int(n * p) for p in (0.1, 0.35, 0.65, 0.9)]
            sample_pts = [active_nums[min(idx, n - 1)] for idx in pct_indices]
            unique_pts = []
            for p in sample_pts:
                if not any(abs(p - u) < 1e-4 for u in unique_pts):
                    unique_pts.append(p)
            sample_pts = unique_pts if len(unique_pts) >= 2 else active_nums[:3]

        def _fmt(val):
            if abs(val - round(val)) < 1e-4:
                return f"{int(round(val))}"
            return f"{val:.2f}"

        samples_str = ", ".join(_fmt(v) for v in sample_pts)
        if min_v != max_v:
            return f"{samples_str} (range: {_fmt(min_v)} – {_fmt(max_v)})"
        return samples_str

    # Categorical / text values
    counts = {}
    for s in cleaned:
        counts[s] = counts.get(s, 0) + 1
    sorted_unique = sorted(counts.keys(), key=lambda k: counts[k], reverse=True)
    if len(sorted_unique) <= 3:
        return ", ".join(f"'{k}'" for k in sorted_unique)
    else:
        top3 = ", ".join(f"'{k}'" for k in sorted_unique[:3])
        return f"{top3} (+{len(sorted_unique) - 3} more)"


class ModalBoundaryVertexTool(QgsMapTool):
    """Interactive in-modal vertex editor tool for QgsMapCanvas."""

    def __init__(self, canvas, layer_getter_callback, on_modified_callback=None):
        if QgsMapTool is not object:
            super().__init__(canvas)
        self.canvas = canvas
        self.get_layer = layer_getter_callback
        self.on_modified = on_modified_callback
        self.dragging_idx = None
        self.markers = []
        self.vertex_points = []

    def refresh_markers(self):
        for m in self.markers:
            try:
                self.canvas.scene().removeItem(m)
            except Exception:
                pass
        self.markers.clear()
        self.vertex_points.clear()

        layer = self.get_layer()
        if not layer or not layer.isValid():
            return

        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            if geom.isMultipart():
                multi = geom.asMultiPolygon()
                for part_idx, poly in enumerate(multi):
                    for ring_idx, ring in enumerate(poly):
                        for v_idx, pt in enumerate(ring):
                            if v_idx == len(ring) - 1 and len(ring) > 1 and pt == ring[0]:
                                continue
                            self._add_marker(feat.id(), part_idx, ring_idx, v_idx, QgsPointXY(pt))
            else:
                poly = geom.asPolygon()
                for ring_idx, ring in enumerate(poly):
                    for v_idx, pt in enumerate(ring):
                        if v_idx == len(ring) - 1 and len(ring) > 1 and pt == ring[0]:
                            continue
                        self._add_marker(feat.id(), 0, ring_idx, v_idx, QgsPointXY(pt))

    def _add_marker(self, fid, part_idx, ring_idx, v_idx, pt_xy):
        if QgsVertexMarker is None:
            return
        m = QgsVertexMarker(self.canvas)
        m.setCenter(pt_xy)
        m.setColor(QColor("#2563eb"))
        m.setIconType(QgsVertexMarker.ICON_BOX)
        m.setIconSize(9)
        m.setPenWidth(2)
        self.markers.append(m)
        self.vertex_points.append((fid, part_idx, ring_idx, v_idx, pt_xy))

    def clear(self):
        for m in self.markers:
            try:
                self.canvas.scene().removeItem(m)
            except Exception:
                pass
        self.markers.clear()
        self.vertex_points.clear()
        self.dragging_idx = None

    def _find_nearest_vertex(self, canvas_pt):
        best_idx = None
        best_dist = 18.0
        for i, (_, _, _, _, pt_xy) in enumerate(self.vertex_points):
            c_pt = self.toCanvasCoordinates(pt_xy)
            dist = math.hypot(canvas_pt.x() - c_pt.x(), canvas_pt.y() - c_pt.y())
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        return best_idx

    def _find_nearest_edge(self, map_pt, canvas_pt):
        layer = self.get_layer()
        if not layer:
            return None
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            try:
                dist_sq, min_pt, after_idx, left_of = geom.closestSegmentWithContext(map_pt)
                canvas_min = self.toCanvasCoordinates(min_pt)
                pixel_dist = math.hypot(canvas_pt.x() - canvas_min.x(), canvas_pt.y() - canvas_min.y())
                if pixel_dist <= 14.0:
                    return (feat.id(), min_pt, after_idx)
            except Exception:
                pass
        return None

    def canvasPressEvent(self, e):
        layer = self.get_layer()
        if not layer or not layer.isValid():
            return

        canvas_pt = e.pos()
        map_pt = self.toMapCoordinates(canvas_pt)
        v_idx = self._find_nearest_vertex(canvas_pt)

        btn = e.button()
        is_right = btn == enum_member(Qt, "MouseButton", "RightButton") or btn == 2
        is_left = btn == enum_member(Qt, "MouseButton", "LeftButton") or btn == 1
        is_mid = btn == enum_member(Qt, "MouseButton", "MiddleButton") or btn == 4

        # Middle click -> Start panning canvas
        if is_mid:
            self.is_panning = True
            try:
                self.canvas.panAction(e)
            except Exception:
                pass
            return

        # Right click on vertex -> Delete vertex
        if is_right:
            if v_idx is not None:
                fid, part_idx, ring_idx, vertex_idx, _ = self.vertex_points[v_idx]
                for feat in layer.getFeatures():
                    if feat.id() == fid:
                        geom = QgsGeometry(feat.geometry())
                        try:
                            geom.deleteVertex(vertex_idx)
                            if not geom.isEmpty() and geom.isGeosValid():
                                layer.startEditing()
                                layer.changeGeometry(fid, geom)
                                layer.commitChanges()
                                self.refresh_markers()
                                self.canvas.refresh()
                                if self.on_modified:
                                    self.on_modified("Vertex deleted.")
                        except Exception:
                            pass
                return
            else:
                self.is_panning = True
                try:
                    self.canvas.panAction(e)
                except Exception:
                    pass
                return

        # Left click on vertex -> Start dragging
        if is_left:
            if v_idx is not None:
                self.dragging_idx = v_idx
                if v_idx < len(self.markers):
                    self.markers[v_idx].setColor(QColor("#dc2626"))
                    self.markers[v_idx].setIconSize(12)
                return

            # Left click on segment -> Add new vertex
            edge_info = self._find_nearest_edge(map_pt, canvas_pt)
            if edge_info:
                fid, insert_pt, after_idx = edge_info
                for feat in layer.getFeatures():
                    if feat.id() == fid:
                        geom = QgsGeometry(feat.geometry())
                        try:
                            geom.insertVertex(insert_pt.x(), insert_pt.y(), after_idx)
                            if not geom.isEmpty() and geom.isGeosValid():
                                layer.startEditing()
                                layer.changeGeometry(fid, geom)
                                layer.commitChanges()
                                self.refresh_markers()
                                self.canvas.refresh()
                                if self.on_modified:
                                    self.on_modified("New vertex added on boundary edge.")
                        except Exception:
                            pass
                return

            # Left click on empty space -> Seamless pan without leaving vertex mode
            self.is_panning = True
            try:
                self.canvas.panAction(e)
            except Exception:
                pass
            return

    def canvasMoveEvent(self, e):
        if self.dragging_idx is not None and self.dragging_idx < len(self.vertex_points):
            new_map_pt = self.toMapCoordinates(e.pos())
            self.markers[self.dragging_idx].setCenter(new_map_pt)
            self.markers[self.dragging_idx].update()
        elif getattr(self, "is_panning", False):
            try:
                self.canvas.panAction(e)
            except Exception:
                pass

    def canvasReleaseEvent(self, e):
        if getattr(self, "is_panning", False):
            self.is_panning = False
            try:
                self.canvas.panActionEnd(e.pos())
            except Exception:
                pass
            return

        if self.dragging_idx is not None:
            layer = self.get_layer()
            if layer and layer.isValid():
                new_map_pt = self.toMapCoordinates(e.pos())
                fid, part_idx, ring_idx, vertex_idx, _ = self.vertex_points[self.dragging_idx]
                for feat in layer.getFeatures():
                    if feat.id() == fid:
                        geom = QgsGeometry(feat.geometry())
                        try:
                            geom.moveVertex(new_map_pt.x(), new_map_pt.y(), vertex_idx)
                            if not geom.isEmpty():
                                layer.startEditing()
                                layer.changeGeometry(fid, geom)
                                layer.commitChanges()
                        except Exception:
                            pass
                self.refresh_markers()
                self.canvas.refresh()
                if self.on_modified:
                    self.on_modified("Vertex moved.")
            self.dragging_idx = None


class ModalPointSelectTool(QgsMapTool):
    """Interactive rectangle / click point selection tool on the in-modal Clean & Review canvas."""

    def __init__(self, canvas, layer_getter, on_selection_changed=None):
        if QgsMapTool is not object:
            super().__init__(canvas)
        self.canvas = canvas
        self.layer_getter = layer_getter
        self.on_selection_changed = on_selection_changed
        if QgsRubberBand is not None and canvas is not None:
            self.rubber_band = QgsRubberBand(canvas, enum_member(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
            self.rubber_band.setColor(QColor(254, 240, 138, 90))
            self.rubber_band.setStrokeColor(QColor(202, 138, 4, 220))
            self.rubber_band.setWidth(2)
        else:
            self.rubber_band = None
        self.start_point = None
        self.is_dragging = False

    def canvasPressEvent(self, event):
        if event.button() == enum_member(Qt, "MouseButton", "LeftButton") or event.button() == 1:
            self.start_point = self.toMapCoordinates(event.pos())
            if self.rubber_band:
                self.rubber_band.reset(enum_member(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
            self.is_dragging = True

    def canvasMoveEvent(self, event):
        if self.is_dragging and self.start_point is not None and self.rubber_band:
            curr = self.toMapCoordinates(event.pos())
            rect = QgsRectangle(self.start_point, curr)
            self.rubber_band.setToGeometry(QgsGeometry.fromRect(rect), None)
            self.rubber_band.show()

    def canvasReleaseEvent(self, event):
        if (event.button() == enum_member(Qt, "MouseButton", "LeftButton") or event.button() == 1) and self.is_dragging:
            self.is_dragging = False
            if self.rubber_band:
                self.rubber_band.hide()
            end_point = self.toMapCoordinates(event.pos())
            rect = QgsRectangle(self.start_point, end_point)
            layer = self.layer_getter()
            if layer and layer.isValid():
                if abs(rect.width()) < 1e-6 or abs(rect.height()) < 1e-6:
                    buffer_dist = self.canvas.mapUnitsPerPixel() * 8.0
                    rect = QgsRectangle(
                        end_point.x() - buffer_dist,
                        end_point.y() - buffer_dist,
                        end_point.x() + buffer_dist,
                        end_point.y() + buffer_dist,
                    )
                shift = bool(event.modifiers() & enum_member(Qt, "KeyboardModifier", "ShiftModifier"))
                if shift:
                    layer.selectByRect(rect, enum_member(QgsVectorLayer, "SelectBehavior", "AddToSelection"))
                else:
                    layer.selectByRect(rect, enum_member(QgsVectorLayer, "SelectBehavior", "SetSelection"))
                self.canvas.refresh()
                if self.on_selection_changed:
                    self.on_selection_changed(list(layer.selectedFeatureIds()))

    def deactivate(self):
        if hasattr(self, "rubber_band") and self.rubber_band:
            self.rubber_band.hide()
        super().deactivate()


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
        self.current_run_folder = None
        self.current_run_paths = None
        self.current_prepared_layer = None
        self.current_review_html_path = None
        self.current_cleaning_result = None
        self.current_observations = []
        self.current_crop_code = "corn"
        self.current_unit_profile = "imperial"
        self.manual_excluded_ids = set()
        self.manual_restored_ids = set()
        self.setWindowTitle(f"{PLUGIN_NAME} {VERSION} - Guided workflow")
        screen = QGuiApplication.primaryScreen() if QGuiApplication is not None else None
        if screen:
            avail = screen.availableGeometry()
            target_w = min(1180, max(750, int(avail.width() * 0.90)))
            target_h = min(740, max(520, int(avail.height() * 0.88)))
            self.resize(target_w, target_h)
        else:
            self.resize(1050, 620)
        self._build_ui()
        self._refresh_layers()

    def _wrap_in_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(enum_member(QFrame, "Shape", "NoFrame"))
        return scroll

    def _build_ui(self):
        self.setStyleSheet("""
            QPushButton#inspectInputButton,
            QPushButton#continueToBoundaryButton,
            QPushButton#confirmFieldBoundaryButton,
            QPushButton#createPreparedDatasetButton,
            QPushButton#continueToCleanButton,
            QPushButton#executeCleaningButton {
                background-color: #d32f2f;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 4px;
                border: 1px solid #b71c1c;
                min-height: 24px;
            }
            QPushButton#inspectInputButton:hover,
            QPushButton#continueToBoundaryButton:hover,
            QPushButton#confirmFieldBoundaryButton:hover,
            QPushButton#createPreparedDatasetButton:hover,
            QPushButton#continueToCleanButton:hover,
            QPushButton#executeCleaningButton:hover {
                background-color: #b71c1c;
                border-color: #7f0000;
            }
            QPushButton#inspectInputButton:pressed,
            QPushButton#continueToBoundaryButton:pressed,
            QPushButton#confirmFieldBoundaryButton:pressed,
            QPushButton#createPreparedDatasetButton:pressed,
            QPushButton#continueToCleanButton:pressed,
            QPushButton#executeCleaningButton:pressed {
                background-color: #7f0000;
            }
            QPushButton#inspectInputButton:disabled,
            QPushButton#continueToBoundaryButton:disabled,
            QPushButton#confirmFieldBoundaryButton:disabled,
            QPushButton#createPreparedDatasetButton:disabled,
            QPushButton#continueToCleanButton:disabled,
            QPushButton#executeCleaningButton:disabled {
                background-color: #e2e8f0;
                color: #94a3b8;
                border: 1px solid #cbd5e1;
            }
        """)
        layout = QVBoxLayout(self)
        workspace = QHBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.setObjectName("yieldDataCleanerWorkflowTabs")
        self.tabs.addTab(self._wrap_in_scroll(self._build_input_tab()), "1. Input & Mapping")
        self.tabs.addTab(self._wrap_in_scroll(self._build_boundary_tab()), "2. Field Boundary")
        self.tabs.addTab(self._wrap_in_scroll(self._build_prepare_tab()), "3. Prepare Dataset")
        self.tabs.addTab(self._wrap_in_scroll(self._build_clean_tab()), "4. Clean & Review")
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

        bottom_layout = QHBoxLayout()
        self.reset_tool_button = QPushButton("Reset Tool")
        self.reset_tool_button.setObjectName("yieldDataCleanerResetButton")
        self.reset_tool_button.setToolTip("Reset all inputs and results to start over with a new field")
        self.reset_tool_button.setStyleSheet(
            "QPushButton { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 14px; font-weight: 600; } "
            "QPushButton:hover { background-color: #e2e8f0; color: #0f172a; border-color: #94a3b8; }"
        )
        self.reset_tool_button.clicked.connect(self._reset_tool)
        bottom_layout.addWidget(self.reset_tool_button)

        bottom_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.setStyleSheet(
            "QPushButton { background-color: #f8fafc; color: #334155; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 16px; font-weight: 500; } "
            "QPushButton:hover { background-color: #f1f5f9; color: #0f172a; border-color: #94a3b8; }"
        )
        close_button.clicked.connect(self.reject)
        bottom_layout.addWidget(close_button)

        layout.addLayout(bottom_layout)
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
        self.layer_combo.currentIndexChanged.connect(self._on_layer_selection_changed)
        refresh_button = QPushButton("Refresh layers")
        refresh_button.clicked.connect(self._refresh_layers)
        layer_row = QHBoxLayout()
        layer_row.addWidget(self.layer_combo, 1)
        layer_row.addWidget(refresh_button)
        self.file_path = QLineEdit()
        self.file_path.textChanged.connect(self._on_file_path_changed)
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

        self.inspect_button = QPushButton("Inspect input")
        self.inspect_button.setObjectName("inspectInputButton")
        self.inspect_button.clicked.connect(self._inspect)
        self._style_button_action_needed(self.inspect_button)
        layout.addWidget(self.inspect_button)
        self.inspect_progress = QProgressBar()
        self.inspect_progress.setRange(0, 0)
        self.inspect_progress.setVisible(False)
        layout.addWidget(self.inspect_progress)
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
        for p in available_crops():
            self.crop_combo.addItem(p.display_name, p.code)
        self.crop_combo.currentIndexChanged.connect(self._on_crop_changed)

        self.test_weight_spin = QDoubleSpinBox()
        self.test_weight_spin.setRange(10.0, 100.0)
        self.test_weight_spin.setValue(56.0)
        self.test_weight_spin.setSuffix(" lb/bu")
        self.test_weight_spin.setToolTip("Standard bushel test weight reference for crop yield conversions.")

        self.standard_moisture_spin = QDoubleSpinBox()
        self.standard_moisture_spin.setRange(1.0, 40.0)
        self.standard_moisture_spin.setValue(15.5)
        self.standard_moisture_spin.setSuffix(" %")
        self.standard_moisture_spin.setToolTip("Standard commercial harvest moisture basis.")

        self.units_combo = QComboBox()
        self.units_combo.addItem("Imperial (default)", "imperial")
        self.units_combo.addItem("Metric", "metric")
        self.crs_text = QLineEdit()
        self.crs_text.setPlaceholderText("Example: EPSG:4326")
        assumptions.addRow("Crop", self.crop_combo)
        assumptions.addRow("Default Test Weight", self.test_weight_spin)
        assumptions.addRow("Standard Market Moisture", self.standard_moisture_spin)
        assumptions.addRow("Source units", self.units_combo)
        assumptions.addRow("Confirmed source CRS", self.crs_text)
        mapping_layout.addLayout(assumptions)
        self.mapping_table = QTableWidget(len(FIELD_ALIASES), 5)
        self.mapping_table.setHorizontalHeaderLabels(
            ("Canonical field", "Source column", "Unit / Format", "Representative values from file", "Evidence")
        )
        self.mapping_table.verticalHeader().setVisible(False)
        resize_contents = enum_member(QHeaderView, "ResizeMode", "ResizeToContents")
        stretch = enum_member(QHeaderView, "ResizeMode", "Stretch")
        self.mapping_table.horizontalHeader().setSectionResizeMode(0, resize_contents)
        self.mapping_table.horizontalHeader().setSectionResizeMode(1, stretch)
        self.mapping_table.horizontalHeader().setSectionResizeMode(2, resize_contents)
        self.mapping_table.horizontalHeader().setSectionResizeMode(3, stretch)
        self.mapping_table.horizontalHeader().setSectionResizeMode(4, stretch)
        for row, canonical in enumerate(FIELD_ALIASES):
            display_label = CANONICAL_FIELD_DISPLAY_LABELS.get(canonical, canonical)
            item = QTableWidgetItem(display_label)
            item.setData(enum_member(Qt, "ItemDataRole", "UserRole"), canonical)
            item.setToolTip(f"Canonical internal field: {canonical}")
            item.setFlags(item.flags() & ~enum_member(Qt, "ItemFlag", "ItemIsEditable"))
            self.mapping_table.setItem(row, 0, item)

            col_combo = QComboBox()
            self.mapping_table.setCellWidget(row, 1, col_combo)

            unit_combo = QComboBox()
            units_list = CANONICAL_FIELD_UNITS.get(canonical, [("—", "")])
            for label, code in units_list:
                unit_combo.addItem(label, code)
            self.mapping_table.setCellWidget(row, 2, unit_combo)

            val_item = QTableWidgetItem("—")
            val_item.setFlags(val_item.flags() & ~enum_member(Qt, "ItemFlag", "ItemIsEditable"))
            self.mapping_table.setItem(row, 3, val_item)

            ev_item = QTableWidgetItem("Not inspected")
            ev_item.setFlags(ev_item.flags() & ~enum_member(Qt, "ItemFlag", "ItemIsEditable"))
            self.mapping_table.setItem(row, 4, ev_item)
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
        self._style_button_action_needed(self.input_continue_button)
        self.input_continue_button.clicked.connect(self._continue_to_boundary)
        layout.addWidget(self.input_continue_button)
        return tab

    def _style_button_action_needed(self, btn: QPushButton, text: str | None = None):
        if text:
            btn.setText(text)
        btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #dc2626;"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  padding: 10px 14px;"
            "  border-radius: 6px;"
            "  border: 1px solid #b91c1c;"
            "}"
            "QPushButton:hover {"
            "  background-color: #b91c1c;"
            "}"
            "QPushButton:disabled {"
            "  background-color: #f87171;"
            "  color: #fef2f2;"
            "}"
        )

    def _style_button_completed(self, btn: QPushButton, text: str | None = None):
        if text:
            btn.setText(text)
        btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #16a34a;"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  padding: 10px 14px;"
            "  border-radius: 6px;"
            "  border: 1px solid #15803d;"
            "}"
            "QPushButton:hover {"
            "  background-color: #15803d;"
            "}"
            "QPushButton:disabled {"
            "  background-color: #86efac;"
            "  color: #f0fdf4;"
            "}"
        )

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
            "Choose a destination directory (Required)"
        )
        self.output_parent_folder.setStyleSheet("border: 2px solid #dc2626; border-radius: 4px; padding: 4px;")
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
        
        save_label = QLabel("<span style='color: #dc2626; font-weight: bold;'>*</span> Destination / Output folder:")
        form.addRow("Field / boundary name", self.field_name)
        form.addRow(save_label, folder_row)
        form.addRow("Analysis/output CRS", self.output_crs)
        form.addRow("New run folder", self.run_name_preview)
        layout.addWidget(settings)

        self.create_dataset_button = QPushButton("Create prepared yield dataset")
        self.create_dataset_button.setObjectName("createPreparedDatasetButton")
        self.create_dataset_button.clicked.connect(self._run_prepare_dataset)
        self._style_button_action_needed(self.create_dataset_button)
        layout.addWidget(self.create_dataset_button)

        self.prepare_progress = QProgressBar()
        self.prepare_progress.setRange(0, 0)
        self.prepare_progress.setVisible(False)
        layout.addWidget(self.prepare_progress)

        self.prepare_continue_button = QPushButton("Continue to Clean & Review")
        self.prepare_continue_button.setObjectName("continueToCleanButton")
        self.prepare_continue_button.setEnabled(False)
        self._style_button_action_needed(self.prepare_continue_button)
        self.prepare_continue_button.clicked.connect(self._continue_to_clean)
        layout.addWidget(self.prepare_continue_button)

        self.prepare_map_group = QGroupBox("Prepared Yield Observations Preview")
        map_group_layout = QVBoxLayout(self.prepare_map_group)

        # Attribute, Color Ramp, and Map Navigation toolbar
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("<b>Display Attribute:</b>"))
        self.prepare_attribute_combo = QComboBox()
        self.prepare_attribute_combo.addItem("Dry Yield (Default)", "yield_dry_mass_area")
        self.prepare_attribute_combo.addItem("Wet Yield", "yield_wet_mass_area")
        self.prepare_attribute_combo.addItem("Moisture (%)", "moisture_pct")
        self.prepare_attribute_combo.addItem("Speed / Velocity", "speed_m_s")
        self.prepare_attribute_combo.addItem("Swath Width", "swath_width_m")
        self.prepare_attribute_combo.addItem("Elevation", "elevation_m")
        self.prepare_attribute_combo.addItem("Pass ID", "pass_id")
        ctrl_row.addWidget(self.prepare_attribute_combo)

        ctrl_row.addWidget(QLabel("<b>Color Ramp:</b>"))
        self.prepare_ramp_combo = QComboBox()
        self.prepare_ramp_combo.addItem("Red-Yellow-Green (Standard)", "RdYlGn")
        self.prepare_ramp_combo.addItem("Viridis (Perceptually Uniform)", "Viridis")
        self.prepare_ramp_combo.addItem("Blues (Moisture)", "Blues")
        self.prepare_ramp_combo.addItem("Plasma", "Plasma")
        self.prepare_ramp_combo.addItem("Spectral", "Spectral")
        self.prepare_ramp_combo.addItem("Magma", "Magma")
        ctrl_row.addWidget(self.prepare_ramp_combo)

        self.prepare_pan_btn = QPushButton("✋ Pan")
        self.prepare_pan_btn.setToolTip("Pan map canvas")
        self.prepare_pan_btn.clicked.connect(self._activate_prepare_pan)
        ctrl_row.addWidget(self.prepare_pan_btn)

        self.prepare_zoom_in_btn = QPushButton("🔍+")
        self.prepare_zoom_in_btn.setToolTip("Zoom in on map canvas")
        self.prepare_zoom_in_btn.clicked.connect(lambda: self.prepare_map_canvas.zoomIn() if self.prepare_map_canvas else None)
        ctrl_row.addWidget(self.prepare_zoom_in_btn)

        self.prepare_zoom_out_btn = QPushButton("🔍-")
        self.prepare_zoom_out_btn.setToolTip("Zoom out on map canvas")
        self.prepare_zoom_out_btn.clicked.connect(lambda: self.prepare_map_canvas.zoomOut() if self.prepare_map_canvas else None)
        ctrl_row.addWidget(self.prepare_zoom_out_btn)

        self.prepare_zoom_full_btn = QPushButton("📐 Zoom Full")
        self.prepare_zoom_full_btn.setToolTip("Zoom to full extent of observations")
        self.prepare_zoom_full_btn.clicked.connect(self._zoom_prepare_full)
        ctrl_row.addWidget(self.prepare_zoom_full_btn)

        ctrl_row.addStretch(1)
        map_group_layout.addLayout(ctrl_row)

        if QgsMapCanvas is not None:
            self.prepare_map_canvas = QgsMapCanvas(self)
            self.prepare_map_canvas.setCanvasColor(QColor("#f8fafc"))
            self.prepare_map_canvas.setMinimumHeight(240)
            if QgsMapToolPan is not None:
                self.prepare_pan_tool = QgsMapToolPan(self.prepare_map_canvas)
                self.prepare_map_canvas.setMapTool(self.prepare_pan_tool)
            map_group_layout.addWidget(self.prepare_map_canvas)
        else:
            self.prepare_map_canvas = None

        # Live Classification Legend Bar
        self.prepare_legend_widget = QWidget()
        self.prepare_legend_layout = QHBoxLayout(self.prepare_legend_widget)
        self.prepare_legend_layout.setContentsMargins(4, 2, 4, 2)
        self.prepare_legend_layout.setSpacing(6)
        map_group_layout.addWidget(self.prepare_legend_widget)

        self.prepare_scale_label = QLabel("📏 <b>Scale:</b> 1:— &bull; <b>Display Units:</b> — &bull; <b>CRS:</b> —")
        self.prepare_scale_label.setStyleSheet("color: #475569; font-size: 11px; padding: 4px 8px; background: #f1f5f9; border-radius: 4px; border: 1px solid #e2e8f0;")
        map_group_layout.addWidget(self.prepare_scale_label)

        if self.prepare_map_canvas is not None:
            self.prepare_map_canvas.scaleChanged.connect(self._update_prepare_scale)
            self.prepare_map_canvas.extentsChanged.connect(self._update_prepare_scale)

        self.prepare_attribute_combo.currentIndexChanged.connect(self._apply_prepare_preview_styling)
        self.prepare_ramp_combo.currentIndexChanged.connect(self._apply_prepare_preview_styling)

        self.prepare_map_group.setVisible(True)
        layout.addWidget(self.prepare_map_group, 1)

        for signal in (
            self.field_name.textChanged,
            self.output_parent_folder.textChanged,
            self.crop_combo.currentIndexChanged,
        ):
            signal.connect(self._update_run_preview)
        self._update_run_preview()
        return tab

    def _activate_prepare_pan(self):
        if self.prepare_map_canvas is not None and QgsMapToolPan is not None:
            self.prepare_pan_tool = QgsMapToolPan(self.prepare_map_canvas)
            self.prepare_map_canvas.setMapTool(self.prepare_pan_tool)

    def _zoom_prepare_full(self):
        if self.prepare_map_canvas is not None and hasattr(self, "current_prepared_layer") and self.current_prepared_layer:
            self.prepare_map_canvas.setExtent(self.current_prepared_layer.extent())
            self.prepare_map_canvas.refresh()
            self._update_prepare_scale()

    def _update_prepare_scale(self):
        if self.prepare_map_canvas is None or not hasattr(self, "prepare_scale_label"):
            return
        scale = self.prepare_map_canvas.scale()
        crs_auth = "Unresolved"
        if hasattr(self, "current_prepared_layer") and self.current_prepared_layer and self.current_prepared_layer.isValid():
            crs_auth = self.current_prepared_layer.crs().authid()
        is_metric = str(self.units_combo.currentData() or "imperial") == "metric"
        unit_str = "Metric (Meters, kg/ha)" if is_metric else "Imperial (Feet, bu/ac)"
        self.prepare_scale_label.setText(
            f"📏 <b>Scale:</b> 1:{int(scale):,} &bull; <b>Display Units:</b> {unit_str} &bull; <b>CRS:</b> {crs_auth}"
        )

    def _update_prepare_legend(self):
        if not hasattr(self, "prepare_legend_layout") or not self.current_prepared_layer or not self.current_prepared_layer.isValid():
            return
        while self.prepare_legend_layout.count():
            item = self.prepare_legend_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        items = get_layer_graduated_legend_items(self.current_prepared_layer)
        if not items:
            return

        is_metric = str(self.units_combo.currentData() or "imperial") == "metric"
        attr = str(self.prepare_attribute_combo.currentData() or "yield_dry_mass_area")
        unit_label = ""
        if "yield" in attr:
            unit_label = "kg/ha" if is_metric else "bu/ac"
        elif "speed" in attr:
            unit_label = "m/s" if is_metric else "mph"
        elif "swath" in attr or "elevation" in attr:
            unit_label = "m" if is_metric else "ft"
        elif "moisture" in attr:
            unit_label = "%"

        hdr_lbl = QLabel(f"<b>Legend ({attr.replace('_', ' ').title()}):</b>")
        hdr_lbl.setStyleSheet("font-size: 11px; color: #1e293b; font-weight: bold;")
        self.prepare_legend_layout.addWidget(hdr_lbl)

        for item in items:
            color = item.get("color", "#3388ff")
            label_text = item.get("label", "")
            if "lower" in item and "upper" in item:
                low = item["lower"]
                up = item["upper"]
                if "yield" in attr and not is_metric:
                    tw = float(self.test_weight_spin.value() if hasattr(self, "test_weight_spin") else 56.0)
                    if low > 300 or up > 300:
                        low = kg_per_hectare_to_bushels_per_acre(low, tw)
                        up = kg_per_hectare_to_bushels_per_acre(up, tw)
                label_text = f"{low:.1f} – {up:.1f} {unit_label}".strip()

            chip = QLabel(f"<span style='color: {color}; font-size: 14px;'>■</span> {label_text}")
            chip.setStyleSheet("font-size: 11px; color: #334155; padding: 2px 6px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;")
            self.prepare_legend_layout.addWidget(chip)

        self.prepare_legend_layout.addStretch(1)

    def _apply_prepare_preview_styling(self):
        if not self.current_prepared_layer or not self.current_prepared_layer.isValid():
            return
        attr = str(self.prepare_attribute_combo.currentData() or "yield_dry_mass_area")
        ramp = str(self.prepare_ramp_combo.currentData() or "RdYlGn")
        style_layer_with_attribute_and_ramp(self.current_prepared_layer, attr, ramp)
        self._update_prepare_legend()
        if self.prepare_map_canvas is not None:
            self.prepare_map_canvas.setLayers([self.current_prepared_layer])
            self.prepare_map_canvas.refresh()
        if self.iface and self.iface.mapCanvas():
            self.iface.mapCanvas().refresh()

    def _continue_to_clean(self):
        self._style_button_completed(self.prepare_continue_button, "✓ Clean & Review")
        self.tabs.setCurrentIndex(3)

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

        self.import_create_boundary_button = QPushButton("Import / Create Boundary")
        self.import_create_boundary_button.setObjectName("importCreateBoundaryButton")
        self.import_create_boundary_button.clicked.connect(self._run_import_create_boundary)
        self._style_button_action_needed(self.import_create_boundary_button)
        layout.addWidget(self.import_create_boundary_button)

        self.boundary_map_group = QGroupBox("Field Boundary Preview & Cleanup Tools")
        bnd_map_layout = QVBoxLayout(self.boundary_map_group)

        # Cleanup & vertex modification toolbar
        tools_row = QHBoxLayout()
        self.fill_holes_btn = QPushButton("🧹 Remove Interior Holes")
        self.fill_holes_btn.setToolTip("Remove all interior holes/slivers from the boundary polygon")
        self.fill_holes_btn.clicked.connect(self._fill_boundary_holes)

        self.simplify_bnd_btn = QPushButton("✨ Smooth / Simplify (-15%)")
        self.simplify_bnd_btn.setToolTip("Smooth boundary geometry by removing ~15% of vertices per click")
        self.simplify_bnd_btn.clicked.connect(self._simplify_boundary)

        self.densify_bnd_btn = QPushButton("➕ Densify / Add Vertices (+15%)")
        self.densify_bnd_btn.setToolTip("Add ~15% intermediate vertices along boundary segments to increase detail")
        self.densify_bnd_btn.clicked.connect(self._densify_boundary)

        self.edit_vertices_btn = QPushButton("✏️ Edit Vertices (In-Modal)")
        self.edit_vertices_btn.setCheckable(True)
        self.edit_vertices_btn.setToolTip("Toggle interactive in-modal vertex editing mode")
        self.edit_vertices_btn.toggled.connect(self._toggle_inmodal_vertex_editor)

        self.pan_bnd_btn = QPushButton("✋ Pan")
        self.pan_bnd_btn.setToolTip("Pan boundary canvas")
        self.pan_bnd_btn.clicked.connect(self._activate_boundary_pan)

        self.zoom_in_bnd_btn = QPushButton("🔍+")
        self.zoom_in_bnd_btn.setToolTip("Zoom in on boundary canvas")
        self.zoom_in_bnd_btn.clicked.connect(lambda: self.boundary_map_canvas.zoomIn() if self.boundary_map_canvas else None)

        self.zoom_out_bnd_btn = QPushButton("🔍-")
        self.zoom_out_bnd_btn.setToolTip("Zoom out on boundary canvas")
        self.zoom_out_bnd_btn.clicked.connect(lambda: self.boundary_map_canvas.zoomOut() if self.boundary_map_canvas else None)

        self.zoom_full_bnd_btn = QPushButton("📐 Zoom Full")
        self.zoom_full_bnd_btn.setToolTip("Zoom to full extent of boundary")
        self.zoom_full_bnd_btn.clicked.connect(self._zoom_boundary_full)

        self.reset_bnd_btn = QPushButton("↶ Reset Original")
        self.reset_bnd_btn.setToolTip("Revert any hole removals or edits back to the original boundary")
        self.reset_bnd_btn.clicked.connect(self._reset_boundary_preview)

        tools_row.addWidget(self.fill_holes_btn)
        tools_row.addWidget(self.simplify_bnd_btn)
        tools_row.addWidget(self.densify_bnd_btn)
        tools_row.addWidget(self.edit_vertices_btn)
        tools_row.addWidget(self.pan_bnd_btn)
        tools_row.addWidget(self.zoom_in_bnd_btn)
        tools_row.addWidget(self.zoom_out_bnd_btn)
        tools_row.addWidget(self.zoom_full_bnd_btn)
        tools_row.addWidget(self.reset_bnd_btn)

        self.bnd_vertex_count_label = QLabel("")
        self.bnd_vertex_count_label.setStyleSheet("color: #0369a1; font-weight: bold; padding: 2px 6px;")
        tools_row.addWidget(self.bnd_vertex_count_label)

        tools_row.addStretch(1)
        bnd_map_layout.addLayout(tools_row)

        self.vertex_guide_label = QLabel(
            "💡 <b>In-Modal Vertex Editor Active:</b> Drag vertices to reposition • Click on boundary edge to add a vertex • Right-click on a vertex to delete it."
        )
        self.vertex_guide_label.setStyleSheet(
            "background: #eff6ff; color: #1e40af; padding: 6px 10px; border-radius: 4px; border: 1px solid #bfdbfe; font-size: 11px;"
        )
        self.vertex_guide_label.setVisible(False)
        bnd_map_layout.addWidget(self.vertex_guide_label)

        if QgsMapCanvas is not None:
            self.boundary_map_canvas = QgsMapCanvas(self)
            self.boundary_map_canvas.setCanvasColor(QColor("#f8fafc"))
            self.boundary_map_canvas.setMinimumHeight(240)
            if QgsMapToolPan is not None:
                self.boundary_pan_tool = QgsMapToolPan(self.boundary_map_canvas)
                self.boundary_map_canvas.setMapTool(self.boundary_pan_tool)
            bnd_map_layout.addWidget(self.boundary_map_canvas)
        else:
            self.boundary_map_canvas = None
        self.boundary_map_group.setVisible(True)
        layout.addWidget(self.boundary_map_group, 1)

        self.boundary_continue_button = QPushButton("Continue to Prepare Dataset")
        self.boundary_continue_button.setObjectName("continueToPrepareButton")
        self.boundary_continue_button.setEnabled(False)
        self.boundary_continue_button.clicked.connect(self._continue_to_prepare_dataset)
        self._style_button_action_needed(self.boundary_continue_button)
        layout.addWidget(self.boundary_continue_button)

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
            """
            <h2>Clean &amp; Review</h2>
            <ol>
              <li>Configure sensor delays, motion limits, swath trimming, overlap, and spatial outlier parameters.</li>
              <li>Click <b>Execute Cleaning Pipeline</b>.</li>
              <li>Inspect KPI summary statistics and filter reason counts.</li>
              <li>Click <b>Open HTML Review Report</b> to view the interactive before/after map and charts in your browser.</li>
              <li>Optionally export the cleaned operation to <b>ADAPT Standard</b>.</li>
            </ol>
            <p><b>Auditable &amp; Non-destructive:</b> All source points are preserved. Excluded points receive standard reason codes.</p>
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

    def _detect_crop_code(self, source_text: str, rows: list = None) -> str | None:
        return detect_crop_code(source_text, rows)

    def _auto_detect_and_set_crop(self, source_text: str, rows: list = None):
        detected = detect_crop_code(source_text, rows)
        if detected and hasattr(self, "crop_combo"):
            idx = self.crop_combo.findData(detected)
            if idx >= 0 and idx != self.crop_combo.currentIndex():
                self.crop_combo.setCurrentIndex(idx)

    def _on_layer_selection_changed(self, *_args):
        self._refresh_suggested_field_name()
        if hasattr(self, "layer_combo") and self.layer_combo.count() > 0:
            layer_name = self.layer_combo.currentText().strip()
            self._auto_detect_and_set_crop(layer_name)

    def _on_file_path_changed(self, *_args):
        self._refresh_suggested_field_name()
        path_str = self.file_path.text().strip()
        if path_str:
            self._auto_detect_and_set_crop(path_str)

    def _on_crop_changed(self, *_args):
        crop = str(self.crop_combo.currentData() or "corn")
        try:
            prof = crop_profile(crop)
            if hasattr(self, "test_weight_spin"):
                self.test_weight_spin.setValue(prof.test_weight_lb_per_bushel)
            if hasattr(self, "standard_moisture_spin"):
                self.standard_moisture_spin.setValue(prof.standard_moisture_pct)
        except Exception:
            pass
        self._refresh_suggested_field_name()
        self._update_run_preview()
        if hasattr(self, "flow_delay_spin"):
            self._reset_recipe_defaults()

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
        stem = build_run_stem(field_name, str(self.crop_combo.currentData()), include_time=True)
        parent_text = self.output_parent_folder.text().strip()
        if not parent_text:
            self.output_parent_folder.setStyleSheet(
                "border: 2px solid #dc2626; border-radius: 4px; padding: 5px; background: #fef2f2;"
            )
            candidate = Path(stem)
        else:
            self.output_parent_folder.setStyleSheet(
                "border: 1px solid #16a34a; border-radius: 4px; padding: 5px; background: #f0fdf4;"
            )
            candidate = next_available_run_folder(Path(parent_text), stem)
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

    def _run_import_create_boundary(self):
        try:
            existing_boundary, yield_points = self._boundary_parameters()
            self._refresh_suggested_field_name()
            field_name = self.field_name.text().strip() or self._suggested_field_name()
            self.field_name.setText(field_name)

            boundary_layer = None
            if self.boundary_mode.currentIndex() == 0:
                # Existing polygon boundary
                if isinstance(existing_boundary, str):
                    boundary_layer = QgsVectorLayer(existing_boundary, "Field Boundary", "ogr")
                else:
                    boundary_layer = existing_boundary
                if boundary_layer is None or not boundary_layer.isValid():
                    raise ValueError("The selected boundary layer could not be opened")

                feat_count = boundary_layer.featureCount()
                detail = f"Existing boundary loaded successfully ({feat_count:,} polygon feature{'s' if feat_count != 1 else ''})."
            else:
                # Derive operational boundary from yield points
                import processing

                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                QApplication.processEvents()
                try:
                    result = processing.run(
                        "yield_data_cleaner:prepare_field_boundary",
                        {
                            "MODE": 1,
                            "EXISTING_BOUNDARY": None,
                            "YIELD_POINTS": yield_points,
                            "WIDTH_FIELD": self.width_field.currentText().strip() or None,
                            "DEFAULT_WIDTH": self.default_width.value() * 0.3048,
                            "GAP_CLOSING": self.gap_closing.value() * 0.3048,
                            "CONCAVITY": self.concavity.value(),
                            "PROVENANCE": "TEMPORARY_OUTPUT",
                            "OUTPUT": "TEMPORARY_OUTPUT",
                        },
                    )
                    out_uri = result.get("OUTPUT")
                    if isinstance(out_uri, QgsVectorLayer):
                        boundary_layer = out_uri
                    elif out_uri:
                        boundary_layer = QgsVectorLayer(str(out_uri), "Derived Boundary", "ogr")
                    if boundary_layer is None or not boundary_layer.isValid():
                        raise ValueError("Failed to derive operational field boundary from points")
                    detail = "Operational field boundary derived from yield points."
                finally:
                    QApplication.restoreOverrideCursor()

            # Render in boundary_map_canvas
            if self.boundary_map_canvas is not None and boundary_layer is not None:
                self.boundary_map_canvas.setLayers([boundary_layer])
                self.boundary_map_canvas.setExtent(boundary_layer.extent())
                self.boundary_map_canvas.refresh()
                self.boundary_map_group.setVisible(True)

            self.current_preview_boundary_layer = boundary_layer
            self.original_boundary_geometries = {
                feat.id(): QgsGeometry(feat.geometry())
                for feat in boundary_layer.getFeatures()
                if feat.geometry() and not feat.geometry().isEmpty()
            }

            # Apply initial default simplification: default to 50% vertices for cleaner boundary
            raw_v = sum(self._count_geom_vertices(g) for g in self.original_boundary_geometries.values())
            if raw_v > 8:
                boundary_layer.startEditing()
                for feat in boundary_layer.getFeatures():
                    orig_g = feat.geometry()
                    simp_g = self._simplify_geom_by_ratio(orig_g, ratio=0.50)
                    if simp_g and not simp_g.isEmpty() and simp_g.isGeosValid():
                        boundary_layer.changeGeometry(feat.id(), simp_g)
                boundary_layer.commitChanges()

            curr_v = sum(self._count_geom_vertices(f.geometry()) for f in boundary_layer.getFeatures())
            if hasattr(self, "bnd_vertex_count_label"):
                self.bnd_vertex_count_label.setText(f"Vertices: {curr_v} (50% default)")

            # Render in boundary_map_canvas
            if self.boundary_map_canvas is not None and boundary_layer is not None:
                self.boundary_map_canvas.setLayers([boundary_layer])
                self.boundary_map_canvas.setExtent(boundary_layer.extent())
                self.boundary_map_canvas.refresh()
                self.boundary_map_group.setVisible(True)

            self._style_button_completed(self.import_create_boundary_button, "✓ Boundary Ready")
            self.boundary_continue_button.setEnabled(True)
            self._style_button_action_needed(self.boundary_continue_button, "Continue to Prepare Dataset")

        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))

    def _count_geom_vertices(self, geom):
        if not geom or geom.isEmpty():
            return 0
        try:
            if geom.isMultipart():
                return sum(len(ring) for poly in geom.asMultiPolygon() for ring in poly)
            return sum(len(ring) for ring in geom.asPolygon())
        except Exception:
            return 0

    def _simplify_geom_by_ratio(self, geom, ratio: float = 0.85):
        """Simplify geometry to achieve target vertex count (~15% reduction)."""
        if not geom or geom.isEmpty():
            return geom
        v_orig = self._count_geom_vertices(geom)
        if v_orig <= 4:
            return geom
        target_v = max(4, int(round(v_orig * ratio)))

        sample_pt = geom.centroid().asPoint() if geom.centroid() else None
        is_geo = (sample_pt and 10.0 < abs(sample_pt.x()) <= 180.0 and 10.0 < abs(sample_pt.y()) <= 90.0)
        low_tol = 1e-7
        high_tol = 0.005 if is_geo else 20.0
        best_geom = geom
        best_diff = 999999

        for _ in range(14):
            mid_tol = (low_tol + high_tol) / 2.0
            simp = geom.simplify(mid_tol)
            if simp and not simp.isEmpty() and simp.isGeosValid():
                v_mid = self._count_geom_vertices(simp)
                diff = abs(v_mid - target_v)
                if diff < best_diff:
                    best_diff = diff
                    best_geom = simp
                if v_mid > target_v:
                    low_tol = mid_tol
                else:
                    high_tol = mid_tol
            else:
                high_tol = mid_tol
        return best_geom

    def _densify_geom_by_ratio(self, geom, ratio: float = 1.15):
        """Densify geometry to achieve target vertex count (~15% addition)."""
        if not geom or geom.isEmpty():
            return geom
        v_orig = self._count_geom_vertices(geom)
        target_v = max(v_orig + 1, int(round(v_orig * ratio)))
        perimeter = geom.length()
        if perimeter <= 0:
            return geom
        seg_dist = max(1e-6, perimeter / float(target_v))
        dens = geom.densifyByDistance(seg_dist)
        if dens and not dens.isEmpty() and dens.isGeosValid():
            return dens
        return geom

    def _fill_boundary_holes(self):
        if not hasattr(self, "current_preview_boundary_layer") or not self.current_preview_boundary_layer or not self.current_preview_boundary_layer.isValid():
            QMessageBox.information(self, PLUGIN_NAME, "Import or create a boundary first.")
            return
        layer = self.current_preview_boundary_layer
        try:
            layer.startEditing()
            modified = False
            v_before = 0
            v_after = 0
            for feat in layer.getFeatures():
                orig_geom = feat.geometry()
                v_before += self._count_geom_vertices(orig_geom)
                filled_geom = fill_polygon_holes(orig_geom)
                if filled_geom and not filled_geom.isEmpty():
                    layer.changeGeometry(feat.id(), filled_geom)
                    v_after += self._count_geom_vertices(filled_geom)
                    modified = True
                else:
                    v_after += self._count_geom_vertices(orig_geom)
            layer.commitChanges()
            if hasattr(self, "vertex_tool") and self.edit_vertices_btn.isChecked():
                self.vertex_tool.refresh_markers()
            if self.boundary_map_canvas is not None:
                self.boundary_map_canvas.setLayers([layer])
                self.boundary_map_canvas.refresh()
            if self.iface and self.iface.mapCanvas():
                self.iface.mapCanvas().refresh()
            if hasattr(self, "bnd_vertex_count_label"):
                self.bnd_vertex_count_label.setText(f"Holes removed • Vertices: {v_after}")
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, f"Could not remove holes: {exc}")

    def _simplify_boundary(self):
        if not hasattr(self, "current_preview_boundary_layer") or not self.current_preview_boundary_layer or not self.current_preview_boundary_layer.isValid():
            QMessageBox.information(self, PLUGIN_NAME, "Import or create a boundary first.")
            return
        layer = self.current_preview_boundary_layer
        try:
            layer.startEditing()
            v_before = 0
            v_after = 0
            for feat in layer.getFeatures():
                orig_geom = feat.geometry()
                v_b = self._count_geom_vertices(orig_geom)
                v_before += v_b
                simp_geom = self._simplify_geom_by_ratio(orig_geom, ratio=0.85)
                if simp_geom and not simp_geom.isEmpty() and simp_geom.isGeosValid():
                    layer.changeGeometry(feat.id(), simp_geom)
                    v_after += self._count_geom_vertices(simp_geom)
                else:
                    v_after += v_b
            layer.commitChanges()
            if hasattr(self, "vertex_tool") and self.edit_vertices_btn.isChecked():
                self.vertex_tool.refresh_markers()
            if self.boundary_map_canvas is not None:
                self.boundary_map_canvas.setLayers([layer])
                self.boundary_map_canvas.refresh()
            if self.iface and self.iface.mapCanvas():
                self.iface.mapCanvas().refresh()
            if hasattr(self, "bnd_vertex_count_label"):
                diff = v_after - v_before
                pct = (diff / v_before * 100.0) if v_before else 0.0
                self.bnd_vertex_count_label.setText(f"Vertices: {v_after} ({diff:+d}, {pct:+.0f}%)")
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, f"Could not simplify boundary: {exc}")

    def _densify_boundary(self):
        if not hasattr(self, "current_preview_boundary_layer") or not self.current_preview_boundary_layer or not self.current_preview_boundary_layer.isValid():
            QMessageBox.information(self, PLUGIN_NAME, "Import or create a boundary first.")
            return
        layer = self.current_preview_boundary_layer
        try:
            layer.startEditing()
            v_before = 0
            v_after = 0
            for feat in layer.getFeatures():
                orig_geom = feat.geometry()
                v_b = self._count_geom_vertices(orig_geom)
                v_before += v_b
                dens_geom = self._densify_geom_by_ratio(orig_geom, ratio=1.15)
                if dens_geom and not dens_geom.isEmpty() and dens_geom.isGeosValid():
                    layer.changeGeometry(feat.id(), dens_geom)
                    v_after += self._count_geom_vertices(dens_geom)
                else:
                    v_after += v_b
            layer.commitChanges()
            if hasattr(self, "vertex_tool") and self.edit_vertices_btn.isChecked():
                self.vertex_tool.refresh_markers()
            if self.boundary_map_canvas is not None:
                self.boundary_map_canvas.setLayers([layer])
                self.boundary_map_canvas.refresh()
            if self.iface and self.iface.mapCanvas():
                self.iface.mapCanvas().refresh()
            if hasattr(self, "bnd_vertex_count_label"):
                diff = v_after - v_before
                pct = (diff / v_before * 100.0) if v_before else 0.0
                self.bnd_vertex_count_label.setText(f"Vertices: {v_after} ({diff:+d}, {pct:+.0f}%)")
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, f"Could not densify boundary: {exc}")

    def _toggle_inmodal_vertex_editor(self, active: bool):
        if not hasattr(self, "current_preview_boundary_layer") or not self.current_preview_boundary_layer or not self.current_preview_boundary_layer.isValid():
            self.edit_vertices_btn.blockSignals(True)
            self.edit_vertices_btn.setChecked(False)
            self.edit_vertices_btn.blockSignals(False)
            QMessageBox.information(self, PLUGIN_NAME, "Import or create a boundary first.")
            return

        if active:
            if self.boundary_map_canvas is not None:
                self.vertex_tool = ModalBoundaryVertexTool(
                    self.boundary_map_canvas,
                    lambda: self.current_preview_boundary_layer,
                    self._on_vertex_edited,
                )
                self.vertex_tool.refresh_markers()
                self.boundary_map_canvas.setMapTool(self.vertex_tool)
            self.vertex_guide_label.setVisible(True)
            self.edit_vertices_btn.setText("✓ Done Editing Vertices")
            self.edit_vertices_btn.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold;")
        else:
            if hasattr(self, "vertex_tool") and self.vertex_tool:
                self.vertex_tool.clear()
            if self.boundary_map_canvas is not None and QgsMapToolPan is not None:
                self.boundary_pan_tool = QgsMapToolPan(self.boundary_map_canvas)
                self.boundary_map_canvas.setMapTool(self.boundary_pan_tool)
            self.vertex_guide_label.setVisible(False)
            self.edit_vertices_btn.setText("✏️ Edit Vertices (In-Modal)")
            self.edit_vertices_btn.setStyleSheet("")

    def _activate_boundary_pan(self):
        if self.boundary_map_canvas is None:
            return
        if QgsMapToolPan is not None:
            self.boundary_pan_tool = QgsMapToolPan(self.boundary_map_canvas)
            self.boundary_map_canvas.setMapTool(self.boundary_pan_tool)

    def _zoom_boundary_full(self):
        if self.boundary_map_canvas is not None and hasattr(self, "current_preview_boundary_layer") and self.current_preview_boundary_layer:
            self.boundary_map_canvas.setExtent(self.current_preview_boundary_layer.extent())
            self.boundary_map_canvas.refresh()

    def _on_vertex_edited(self, message: str):
        if self.iface and self.iface.mapCanvas():
            self.iface.mapCanvas().refresh()

    def _reset_boundary_preview(self):
        if not hasattr(self, "original_boundary_geometries") or not self.original_boundary_geometries:
            QMessageBox.information(self, PLUGIN_NAME, "No original boundary backup available.")
            return
        layer = self.current_preview_boundary_layer
        try:
            layer.startEditing()
            for fid, orig_geom in self.original_boundary_geometries.items():
                layer.changeGeometry(fid, QgsGeometry(orig_geom))
            layer.commitChanges()
            if hasattr(self, "vertex_tool") and self.edit_vertices_btn.isChecked():
                self.vertex_tool.refresh_markers()
            if self.boundary_map_canvas is not None:
                self.boundary_map_canvas.setLayers([layer])
                self.boundary_map_canvas.refresh()
            if self.iface and self.iface.mapCanvas():
                self.iface.mapCanvas().refresh()
            if hasattr(self, "bnd_vertex_count_label"):
                total_v = sum(self._count_geom_vertices(g) for g in self.original_boundary_geometries.values())
                self.bnd_vertex_count_label.setText(f"Reset • Vertices: {total_v}")
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, f"Could not reset boundary: {exc}")

    def _continue_to_prepare_dataset(self):
        self._style_button_completed(self.boundary_continue_button, "✓ Field Boundary Confirmed")
        self.tabs.setCurrentIndex(2)

    def _continue_to_boundary(self):
        try:
            if not self.current_columns:
                raise ValueError("Inspect the input before continuing")
            profile = MappingProfile(
                mapping=self._reviewed_mapping(),
                crop_code=str(self.crop_combo.currentData()),
                unit_profile=str(self.units_combo.currentData()),
                source_crs=self.crs_text.text().strip() or None,
                source_units=self._reviewed_source_units(),
                profile_name="guided_workflow_review",
            )
            errors = profile.validate(self.current_columns)
            if errors:
                raise ValueError("Review the column mapping: " + "; ".join(errors))
            self._style_button_completed(self.input_continue_button, "✓ Field Boundary Setup")
            self.tabs.setCurrentIndex(1)
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, str(exc))

    def _run_prepare_dataset(self):
        folder = None
        if hasattr(self, "create_dataset_button"):
            self.create_dataset_button.setEnabled(False)
            self.create_dataset_button.setText("Creating prepared dataset... Please wait...")
        if hasattr(self, "prepare_progress"):
            self.prepare_progress.setVisible(True)
        if hasattr(self, "prepare_status"):
            self.prepare_status.setHtml(
                "<h3>Preparing dataset in progress...</h3>"
                "<p>Ingesting raw observations, validating CRS, creating canonical layer, and preparing boundary. Please wait...</p>"
            )
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            if not self.current_columns:
                raise ValueError("Complete Input & Mapping before preparing the dataset")
            existing_boundary, yield_points = self._boundary_parameters()
            parent_text = self.output_parent_folder.text().strip()
            if not parent_text:
                raise ValueError("Choose a destination output folder")
            parent = Path(parent_text)
            parent.mkdir(parents=True, exist_ok=True)
            field_name = self.field_name.text().strip() or self._suggested_field_name()
            stem = build_run_stem(field_name, str(self.crop_combo.currentData()), include_time=True)
            profile = MappingProfile(
                mapping=self._reviewed_mapping(),
                crop_code=str(self.crop_combo.currentData()),
                unit_profile=str(self.units_combo.currentData()),
                source_crs=self.crs_text.text().strip() or None,
                source_units=self._reviewed_source_units(),
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

            prepared_uri = str(prepared_result.get("OUTPUT") or paths["geopackage"])
            prepared_layer = QgsVectorLayer(prepared_uri, "Prepared yield observations", "ogr")
            if not prepared_layer.isValid():
                prepared_layer = QgsVectorLayer(
                    f"{paths['geopackage']}|layername=prepared_observations",
                    "Prepared yield observations",
                    "ogr",
                )

            if hasattr(self, "current_preview_boundary_layer") and self.current_preview_boundary_layer and self.current_preview_boundary_layer.isValid() and self.current_preview_boundary_layer.featureCount() > 0:
                from qgis.core import QgsVectorFileWriter
                write_opts = QgsVectorFileWriter.SaveVectorOptions()
                write_opts.driverName = "GPKG"
                write_opts.layerName = "field_boundary"
                write_opts.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
                QgsVectorFileWriter.writeAsVectorFormatV3(
                    self.current_preview_boundary_layer,
                    str(paths["geopackage"]),
                    QgsProject.instance().transformContext(),
                    write_opts,
                )
                boundary_layer = QgsVectorLayer(
                    f"{paths['geopackage']}|layername=field_boundary",
                    "Prepared field boundary",
                    "ogr",
                )
            else:
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
            self.current_prepared_boundary_layer = boundary_layer
            self.current_run_folder = folder
            self.current_run_paths = paths
            self.current_prepared_layer = prepared_layer
            self.current_crop_code = str(self.crop_combo.currentData())
            self.current_unit_profile = str(self.units_combo.currentData())
            self.prepare_continue_button.setEnabled(True)
            self.execute_button.setEnabled(True)
            self._reset_recipe_defaults()

            # Style the prepared layer on the QGIS map canvas with the Yield graduated color ramp
            style_layer_with_attribute_and_ramp(prepared_layer, "yield_dry_mass_area", "RdYlGn")

            # Render embedded map preview on Tab 3 - showing ONLY prepared yield points (no boundary)
            if self.prepare_map_canvas is not None:
                self.prepare_attribute_combo.blockSignals(True)
                self.prepare_attribute_combo.clear()
                standard_fields = [
                    ("Dry Yield (Default)", "yield_dry_mass_area"),
                    ("Wet Yield", "yield_wet_mass_area"),
                    ("Moisture (%)", "moisture_pct"),
                    ("Speed / Velocity", "speed_m_s"),
                    ("Swath Width", "swath_width_m"),
                    ("Elevation", "elevation_m"),
                    ("Pass ID", "pass_id"),
                ]
                for label, field_name in standard_fields:
                    self.prepare_attribute_combo.addItem(label, field_name)

                # Add all additional original dataset columns
                standard_internal = {item[1] for item in standard_fields} | {"observation_id", "source_index", "geometry"}
                for f in prepared_layer.fields():
                    fn = f.name()
                    if fn not in standard_internal:
                        self.prepare_attribute_combo.addItem(fn, fn)

                self.prepare_ramp_combo.blockSignals(True)
                self.prepare_attribute_combo.setCurrentIndex(0)
                self.prepare_ramp_combo.setCurrentIndex(0)
                self.prepare_attribute_combo.blockSignals(False)
                self.prepare_ramp_combo.blockSignals(False)

                self.prepare_map_canvas.setLayers([prepared_layer])
                self.prepare_map_canvas.setExtent(prepared_layer.extent())
                self.prepare_map_canvas.refresh()
                self.prepare_map_group.setVisible(True)
                self._apply_prepare_preview_styling()

            # Connect selectionChanged signal so selected points on map canvas display in modal table
            try:
                prepared_layer.selectionChanged.connect(self._on_canvas_selection_changed)
            except Exception:
                pass

            self._style_button_completed(self.create_dataset_button, "✓ Prepared Yield Dataset Created")
            self._style_button_action_needed(self.prepare_continue_button, "Continue to Clean & Review")

            review_text = (
                "Review the derived field boundary on the map before using it."
                if self.boundary_mode.currentIndex() == 1
                else "The selected field boundary was validated and included."
            )
            if hasattr(self, "prepare_status"):
                self.prepare_status.setHtml(
                    "<h3><span style='color: #16a34a;'>&#10004; Prepared Yield Dataset Created</span></h3>"
                    f"<p><b>Run folder:</b> {html.escape(str(folder))}</p>"
                    f"<p><b>Yield data:</b> {html.escape(paths['geopackage'].name)} ({prepared_layer.featureCount():,} points)</p>"
                    f"<p>{html.escape(review_text)}</p>"
                    "<div style='margin: 10px 0; padding: 10px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px;'>"
                    "<b>Map Canvas Symbology:</b> Yield variable styled with Graduated Color Ramp (Red &rarr; Yellow &rarr; Green).<br/>"
                    "<div style='height: 12px; margin: 6px 0; border-radius: 4px; background: linear-gradient(to right, #ef4444, #eab308, #22c55e);'></div>"
                    "<span style='font-size: 11px; color: #475569;'>Low Yield (Red) &bull; Average Yield (Yellow) &bull; High Yield (Green)</span>"
                    "</div>"
                    "<p>No source observations were deleted. Click <b>Continue to Clean &amp; Review</b> to proceed.</p>"
                )
            if hasattr(self, "clean_status"):
                self.clean_status.setHtml(
                    "<h3>Dataset ready for cleaning</h3>"
                    f"<p><b>Field:</b> {html.escape(field_name)} | <b>Crop:</b> {html.escape(self.current_crop_code.capitalize())}</p>"
                    f"<p><b>Total Observations:</b> {prepared_layer.featureCount():,}</p>"
                    "<p>Configure recipe parameters above and click <b>Execute Cleaning Pipeline</b>.</p>"
                )
            self._update_run_preview()
        except Exception as exc:
            if hasattr(self, "create_dataset_button"):
                self.create_dataset_button.setEnabled(True)
                self.create_dataset_button.setText("Create prepared yield dataset")
                self._style_button_action_needed(self.create_dataset_button)
            partial = (
                f"\n\nA partial run folder was retained for diagnostics:\n{folder}"
                if folder is not None and folder.exists()
                else ""
            )
            QMessageBox.warning(self, PLUGIN_NAME, f"{exc}{partial}")
        finally:
            if hasattr(self, "prepare_progress"):
                self.prepare_progress.setVisible(False)
            QApplication.restoreOverrideCursor()
            QApplication.restoreOverrideCursor()

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
        feat_count = layer.featureCount()
        step = max(1, feat_count // 150) if feat_count > 0 else 1
        rows = []
        for index, feature in enumerate(layer.getFeatures()):
            if index % step == 0:
                rows.append({name: feature[name] for name in columns})
            if len(rows) >= 200:
                break
        if not rows and feat_count > 0:
            for index, feature in enumerate(layer.getFeatures()):
                rows.append({name: feature[name] for name in columns})
                if len(rows) >= 50:
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
        if hasattr(self, "inspect_button"):
            self.inspect_button.setEnabled(False)
            self.inspect_button.setText("Inspecting input... Please wait...")
        if hasattr(self, "inspect_progress"):
            self.inspect_progress.setVisible(True)
        self.results.setHtml("<h3>Inspecting input...</h3><p>Analyzing fields, coordinates, and column suggestions. Please wait...</p>")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
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
                    inspection = inspect_delimited_file(path, sample_rows=250)
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
        finally:
            if hasattr(self, "inspect_button"):
                self.inspect_button.setEnabled(True)
                self.inspect_button.setText("Inspect input")
            if hasattr(self, "inspect_progress"):
                self.inspect_progress.setVisible(False)
            QApplication.restoreOverrideCursor()

        # Build representative sample values map for every column
        self.current_sample_values = {}
        for col in columns:
            col_vals = [r.get(col) for r in rows]
            self.current_sample_values[col] = _extract_representative_samples(col_vals)

        # Auto-detect and set crop if identified from file name or attributes
        self._auto_detect_and_set_crop(source_label, rows)

        mapping_rows = (
            "".join(
                "<tr><td><code>{}</code></td><td><b>{}</b></td><td><span style='color: #1e40af; font-family: monospace;'>{}</span></td><td>{:.0%}</td><td>{}</td></tr>".format(
                    html.escape(item.canonical_field),
                    html.escape(item.source_column),
                    html.escape(self.current_sample_values.get(item.source_column, "—")),
                    item.confidence,
                    html.escape(item.reason),
                )
                for item in suggestions
            )
            or '<tr><td colspan="5">No confident column suggestions</td></tr>'
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
        # Yield Calculation & Advisory audit with Calculation Precedence
        suggested_map = {item.canonical_field: item.source_column for item in suggestions}
        dry_col = suggested_map.get("yield_dry_mass_area")
        wet_col = suggested_map.get("yield_wet_mass_area")
        flow_col = suggested_map.get("mass_flow_wet")
        speed_col = suggested_map.get("speed_m_s")
        swath_col = suggested_map.get("swath_width_m")
        moist_col = suggested_map.get("moisture_pct")

        has_calc_vars = bool(flow_col and speed_col and swath_col)

        advisory_items = []
        if has_calc_vars:
            advisory_items.append(
                f"<li><b style='color: #15803d;'>✓ Primary Calculation Mode:</b> Yield is dynamically calculated from physical sensor observations: "
                f"Mass Flow (<code>{html.escape(flow_col)}</code>), Speed (<code>{html.escape(speed_col)}</code>), and Swath Width (<code>{html.escape(swath_col)}</code>), "
                "adjusted to standard market moisture. Sensor calculation takes precedence over direct yield columns.</li>"
            )
            if dry_col:
                sample_dry = self.current_sample_values.get(dry_col, "")
                advisory_items.append(
                    f"<li><b>Direct Dry Yield Attribute (<code>{html.escape(dry_col)}</code>):</b> "
                    f"Detected ({html.escape(sample_dry)}) and available as an automated fallback if flow rate is zero or missing.</li>"
                )
        elif dry_col:
            sample_dry = self.current_sample_values.get(dry_col, "")
            advisory_items.append(
                f"<li><b>Direct Dry Yield Mode:</b> Calculation attributes are incomplete; direct dry yield column (<code>{html.escape(dry_col)}</code>) "
                f"({html.escape(sample_dry)}) will be used directly for all filtering, calculations, and statistics.</li>"
            )
        elif wet_col:
            advisory_items.append(
                f"<li><b>Direct Wet Yield Mode:</b> Wet yield column (<code>{html.escape(wet_col)}</code>) detected and will be adjusted to dry yield using moisture.</li>"
            )
        else:
            missing_req = []
            if not flow_col: missing_req.append("Mass Flow")
            if not speed_col: missing_req.append("Speed / Velocity")
            if not swath_col: missing_req.append("Swath Width")
            advisory_items.append(
                f"<li style='color: #b91c1c;'><b>⚠️ Yield Data Incomplete:</b> No direct dry yield column mapped and calculation fields ({', '.join(missing_req)}) are missing. "
                "Please review column mappings in the table below.</li>"
            )

        if not moist_col:
            advisory_items.append(
                "<li><b>Moisture Column:</b> Not detected; standard crop default moisture will be applied.</li>"
            )
        if not swath_col:
            advisory_items.append(
                "<li><b>Swath Width Column:</b> Not detected; default header width (30 ft / 9.14 m) will be applied.</li>"
            )

        # Build live step-by-step sample calculation worked out from actual data row
        sample_calc_html = ""
        calc_row = None
        for r in rows:
            f_val = r.get(flow_col) if flow_col else None
            s_val = r.get(speed_col) if speed_col else None
            if f_val is not None and s_val is not None:
                try:
                    f_num = float(str(f_val).replace(",", ""))
                    s_num = float(str(s_val).replace(",", ""))
                    if f_num > 0 and s_num > 0:
                        calc_row = r
                        break
                except (TypeError, ValueError):
                    pass
        if calc_row is None and rows:
            calc_row = rows[0]

        if calc_row:
            f_raw = calc_row.get(flow_col) if flow_col else None
            s_raw = calc_row.get(speed_col) if speed_col else None
            w_raw = calc_row.get(swath_col) if swath_col else None
            m_raw = calc_row.get(moist_col) if moist_col else None
            dry_raw = calc_row.get(dry_col) if dry_col else None

            try:
                f_lb_s = float(str(f_raw).replace(",", "")) if f_raw is not None else 23.77
            except Exception:
                f_lb_s = 23.77
            try:
                s_mph = float(str(s_raw).replace(",", "")) if s_raw is not None else 2.65
            except Exception:
                s_mph = 2.65
            try:
                w_ft = float(str(w_raw).replace(",", "")) if w_raw is not None else 30.0
            except Exception:
                w_ft = 30.0
            try:
                m_val = float(str(m_raw).replace(",", "")) if m_raw is not None else 23.5
            except Exception:
                m_val = 23.5

            f_kg_s = f_lb_s * 0.45359237
            s_m_s = s_mph * (1609.344 / 3600.0)
            w_m = w_ft * 0.3048
            std_m = float(self.standard_moisture_spin.value() if hasattr(self, "standard_moisture_spin") else 15.5)
            tw = float(self.test_weight_spin.value() if hasattr(self, "test_weight_spin") else 56.0)

            area_rate_m2_s = s_m_s * w_m
            wet_kg_ha = (f_kg_s / area_rate_m2_s) * 10000.0 if area_rate_m2_s > 0 else 0.0
            dry_kg_ha = wet_kg_ha * ((100.0 - m_val) / (100.0 - std_m)) if (100.0 - std_m) > 0 else wet_kg_ha
            calc_bu_ac = dry_kg_ha / (tw * 1.12085) if tw > 0 else 0.0

            direct_note = ""
            if dry_raw is not None and dry_col:
                try:
                    dry_num = float(str(dry_raw).replace(",", ""))
                    direct_note = f"<br/>• Compare with direct column (<code>{html.escape(dry_col)}</code>): <b>{dry_num:.2f} bu/ac</b> (diff: {calc_bu_ac - dry_num:+.2f} bu/ac)"
                except Exception:
                    pass

            sample_calc_html = (
                "<div style='margin-top: 10px; padding: 10px 14px; background: #ffffff; border: 1px solid #94a3b8; border-radius: 4px; font-family: monospace; font-size: 11px; color: #1e293b; line-height: 1.6;'>"
                "<b style='color: #0f172a; font-size: 12px;'>🧮 Step-by-Step Sample Yield Calculation (from Representative Row):</b><br/>"
                f"1. <b>Observations:</b> Mass Flow = {f_lb_s:.2f} lb/s ({f_kg_s:.2f} kg/s) &bull; Speed = {s_mph:.2f} mph ({s_m_s:.2f} m/s) &bull; Swath = {w_ft:.1f} ft ({w_m:.2f} m) &bull; Moisture = {m_val:.1f}%<br/>"
                f"2. <b>Area Harvest Rate:</b> {s_m_s:.2f} m/s &times; {w_m:.2f} m = {area_rate_m2_s:.2f} m²/s ({area_rate_m2_s * 3600.0 / 4046.8564224:.2f} ac/hr)<br/>"
                f"3. <b>Wet Yield Rate:</b> ({f_kg_s:.2f} kg/s &divide; {area_rate_m2_s:.2f} m²/s) &times; 10,000 = {wet_kg_ha:.1f} kg/ha<br/>"
                f"4. <b>Market Moisture Adj ({m_val:.1f}% &rarr; {std_m:.1f}%):</b> {wet_kg_ha:.1f} &times; (100 - {m_val:.1f}) / (100 - {std_m:.1f}) = {dry_kg_ha:.1f} kg/ha (&rarr; <b style='color: #15803d; font-size: 12px;'>{calc_bu_ac:.2f} bu/ac</b>){direct_note}"
                "</div>"
            )

        advisory_html = (
            "<div style='background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #0284c7; border-radius: 4px; padding: 10px 14px; margin-top: 10px;'>"
            "<h4 style='margin: 0 0 6px 0; color: #0f172a;'>📊 Yield Calculation & Data Advisory</h4>"
            f"<ul style='margin: 0; padding-left: 20px; font-size: 12px; color: #334155; line-height: 1.5;'>{''.join(advisory_items)}</ul>"
            f"{sample_calc_html}"
            "</div>"
        )

        self.results.setHtml(
            f"<h3>{html.escape(source_label)}</h3>"
            f"<p><b>{len(columns)}</b> columns; <b>{len(rows)}</b> representative sample rows analyzed. "
            "Input was not modified.</p>"
            f"<h4>CRS</h4><p>{crs_html}</p>"
            f"{advisory_html}"
            "<h4>Suggested mappings</h4><table border='1' cellspacing='0' cellpadding='5'>"
            "<tr><th>Canonical field</th><th>Source column</th><th>Representative values from data</th>"
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
        self._style_button_completed(self.inspect_button, "✓ Input Inspected & Columns Mapped")
        self._style_button_action_needed(self.input_continue_button, "Continue to Field Boundary")

    def _populate_mapping_table(self, selected_mapping=None):
        selected_mapping = selected_mapping or {
            item.canonical_field: item.source_column for item in self.current_suggestions
        }
        evidence = {item.canonical_field: item for item in self.current_suggestions}
        for row, canonical in enumerate(FIELD_ALIASES):
            combo = self.mapping_table.cellWidget(row, 1)
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(not mapped)", "")
            for column in self.current_columns:
                combo.addItem(column, column)
            selected = selected_mapping.get(canonical, "")
            selected_index = combo.findData(selected)
            combo.setCurrentIndex(max(0, selected_index))
            combo.blockSignals(False)

            # Update sample values in column 3
            col_name = combo.currentData()
            sample_val = self.current_sample_values.get(col_name, "—") if col_name else "—"
            val_item = self.mapping_table.item(row, 3)
            if val_item is None:
                val_item = QTableWidgetItem(sample_val)
                val_item.setFlags(val_item.flags() & ~enum_member(Qt, "ItemFlag", "ItemIsEditable"))
                self.mapping_table.setItem(row, 3, val_item)
            else:
                val_item.setText(sample_val)

            # Connect selection change to live update sample values
            try:
                combo.currentIndexChanged.disconnect()
            except Exception:
                pass
            combo.currentIndexChanged.connect(lambda _, r=row: self._on_mapping_combo_changed(r))

            suggestion = evidence.get(canonical)
            if suggestion is None:
                text = "No automatic suggestion"
            else:
                review = " — review" if suggestion.confidence < 0.9 else ""
                text = f"{suggestion.confidence:.0%}: {suggestion.reason}{review}"
            ev_item = self.mapping_table.item(row, 4)
            if ev_item is None:
                ev_item = QTableWidgetItem(text)
                ev_item.setFlags(ev_item.flags() & ~enum_member(Qt, "ItemFlag", "ItemIsEditable"))
                self.mapping_table.setItem(row, 4, ev_item)
            else:
                ev_item.setText(text)

    def _on_mapping_combo_changed(self, row: int):
        combo = self.mapping_table.cellWidget(row, 1)
        if not combo:
            return
        col_name = combo.currentData()
        sample_val = getattr(self, "current_sample_values", {}).get(col_name, "—") if col_name else "—"
        val_item = self.mapping_table.item(row, 3)
        if val_item:
            val_item.setText(sample_val)

        canonical = list(FIELD_ALIASES.keys())[row] if row < len(FIELD_ALIASES) else None
        unit_combo = self.mapping_table.cellWidget(row, 2)
        if canonical in {"yield_dry_mass_area", "yield_wet_mass_area"} and unit_combo and sample_val != "—":
            clean_str = sample_val.replace("–", ",").replace("-", ",").replace("(", ",").replace(")", ",").replace("range:", "")
            nums = []
            for part in clean_str.split(","):
                part_clean = part.strip().replace("'", "").replace('"', "")
                try:
                    nums.append(float(part_clean))
                except (ValueError, TypeError):
                    pass
            if nums and max(nums) > 450:
                idx = unit_combo.findData("lb/ac")
                if idx >= 0:
                    unit_combo.setCurrentIndex(idx)

    def _reviewed_mapping(self):
        mapping = {}
        for row, canonical in enumerate(FIELD_ALIASES):
            combo = self.mapping_table.cellWidget(row, 1)
            if combo:
                source_column = combo.currentData()
                if source_column:
                    mapping[canonical] = str(source_column)
        return mapping

    def _reviewed_source_units(self):
        source_units = {}
        for row, canonical in enumerate(FIELD_ALIASES):
            combo = self.mapping_table.cellWidget(row, 1)
            unit_combo = self.mapping_table.cellWidget(row, 2)
            if combo and combo.currentData() and unit_combo:
                u = unit_combo.currentData()
                if u:
                    source_units[canonical] = str(u)
        return source_units

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
            source_units=self._reviewed_source_units(),
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

    def _build_clean_tab(self):
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        intro = QLabel(
            "Interactive Filtering, Mapping, and Editing (inspired by USDA-ARS Yield Editor). "
            "Configure filter thresholds, inspect live deleted point counts, view the in-modal cleaned observations map, "
            "and manually select or exclude points directly on the map canvas."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        top_grid = QHBoxLayout()

        # Left Column: Filter Selection & Parameters (USDA Yield Editor Grid)
        filters_group = QGroupBox("Filter Selection & Live Excluded Counts")
        filter_grid = QGridLayout(filters_group)
        filter_grid.addWidget(QLabel("<b>Use?</b>"), 0, 0)
        filter_grid.addWidget(QLabel("<b>Parameter</b>"), 0, 1)
        filter_grid.addWidget(QLabel("<b>Filter Name</b>"), 0, 2)
        filter_grid.addWidget(QLabel("<b>Deleted Points</b>"), 0, 3)

        # 1. Flow Delay
        self.flow_delay_check = QCheckBox()
        self.flow_delay_check.setChecked(False)
        self.flow_delay_spin = QDoubleSpinBox()
        self.flow_delay_spin.setRange(0.0, 60.0)
        self.flow_delay_spin.setValue(12.0)
        self.flow_delay_spin.setSuffix(" s")
        self.flow_delay_count_lbl = QLabel("0")
        self.flow_delay_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.flow_delay_check, 1, 0)
        filter_grid.addWidget(self.flow_delay_spin, 1, 1)
        filter_grid.addWidget(QLabel("Flow Delay"), 1, 2)
        filter_grid.addWidget(self.flow_delay_count_lbl, 1, 3)

        # 2. Moisture Delay
        self.moisture_delay_check = QCheckBox()
        self.moisture_delay_check.setChecked(False)
        self.moisture_delay_spin = QDoubleSpinBox()
        self.moisture_delay_spin.setRange(0.0, 60.0)
        self.moisture_delay_spin.setValue(8.0)
        self.moisture_delay_spin.setSuffix(" s")
        self.moisture_delay_count_lbl = QLabel("0")
        self.moisture_delay_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.moisture_delay_check, 2, 0)
        filter_grid.addWidget(self.moisture_delay_spin, 2, 1)
        filter_grid.addWidget(QLabel("Moisture Delay"), 2, 2)
        filter_grid.addWidget(self.moisture_delay_count_lbl, 2, 3)

        # 3. Start Pass Trim
        self.pass_start_check = QCheckBox()
        self.pass_start_check.setChecked(True)
        self.trim_start_spin = QSpinBox()
        self.trim_start_spin.setRange(0, 50)
        self.trim_start_spin.setValue(2)
        self.trim_start_spin.setSuffix(" pts")
        self.pass_start_count_lbl = QLabel("0")
        self.pass_start_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.pass_start_check, 3, 0)
        filter_grid.addWidget(self.trim_start_spin, 3, 1)
        filter_grid.addWidget(QLabel("Start Pass Trim"), 3, 2)
        filter_grid.addWidget(self.pass_start_count_lbl, 3, 3)

        # 4. End Pass Trim
        self.pass_end_check = QCheckBox()
        self.pass_end_check.setChecked(True)
        self.trim_end_spin = QSpinBox()
        self.trim_end_spin.setRange(0, 50)
        self.trim_end_spin.setValue(2)
        self.trim_end_spin.setSuffix(" pts")
        self.pass_end_count_lbl = QLabel("0")
        self.pass_end_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.pass_end_check, 4, 0)
        filter_grid.addWidget(self.trim_end_spin, 4, 1)
        filter_grid.addWidget(QLabel("End Pass Trim"), 4, 2)
        filter_grid.addWidget(self.pass_end_count_lbl, 4, 3)

        # 5. Max Velocity
        self.max_speed_check = QCheckBox()
        self.max_speed_check.setChecked(True)
        self.max_speed_spin = QDoubleSpinBox()
        self.max_speed_spin.setRange(0.5, 60.0)
        self.max_speed_spin.setValue(10.0)
        self.max_speed_spin.setSuffix(" mph")
        self.max_speed_count_lbl = QLabel("0")
        self.max_speed_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.max_speed_check, 5, 0)
        filter_grid.addWidget(self.max_speed_spin, 5, 1)
        filter_grid.addWidget(QLabel("Max Velocity"), 5, 2)
        filter_grid.addWidget(self.max_speed_count_lbl, 5, 3)

        # 6. Min Velocity
        self.min_speed_check = QCheckBox()
        self.min_speed_check.setChecked(True)
        self.min_speed_spin = QDoubleSpinBox()
        self.min_speed_spin.setRange(0.1, 50.0)
        self.min_speed_spin.setValue(1.0)
        self.min_speed_spin.setSuffix(" mph")
        self.min_speed_count_lbl = QLabel("0")
        self.min_speed_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.min_speed_check, 6, 0)
        filter_grid.addWidget(self.min_speed_spin, 6, 1)
        filter_grid.addWidget(QLabel("Min Velocity"), 6, 2)
        filter_grid.addWidget(self.min_speed_count_lbl, 6, 3)

        # 7. Minimum Swath
        self.min_swath_check = QCheckBox()
        self.min_swath_check.setChecked(True)
        self.min_swath_spin = QDoubleSpinBox()
        self.min_swath_spin.setRange(0.1, 200.0)
        self.min_swath_spin.setValue(3.28)
        self.min_swath_spin.setSuffix(" ft")
        self.min_swath_count_lbl = QLabel("0")
        self.min_swath_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.min_swath_check, 7, 0)
        filter_grid.addWidget(self.min_swath_spin, 7, 1)
        filter_grid.addWidget(QLabel("Minimum Swath"), 7, 2)
        filter_grid.addWidget(self.min_swath_count_lbl, 7, 3)

        # 8. Maximum Yield
        self.max_yield_check = QCheckBox()
        self.max_yield_check.setChecked(True)
        self.max_yield_spin = QDoubleSpinBox()
        self.max_yield_spin.setRange(1.0, 100000.0)
        self.max_yield_spin.setValue(350.0)
        self.max_yield_spin.setSuffix(" bu/ac")
        self.max_yield_count_lbl = QLabel("0")
        self.max_yield_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.max_yield_check, 8, 0)
        filter_grid.addWidget(self.max_yield_spin, 8, 1)
        filter_grid.addWidget(QLabel("Maximum Yield"), 8, 2)
        filter_grid.addWidget(self.max_yield_count_lbl, 8, 3)

        # 9. Minimum Yield
        self.min_yield_check = QCheckBox()
        self.min_yield_check.setChecked(True)
        self.min_yield_spin = QDoubleSpinBox()
        self.min_yield_spin.setRange(0.0, 100000.0)
        self.min_yield_spin.setValue(10.0)
        self.min_yield_spin.setSuffix(" bu/ac")
        self.min_yield_count_lbl = QLabel("0")
        self.min_yield_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.min_yield_check, 9, 0)
        filter_grid.addWidget(self.min_yield_spin, 9, 1)
        filter_grid.addWidget(QLabel("Minimum Yield"), 9, 2)
        filter_grid.addWidget(self.min_yield_count_lbl, 9, 3)

        # 10. Local Spatial STD / MAD Filter
        self.outlier_check = QCheckBox()
        self.outlier_check.setChecked(True)
        self.outlier_std_spin = QDoubleSpinBox()
        self.outlier_std_spin.setRange(1.0, 10.0)
        self.outlier_std_spin.setValue(3.0)
        self.outlier_std_spin.setDecimals(1)
        self.outlier_std_spin.setSuffix(" MAD")
        self.outlier_radius_spin = QDoubleSpinBox()
        self.outlier_radius_spin.setRange(1.0, 500.0)
        self.outlier_radius_spin.setValue(82.0)
        self.outlier_radius_spin.setSuffix(" ft")
        self.outlier_count_lbl = QLabel("0")
        self.outlier_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.outlier_check, 10, 0)
        filter_grid.addWidget(self.outlier_std_spin, 10, 1)
        filter_grid.addWidget(QLabel("Local Spatial STD"), 10, 2)
        filter_grid.addWidget(self.outlier_count_lbl, 10, 3)

        # 11. Swath Overlap
        self.overlap_check = QCheckBox()
        self.overlap_check.setChecked(True)
        self.overlap_dist_spin = QDoubleSpinBox()
        self.overlap_dist_spin.setRange(0.5, 50.0)
        self.overlap_dist_spin.setValue(9.84)
        self.overlap_dist_spin.setSuffix(" ft")
        self.overlap_count_lbl = QLabel("0")
        self.overlap_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.overlap_check, 11, 0)
        filter_grid.addWidget(self.overlap_dist_spin, 11, 1)
        filter_grid.addWidget(QLabel("Overlap (Auto)"), 11, 2)
        filter_grid.addWidget(self.overlap_count_lbl, 11, 3)

        # 12. Header Down Req
        self.header_req_check = QCheckBox()
        self.header_req_check.setChecked(False)
        self.header_count_lbl = QLabel("0")
        self.header_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(self.header_req_check, 12, 0)
        filter_grid.addWidget(QLabel("Optional"), 12, 1)
        filter_grid.addWidget(QLabel("Header Down Req"), 12, 2)
        filter_grid.addWidget(self.header_count_lbl, 12, 3)

        # 13. Manual Deletes
        self.manual_deletes_count_lbl = QLabel("0")
        self.manual_deletes_count_lbl.setStyleSheet("color: #d32f2f; font-weight: bold;")
        filter_grid.addWidget(QLabel("-"), 13, 0)
        filter_grid.addWidget(QLabel("Interactive"), 13, 1)
        filter_grid.addWidget(QLabel("Manual Deletions"), 13, 2)
        filter_grid.addWidget(self.manual_deletes_count_lbl, 13, 3)

        # 14. HTML Review Grid Size
        self.grid_size_spin = QDoubleSpinBox()
        self.grid_size_spin.setRange(5.0, 500.0)
        self.grid_size_spin.setValue(30.0)
        self.grid_size_spin.setSuffix(" ft")
        self.grid_size_spin.setToolTip("Interpolated yield surface grid cell resolution for the HTML review map")
        filter_grid.addWidget(QLabel("-"), 14, 0)
        filter_grid.addWidget(self.grid_size_spin, 14, 1)
        filter_grid.addWidget(QLabel("HTML Surface Grid"), 14, 2)
        filter_grid.addWidget(QLabel("30 ft def"), 14, 3)

        btn_row = QHBoxLayout()
        reset_defaults_button = QPushButton("Reset to Crop Defaults")
        reset_defaults_button.clicked.connect(self._reset_recipe_defaults)
        btn_row.addWidget(reset_defaults_button)
        filter_grid.addLayout(btn_row, 15, 0, 1, 4)

        # Wire all recipe parameter inputs to signal re-execution readiness
        for spin in (
            self.flow_delay_spin, self.moisture_delay_spin, self.trim_start_spin,
            self.trim_end_spin, self.max_speed_spin, self.min_speed_spin,
            self.min_swath_spin, self.max_yield_spin, self.min_yield_spin,
            self.outlier_std_spin, self.outlier_radius_spin, self.overlap_dist_spin,
            self.grid_size_spin
        ):
            spin.valueChanged.connect(self._on_recipe_parameter_changed)

        for chk in (
            self.flow_delay_check, self.moisture_delay_check, self.pass_start_check,
            self.pass_end_check, self.max_speed_check, self.min_speed_check,
            self.min_swath_check, self.max_yield_check, self.min_yield_check,
            self.outlier_check, self.overlap_check, self.header_req_check
        ):
            chk.toggled.connect(self._on_recipe_parameter_changed)

        top_grid.addWidget(filters_group, 3)

        # Right Column: Yield Statistics (Clean vs Raw)
        stats_group = QGroupBox("Yield Statistics (Clean vs Raw)")
        stats_layout = QVBoxLayout(stats_group)
        self.clean_status = QTextBrowser()
        self.clean_status.setHtml(
            "<h3>Dataset not cleaned yet</h3>"
            "<p>Prepare a dataset on Step 3, then configure recipe parameters and click "
            "<b>Execute Cleaning Pipeline / Apply Filters</b>.</p>"
        )
        stats_layout.addWidget(self.clean_status)
        top_grid.addWidget(stats_group, 3)

        layout.addLayout(top_grid)

        # Execution Button
        self.execute_button = QPushButton("Execute Cleaning Pipeline / Apply Filters")
        self.execute_button.setObjectName("executeCleaningButton")
        self.execute_button.setEnabled(False)
        self.execute_button.clicked.connect(self._run_cleaning_pipeline)
        self._style_button_action_needed(self.execute_button)
        layout.addWidget(self.execute_button)

        self.clean_progress = QProgressBar()
        self.clean_progress.setRange(0, 0)
        self.clean_progress.setVisible(False)
        layout.addWidget(self.clean_progress)

        # Bottom Section (The Red Box): Clean & Review Interactive Map & Manual Cleanup Canvas
        self.clean_map_group = QGroupBox("Clean & Review Interactive Map & Manual Cleanup Tools")
        clean_map_layout = QVBoxLayout(self.clean_map_group)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("<b>Attribute:</b>"))
        self.clean_attribute_combo = QComboBox()
        self.clean_attribute_combo.addItem("Dry Yield", "yield_dry_mass_area")
        self.clean_attribute_combo.addItem("Exclusion Status (Clean / Excluded)", "clean_status")
        self.clean_attribute_combo.addItem("Wet Yield", "yield_wet_mass_area")
        self.clean_attribute_combo.addItem("Moisture %", "moisture_pct")
        self.clean_attribute_combo.addItem("Ground Speed", "speed_m_s")
        self.clean_attribute_combo.addItem("Swath Width", "swath_width_m")
        self.clean_attribute_combo.addItem("Pass ID", "pass_id")
        self.clean_attribute_combo.addItem("Elevation", "elevation_m")
        ctrl_row.addWidget(self.clean_attribute_combo)

        ctrl_row.addWidget(QLabel("<b>Color Ramp:</b>"))
        self.clean_ramp_combo = QComboBox()
        self.clean_ramp_combo.addItem("RdYlGn (Red-Yellow-Green)", "RdYlGn")
        self.clean_ramp_combo.addItem("Viridis", "Viridis")
        self.clean_ramp_combo.addItem("Spectral", "Spectral")
        self.clean_ramp_combo.addItem("Blues", "Blues")
        self.clean_ramp_combo.addItem("YlOrRd (Yellow-Orange-Red)", "YlOrRd")
        ctrl_row.addWidget(self.clean_ramp_combo)

        self.clean_select_tool_btn = QPushButton("🔲 Select Points (Drag Box)")
        self.clean_select_tool_btn.setCheckable(True)
        self.clean_select_tool_btn.setChecked(True)
        self.clean_select_tool_btn.setToolTip("Click and drag a box on the map to select points for manual cleanup")
        self.clean_select_tool_btn.toggled.connect(self._toggle_clean_selection_tool)
        ctrl_row.addWidget(self.clean_select_tool_btn)

        self.exclude_selected_btn = QPushButton("❌ Exclude Selected (Delete)")
        self.exclude_selected_btn.setToolTip("Manually exclude selected points from cleaned yield dataset")
        self.exclude_selected_btn.clicked.connect(self._exclude_selected_points)
        ctrl_row.addWidget(self.exclude_selected_btn)

        self.restore_selected_btn = QPushButton("♻️ Restore Selected (Un-delete)")
        self.restore_selected_btn.setToolTip("Restore manually excluded selected points back to accepted")
        self.restore_selected_btn.clicked.connect(self._restore_selected_points)
        ctrl_row.addWidget(self.restore_selected_btn)

        self.clear_manual_deletes_btn = QPushButton("↶ Clear All Deletions")
        self.clear_manual_deletes_btn.setToolTip("Clear all manual point exclusions")
        self.clear_manual_deletes_btn.clicked.connect(self._clear_manual_deletes)
        ctrl_row.addWidget(self.clear_manual_deletes_btn)

        self.clean_pan_btn = QPushButton("✋ Pan")
        self.clean_pan_btn.setToolTip("Pan map canvas")
        self.clean_pan_btn.clicked.connect(self._activate_clean_pan)
        ctrl_row.addWidget(self.clean_pan_btn)

        self.clean_zoom_in_btn = QPushButton("🔍+")
        self.clean_zoom_in_btn.clicked.connect(lambda: self.clean_map_canvas.zoomIn() if self.clean_map_canvas else None)
        ctrl_row.addWidget(self.clean_zoom_in_btn)

        self.clean_zoom_out_btn = QPushButton("🔍-")
        self.clean_zoom_out_btn.clicked.connect(lambda: self.clean_map_canvas.zoomOut() if self.clean_map_canvas else None)
        ctrl_row.addWidget(self.clean_zoom_out_btn)

        self.clean_zoom_full_btn = QPushButton("📐 Zoom Full")
        self.clean_zoom_full_btn.clicked.connect(self._zoom_clean_full)
        ctrl_row.addWidget(self.clean_zoom_full_btn)

        self.clean_selection_label = QLabel("Selected: 0 points")
        self.clean_selection_label.setStyleSheet("color: #0369a1; font-weight: bold; padding: 2px 6px;")
        ctrl_row.addWidget(self.clean_selection_label)

        ctrl_row.addStretch(1)
        clean_map_layout.addLayout(ctrl_row)

        if QgsMapCanvas is not None:
            self.clean_map_canvas = QgsMapCanvas(self)
            self.clean_map_canvas.setCanvasColor(QColor("#f8fafc"))
            self.clean_map_canvas.setMinimumHeight(240)
            clean_map_layout.addWidget(self.clean_map_canvas)
        else:
            self.clean_map_canvas = None

        # Live Classification Legend Bar
        self.clean_legend_widget = QWidget()
        self.clean_legend_layout = QHBoxLayout(self.clean_legend_widget)
        self.clean_legend_layout.setContentsMargins(4, 2, 4, 2)
        self.clean_legend_layout.setSpacing(6)
        clean_map_layout.addWidget(self.clean_legend_widget)

        self.clean_scale_label = QLabel("📏 <b>Scale:</b> 1:— &bull; <b>Display Units:</b> — &bull; <b>CRS:</b> —")
        self.clean_scale_label.setStyleSheet("color: #475569; font-size: 11px; padding: 4px 8px; background: #f1f5f9; border-radius: 4px; border: 1px solid #e2e8f0;")
        clean_map_layout.addWidget(self.clean_scale_label)

        if self.clean_map_canvas is not None:
            self.clean_map_canvas.scaleChanged.connect(self._update_clean_scale)
            self.clean_map_canvas.extentsChanged.connect(self._update_clean_scale)

        self.clean_attribute_combo.currentIndexChanged.connect(self._apply_clean_preview_styling)
        self.clean_ramp_combo.currentIndexChanged.connect(self._apply_clean_preview_styling)

        layout.addWidget(self.clean_map_group)

        # Post-run export layout
        post_run_layout = QHBoxLayout()
        self.open_review_button = QPushButton("Open HTML Review Report")
        self.open_review_button.setEnabled(False)
        self.open_review_button.clicked.connect(self._open_html_review)

        self.open_log_button = QPushButton("Open Run Log")
        self.open_log_button.setEnabled(False)
        self.open_log_button.clicked.connect(self._open_run_log)

        self.open_folder_button = QPushButton("Open Run Folder")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self._open_run_folder)

        self.export_adapt_button = QPushButton("Export ADAPT Standard Package...")
        self.export_adapt_button.setEnabled(False)
        self.export_adapt_button.clicked.connect(self._export_adapt_package)

        post_run_layout.addWidget(self.open_review_button)
        post_run_layout.addWidget(self.open_log_button)
        post_run_layout.addWidget(self.open_folder_button)
        post_run_layout.addWidget(self.export_adapt_button)
        layout.addLayout(post_run_layout)

        scroll.setWidget(scroll_content)
        tab_layout = QVBoxLayout(tab)
        tab_layout.addWidget(scroll)
        return tab

    def _reset_recipe_defaults(self):
        crop = str(self.crop_combo.currentData() or "corn")
        is_metric = str(self.units_combo.currentData() or "imperial") == "metric"
        default_recipe = default_recipe_for_crop(crop)
        self.flow_delay_check.setChecked(default_recipe.apply_flow_delay)
        self.flow_delay_spin.setValue(default_recipe.flow_delay_s)
        self.moisture_delay_check.setChecked(default_recipe.apply_moisture_delay)
        self.moisture_delay_spin.setValue(default_recipe.moisture_delay_s)
        self.pass_start_check.setChecked(default_recipe.filter_pass_start)
        self.trim_start_spin.setValue(default_recipe.pass_start_count)
        self.pass_end_check.setChecked(default_recipe.filter_pass_end)
        self.trim_end_spin.setValue(default_recipe.pass_end_count)
        self.overlap_check.setChecked(default_recipe.filter_overlap)
        self.outlier_check.setChecked(default_recipe.filter_local_outlier)
        self.outlier_std_spin.setValue(default_recipe.local_outlier_std_devs)
        self.header_req_check.setChecked(default_recipe.filter_header_disengaged)

        tw = float(self.test_weight_spin.value() if hasattr(self, "test_weight_spin") else 56.0)

        if is_metric:
            self.min_speed_spin.setSuffix(" m/s")
            self.max_speed_spin.setSuffix(" m/s")
            self.min_speed_spin.setValue(default_recipe.min_speed_m_s)
            self.max_speed_spin.setValue(default_recipe.max_speed_m_s)
            self.min_swath_spin.setSuffix(" m")
            self.min_swath_spin.setValue(default_recipe.min_swath_width_m)
            self.overlap_dist_spin.setSuffix(" m")
            self.overlap_dist_spin.setValue(default_recipe.overlap_distance_threshold_m)
            self.outlier_radius_spin.setSuffix(" m")
            self.outlier_radius_spin.setValue(default_recipe.local_outlier_radius_m)
            self.min_yield_spin.setSuffix(" kg/ha")
            self.max_yield_spin.setSuffix(" kg/ha")
            self.min_yield_spin.setValue(default_recipe.min_yield_kg_ha)
            self.max_yield_spin.setValue(default_recipe.max_yield_kg_ha)
            if hasattr(self, "grid_size_spin"):
                self.grid_size_spin.setSuffix(" m")
                self.grid_size_spin.setValue(10.0)
        else:
            self.min_speed_spin.setSuffix(" mph")
            self.max_speed_spin.setSuffix(" mph")
            self.min_speed_spin.setValue(round(m_per_s_to_mph(default_recipe.min_speed_m_s), 1))
            self.max_speed_spin.setValue(round(m_per_s_to_mph(default_recipe.max_speed_m_s), 1))
            self.min_swath_spin.setSuffix(" ft")
            self.min_swath_spin.setValue(round(default_recipe.min_swath_width_m * 3.28084, 1))
            self.overlap_dist_spin.setSuffix(" ft")
            self.overlap_dist_spin.setValue(round(default_recipe.overlap_distance_threshold_m * 3.28084, 1))
            self.outlier_radius_spin.setSuffix(" ft")
            self.outlier_radius_spin.setValue(round(default_recipe.local_outlier_radius_m * 3.28084, 1))
            self.min_yield_spin.setSuffix(" bu/ac")
            self.max_yield_spin.setSuffix(" bu/ac")
            min_bu = kg_per_hectare_to_bushels_per_acre(default_recipe.min_yield_kg_ha, tw)
            max_bu = kg_per_hectare_to_bushels_per_acre(default_recipe.max_yield_kg_ha, tw)
            self.min_yield_spin.setValue(round(min_bu, 1))
            self.max_yield_spin.setValue(round(max_bu, 1))
            if hasattr(self, "grid_size_spin"):
                self.grid_size_spin.setSuffix(" ft")
                self.grid_size_spin.setValue(30.0)

        for lbl in (
            self.flow_delay_count_lbl,
            self.moisture_delay_count_lbl,
            self.pass_start_count_lbl,
            self.pass_end_count_lbl,
            self.min_speed_count_lbl,
            self.max_speed_count_lbl,
            self.min_swath_count_lbl,
            self.min_yield_count_lbl,
            self.max_yield_count_lbl,
            self.outlier_count_lbl,
            self.overlap_count_lbl,
            self.header_count_lbl,
            self.manual_deletes_count_lbl,
        ):
            lbl.setText("0")

    def _on_recipe_parameter_changed(self, *args):
        if hasattr(self, "execute_button") and getattr(self, "current_prepared_layer", None) is not None:
            self.execute_button.setEnabled(True)
            self._style_button_action_needed(self.execute_button, "Execute Cleaning Pipeline / Apply Filters")

    def _collect_recipe_from_ui(self) -> CleaningRecipe:
        crop = str(self.crop_combo.currentData() or "corn")
        is_metric = str(self.units_combo.currentData() or "imperial") == "metric"
        if is_metric:
            speed_min = self.min_speed_spin.value()
            speed_max = self.max_speed_spin.value()
            swath_min = self.min_swath_spin.value()
            overlap_dist = self.overlap_dist_spin.value()
            outlier_radius = self.outlier_radius_spin.value()
            yield_min = self.min_yield_spin.value()
            yield_max = self.max_yield_spin.value()
        else:
            tw = float(self.test_weight_spin.value() if hasattr(self, "test_weight_spin") else 56.0)
            speed_min = mph_to_m_per_s(self.min_speed_spin.value())
            speed_max = mph_to_m_per_s(self.max_speed_spin.value())
            swath_min = self.min_swath_spin.value() * 0.3048
            overlap_dist = self.overlap_dist_spin.value() * 0.3048
            outlier_radius = self.outlier_radius_spin.value() * 0.3048
            yield_min = bushels_per_acre_to_kg_per_hectare(self.min_yield_spin.value(), tw)
            yield_max = bushels_per_acre_to_kg_per_hectare(self.max_yield_spin.value(), tw)

        return CleaningRecipe(
            crop_code=crop,
            unit_profile="metric" if is_metric else "imperial",
            apply_flow_delay=self.flow_delay_check.isChecked(),
            flow_delay_s=self.flow_delay_spin.value(),
            apply_moisture_delay=self.moisture_delay_check.isChecked(),
            moisture_delay_s=self.moisture_delay_spin.value(),
            filter_header_disengaged=self.header_req_check.isChecked(),
            filter_min_speed=self.min_speed_check.isChecked(),
            min_speed_m_s=speed_min,
            filter_max_speed=self.max_speed_check.isChecked(),
            max_speed_m_s=speed_max,
            filter_min_swath=self.min_swath_check.isChecked(),
            min_swath_width_m=swath_min,
            filter_pass_start=self.pass_start_check.isChecked() and self.trim_start_spin.value() > 0,
            pass_start_count=int(self.trim_start_spin.value()),
            filter_pass_end=self.pass_end_check.isChecked() and self.trim_end_spin.value() > 0,
            pass_end_count=int(self.trim_end_spin.value()),
            filter_overlap=self.overlap_check.isChecked(),
            overlap_distance_threshold_m=overlap_dist,
            filter_min_yield=self.min_yield_check.isChecked(),
            min_yield_kg_ha=yield_min,
            filter_max_yield=self.max_yield_check.isChecked(),
            max_yield_kg_ha=yield_max,
            filter_local_outlier=self.outlier_check.isChecked(),
            local_outlier_radius_m=outlier_radius,
            local_outlier_std_devs=self.outlier_std_spin.value(),
        )

    def _update_clean_scale(self):
        if self.clean_map_canvas is None or not hasattr(self, "clean_scale_label"):
            return
        scale = self.clean_map_canvas.scale()
        crs_auth = "Unresolved"
        if hasattr(self, "current_clean_preview_layer") and self.current_clean_preview_layer and self.current_clean_preview_layer.isValid():
            crs_auth = self.current_clean_preview_layer.crs().authid()
        is_metric = str(self.units_combo.currentData() or "imperial") == "metric"
        unit_str = "Metric (Meters, kg/ha)" if is_metric else "Imperial (Feet, bu/ac)"
        self.clean_scale_label.setText(
            f"📏 <b>Scale:</b> 1:{int(scale):,} &bull; <b>Display Units:</b> {unit_str} &bull; <b>CRS:</b> {crs_auth}"
        )

    def _update_clean_legend(self):
        if not hasattr(self, "clean_legend_layout") or not hasattr(self, "current_clean_preview_layer") or not self.current_clean_preview_layer or not self.current_clean_preview_layer.isValid():
            return
        while self.clean_legend_layout.count():
            item = self.clean_legend_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        items = get_layer_graduated_legend_items(self.current_clean_preview_layer)
        if not items:
            return

        attr = str(self.clean_attribute_combo.currentData() or "yield_dry_mass_area")
        is_metric = str(self.units_combo.currentData() or "imperial") == "metric"
        unit_label = ""
        if "yield" in attr:
            unit_label = "kg/ha" if is_metric else "bu/ac"
        elif "speed" in attr:
            unit_label = "m/s" if is_metric else "mph"
        elif "swath" in attr or "elevation" in attr:
            unit_label = "m" if is_metric else "ft"
        elif "moisture" in attr:
            unit_label = "%"

        hdr_lbl = QLabel(f"<b>Legend ({attr.replace('_', ' ').title()}):</b>")
        hdr_lbl.setStyleSheet("font-size: 11px; color: #1e293b; font-weight: bold;")
        self.clean_legend_layout.addWidget(hdr_lbl)

        for item in items:
            color = item.get("color", "#3388ff")
            label_text = item.get("label", "")
            if "lower" in item and "upper" in item:
                low = item["lower"]
                up = item["upper"]
                if "yield" in attr and not is_metric:
                    tw = float(self.test_weight_spin.value() if hasattr(self, "test_weight_spin") else 56.0)
                    if low > 300 or up > 300:
                        low = kg_per_hectare_to_bushels_per_acre(low, tw)
                        up = kg_per_hectare_to_bushels_per_acre(up, tw)
                label_text = f"{low:.1f} – {up:.1f} {unit_label}".strip()

            chip = QLabel(f"<span style='color: {color}; font-size: 14px;'>■</span> {label_text}")
            chip.setStyleSheet("font-size: 11px; color: #334155; padding: 2px 6px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;")
            self.clean_legend_layout.addWidget(chip)

        self.clean_legend_layout.addStretch(1)

    def _apply_clean_preview_styling(self):
        if not hasattr(self, "current_clean_preview_layer") or not self.current_clean_preview_layer or not self.current_clean_preview_layer.isValid():
            return
        attr = str(self.clean_attribute_combo.currentData() or "yield_dry_mass_area")
        ramp = str(self.clean_ramp_combo.currentData() or "RdYlGn")

        if attr == "clean_status":
            self.current_clean_preview_layer.setSubsetString("")
            style_layer_for_display(self.current_clean_preview_layer, mode="status")
        else:
            self.current_clean_preview_layer.setSubsetString("clean_status = 'accepted'")
            style_layer_with_attribute_and_ramp(self.current_clean_preview_layer, attr, ramp)

        self._update_clean_legend()
        if self.clean_map_canvas is not None:
            self.clean_map_canvas.setLayers([self.current_clean_preview_layer])
            self.clean_map_canvas.refresh()

    def _toggle_clean_selection_tool(self, active: bool):
        if self.clean_map_canvas is None:
            return
        if active:
            self.clean_select_tool = ModalPointSelectTool(
                self.clean_map_canvas,
                lambda: getattr(self, "current_clean_preview_layer", None),
                self._on_clean_selection_changed,
            )
            self.clean_map_canvas.setMapTool(self.clean_select_tool)
        else:
            if QgsMapToolPan is not None:
                self.clean_pan_tool = QgsMapToolPan(self.clean_map_canvas)
                self.clean_map_canvas.setMapTool(self.clean_pan_tool)

    def _activate_clean_pan(self):
        if self.clean_map_canvas is None:
            return
        self.clean_select_tool_btn.blockSignals(True)
        self.clean_select_tool_btn.setChecked(False)
        self.clean_select_tool_btn.blockSignals(False)
        if QgsMapToolPan is not None:
            self.clean_pan_tool = QgsMapToolPan(self.clean_map_canvas)
            self.clean_map_canvas.setMapTool(self.clean_pan_tool)

    def _zoom_clean_full(self):
        if self.clean_map_canvas is not None and hasattr(self, "current_clean_preview_layer") and self.current_clean_preview_layer and self.current_clean_preview_layer.isValid():
            self.clean_map_canvas.setExtent(self.current_clean_preview_layer.extent())
            self.clean_map_canvas.refresh()
            self._update_clean_scale()

    def _on_clean_selection_changed(self, selected_ids):
        if hasattr(self, "clean_selection_label"):
            self.clean_selection_label.setText(f"Selected: {len(selected_ids):,} points")

    def _exclude_selected_points(self):
        if not hasattr(self, "current_clean_preview_layer") or not self.current_clean_preview_layer or not self.current_clean_preview_layer.isValid():
            QMessageBox.information(self, PLUGIN_NAME, "Clean dataset first, then select points.")
            return
        selected_feats = list(self.current_clean_preview_layer.selectedFeatures())
        if not selected_feats:
            QMessageBox.information(self, PLUGIN_NAME, "No points selected on the map. Drag a box over points first.")
            return
        for feat in selected_feats:
            s_idx = feat["source_index"] if "source_index" in [f.name() for f in self.current_clean_preview_layer.fields()] else feat.id()
            try:
                idx_num = int(s_idx)
            except (ValueError, TypeError):
                idx_num = feat.id()
            self.manual_excluded_ids.add(idx_num)
            self.manual_restored_ids.discard(idx_num)
        self.manual_deletes_count_lbl.setText(f"{len(self.manual_excluded_ids):,}")
        self.current_clean_preview_layer.removeSelection()
        self.clean_selection_label.setText("Selected: 0 points")
        self._recompute_and_refresh_clean_view()
        self._on_recipe_parameter_changed()

    def _restore_selected_points(self):
        if not hasattr(self, "current_clean_preview_layer") or not self.current_clean_preview_layer or not self.current_clean_preview_layer.isValid():
            return
        selected_feats = list(self.current_clean_preview_layer.selectedFeatures())
        if not selected_feats:
            QMessageBox.information(self, PLUGIN_NAME, "No points selected on the map. Drag a box over points first.")
            return
        for feat in selected_feats:
            s_idx = feat["source_index"] if "source_index" in [f.name() for f in self.current_clean_preview_layer.fields()] else feat.id()
            try:
                idx_num = int(s_idx)
            except (ValueError, TypeError):
                idx_num = feat.id()
            self.manual_restored_ids.add(idx_num)
            self.manual_excluded_ids.discard(idx_num)
        self.manual_deletes_count_lbl.setText(f"{len(self.manual_excluded_ids):,}")
        self.current_clean_preview_layer.removeSelection()
        self.clean_selection_label.setText("Selected: 0 points")
        self._recompute_and_refresh_clean_view()
        self._on_recipe_parameter_changed()

    def _clear_manual_deletes(self):
        self.manual_excluded_ids.clear()
        self.manual_restored_ids.clear()
        self.manual_deletes_count_lbl.setText("0")
        if hasattr(self, "current_clean_preview_layer") and self.current_clean_preview_layer and self.current_clean_preview_layer.isValid():
            self.current_clean_preview_layer.removeSelection()
        self.clean_selection_label.setText("Selected: 0 points")
        self._recompute_and_refresh_clean_view()
        self._on_recipe_parameter_changed()

    def _recompute_and_refresh_clean_view(self):
        if not hasattr(self, "current_observations") or not self.current_observations:
            return
        try:
            for idx, obs in enumerate(self.current_observations):
                s_idx = obs.get("source_index", idx)
                try:
                    idx_num = int(s_idx)
                except (ValueError, TypeError):
                    idx_num = idx
                if idx_num in self.manual_excluded_ids:
                    obs["manual_action"] = "exclude"
                elif idx_num in self.manual_restored_ids:
                    obs["manual_action"] = "restore"
                else:
                    obs["manual_action"] = "none"

            recipe = self._collect_recipe_from_ui()
            cleaning_result = run_cleaning_filters(self.current_observations, recipe)
            self.current_cleaning_result = cleaning_result

            if hasattr(self, "current_clean_preview_layer") and self.current_clean_preview_layer and self.current_clean_preview_layer.isValid():
                self.current_clean_preview_layer.setSubsetString("")
                status_idx = self.current_clean_preview_layer.fields().indexOf("clean_status")
                reasons_idx = self.current_clean_preview_layer.fields().indexOf("filter_reasons")
                if status_idx >= 0:
                    self.current_clean_preview_layer.startEditing()
                    for feat in self.current_clean_preview_layer.getFeatures():
                        s_idx = feat["source_index"] if "source_index" in [f.name() for f in self.current_clean_preview_layer.fields()] else feat.id()
                        try:
                            idx_num = int(s_idx)
                        except (ValueError, TypeError):
                            idx_num = feat.id()
                        if idx_num < len(cleaning_result.observation_updates):
                            upd = cleaning_result.observation_updates[idx_num]
                            status_val = upd.get("clean_status", "accepted")
                            reasons_val = upd.get("filter_reasons", "")
                            self.current_clean_preview_layer.changeAttributeValue(feat.id(), status_idx, status_val)
                            if reasons_idx >= 0:
                                self.current_clean_preview_layer.changeAttributeValue(feat.id(), reasons_idx, reasons_val)
                    self.current_clean_preview_layer.commitChanges()

            counts = cleaning_result.reason_counts
            self.flow_delay_count_lbl.setText(f"{counts.get('flow_delay', 0):,}")
            self.moisture_delay_count_lbl.setText(f"{counts.get('moisture_delay', 0):,}")
            self.pass_start_count_lbl.setText(f"{counts.get('pass_start', 0):,}")
            self.pass_end_count_lbl.setText(f"{counts.get('pass_end', 0):,}")
            self.max_speed_count_lbl.setText(f"{counts.get('speed_above_max', 0):,}")
            self.min_speed_count_lbl.setText(f"{counts.get('speed_below_min', 0):,}")
            self.min_swath_count_lbl.setText(f"{counts.get('swath_below_min', 0):,}")
            self.max_yield_count_lbl.setText(f"{counts.get('yield_above_max', 0):,}")
            self.min_yield_count_lbl.setText(f"{counts.get('yield_below_min', 0):,}")
            self.outlier_count_lbl.setText(f"{counts.get('local_yield_outlier', 0):,}")
            self.overlap_count_lbl.setText(f"{counts.get('harvest_overlap', 0):,}")
            self.header_count_lbl.setText(f"{counts.get('header_disengaged', 0):,}")
            self.manual_deletes_count_lbl.setText(f"{len(self.manual_excluded_ids):,}")

            tw = float(self.test_weight_spin.value() if hasattr(self, "test_weight_spin") else 56.0)
            is_metric = self.current_unit_profile == "metric"
            yield_unit = "kg/ha" if is_metric else "bu/ac"

            raw_vals = []
            clean_vals = []
            for i, obs in enumerate(self.current_observations):
                y = None
                for k in ("yield_dry_mass_area", "yield_wet_mass_area", "dry_yield_mass_area", "yield", "dry_yield"):
                    val = obs.get(k)
                    if val is not None:
                        try:
                            num = float(val)
                            if math.isfinite(num) and num > 0:
                                y = num
                                break
                        except (TypeError, ValueError):
                            pass
                if y is not None:
                    y_val = kg_per_hectare_to_bushels_per_acre(y, tw) if not is_metric else y
                    raw_vals.append(y_val)
                    if cleaning_result.observation_updates[i].get("clean_status") == "accepted":
                        clean_vals.append(y_val)

            import statistics
            def get_stats(vals):
                if not vals:
                    return {"mean": 0.0, "std": 0.0, "cv": 0.0, "n": 0, "min": 0.0, "max": 0.0}
                n_v = len(vals)
                mean_v = statistics.mean(vals)
                std_v = statistics.stdev(vals) if n_v > 1 else 0.0
                cv_v = (std_v / mean_v * 100.0) if mean_v > 0 else 0.0
                return {"mean": mean_v, "std": std_v, "cv": cv_v, "n": n_v, "min": min(vals), "max": max(vals)}

            raw_s = get_stats(raw_vals)
            clean_s = get_stats(clean_vals)
            diff_mean = clean_s["mean"] - raw_s["mean"]
            diff_std = clean_s["std"] - raw_s["std"]
            diff_cv = clean_s["cv"] - raw_s["cv"]
            exc_pts = raw_s["n"] - clean_s["n"]
            exc_pct = (exc_pts / raw_s["n"] * 100.0) if raw_s["n"] > 0 else 0.0

            stats_html = f"""
            <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 13px;">
              <tr style="background-color: #f1f5f9; text-align: left;">
                <th>Metric</th><th>Cleaned Dataset</th><th>Raw / Source Data</th><th>Difference / Excluded</th>
              </tr>
              <tr>
                <td><b>Mean Yield</b></td>
                <td><b style="color: #2e7d32;">{clean_s['mean']:.2f} {yield_unit}</b></td>
                <td>{raw_s['mean']:.2f} {yield_unit}</td>
                <td>{diff_mean:+.2f} {yield_unit}</td>
              </tr>
              <tr>
                <td><b>Std Dev (STD)</b></td>
                <td>{clean_s['std']:.2f} {yield_unit}</td>
                <td>{raw_s['std']:.2f} {yield_unit}</td>
                <td>{diff_std:+.2f} {yield_unit}</td>
              </tr>
              <tr>
                <td><b>Coeff of Variation (CV)</b></td>
                <td>{clean_s['cv']:.1f} %</td>
                <td>{raw_s['cv']:.1f} %</td>
                <td>{diff_cv:+.1f} %</td>
              </tr>
              <tr>
                <td><b>Observations (N)</b></td>
                <td><b style="color: #2e7d32;">{clean_s['n']:,}</b></td>
                <td>{raw_s['n']:,}</td>
                <td><b style="color: #d32f2f;">{exc_pts:,} ({exc_pct:.1f}%)</b></td>
              </tr>
              <tr>
                <td><b>Yield Range</b></td>
                <td>{clean_s['min']:.1f} - {clean_s['max']:.1f} {yield_unit}</td>
                <td>{raw_s['min']:.1f} - {raw_s['max']:.1f} {yield_unit}</td>
                <td>-</td>
              </tr>
            </table>
            """
            self.clean_status.setHtml(stats_html)
            self._apply_clean_preview_styling()
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, f"Could not refresh clean view: {exc}")

    def _run_cleaning_pipeline(self):
        if hasattr(self, "execute_button"):
            self.execute_button.setEnabled(False)
            self.execute_button.setText("Executing Cleaning Pipeline... Please wait...")
        if hasattr(self, "clean_progress"):
            self.clean_progress.setVisible(True)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            if not self.current_prepared_layer or not self.current_prepared_layer.isValid():
                raise ValueError("No valid prepared dataset available. Complete step 3 first.")
            if not self.current_run_folder or not self.current_run_folder.exists():
                raise ValueError("The run folder does not exist.")

            obs_list = []
            for idx, feat in enumerate(self.current_prepared_layer.getFeatures()):
                obs = {"source_index": idx}
                fid = feat.id()
                if fid in self.manual_excluded_ids:
                    obs["manual_action"] = "exclude"
                elif fid in self.manual_restored_ids:
                    obs["manual_action"] = "restore"
                geom = feat.geometry()
                if geom and not geom.isEmpty():
                    pt = geom.asPoint()
                    obs["x"] = pt.x()
                    obs["y"] = pt.y()
                for f in self.current_prepared_layer.fields():
                    val = feat[f.name()]
                    if val is None or val == "" or str(val) == "NULL":
                        obs[f.name()] = None
                    elif hasattr(val, "isNull") and val.isNull():
                        obs[f.name()] = None
                    elif hasattr(val, "toString"):
                        obs[f.name()] = str(val.toString())
                    elif hasattr(val, "isoformat"):
                        obs[f.name()] = str(val.isoformat())
                    else:
                        obs[f.name()] = val
                obs_list.append(obs)

            if not obs_list:
                raise ValueError("The prepared layer contains zero observations.")

            has_passes = any(obs.get("pass_id") for obs in obs_list[:20])
            if not has_passes:
                pass_res = reconstruct_passes(obs_list)
                for i, upd in enumerate(pass_res.observation_updates):
                    if upd:
                        obs_list[i].update(upd)

            recipe = self._collect_recipe_from_ui()
            cleaning_result = run_cleaning_filters(obs_list, recipe)
            self.current_cleaning_result = cleaning_result
            self.current_observations = obs_list

            analysis_crs = (
                self.current_prepared_layer.crs().authid()
                if self.current_prepared_layer.crs().isValid()
                else "EPSG:4326"
            )
            field_name = self.field_name.text().strip() or self._suggested_field_name()

            bnd_rings = []
            bnd_layer = None
            if hasattr(self, "current_preview_boundary_layer") and self.current_preview_boundary_layer and self.current_preview_boundary_layer.isValid() and self.current_preview_boundary_layer.featureCount() > 0:
                bnd_layer = self.current_preview_boundary_layer
            elif hasattr(self, "current_prepared_boundary_layer") and self.current_prepared_boundary_layer and self.current_prepared_boundary_layer.isValid() and self.current_prepared_boundary_layer.featureCount() > 0:
                bnd_layer = self.current_prepared_boundary_layer
            elif self.current_run_paths and "geopackage" in self.current_run_paths:
                gpkg_bnd = QgsVectorLayer(f"{self.current_run_paths['geopackage']}|layername=field_boundary", "Field Boundary", "ogr")
                if gpkg_bnd.isValid() and gpkg_bnd.featureCount() > 0:
                    bnd_layer = gpkg_bnd

            if bnd_layer is not None and bnd_layer.isValid() and bnd_layer.featureCount() > 0:
                try:
                    wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                    src_crs = bnd_layer.crs() if (bnd_layer.crs() and bnd_layer.crs().isValid()) else QgsCoordinateReferenceSystem(analysis_crs)
                    need_xform = src_crs.isValid() and src_crs.authid().upper() != "EPSG:4326"
                    transform_context = QgsProject.instance().transformContext()
                    xform = QgsCoordinateTransform(src_crs, wgs84_crs, transform_context) if need_xform else None

                    for feat in bnd_layer.getFeatures():
                        geom = feat.geometry()
                        if not geom or geom.isEmpty():
                            continue
                        geom_wgs = QgsGeometry(geom)
                        if xform is not None:
                            try:
                                geom_wgs.transform(xform)
                            except Exception:
                                pass
                        if geom_wgs.isMultipart():
                            polys = geom_wgs.asMultiPolygon()
                        else:
                            polys = [geom_wgs.asPolygon()]

                        for poly in polys:
                            for ring_pts in poly:
                                if ring_pts:
                                    ring = []
                                    for pt in ring_pts:
                                        vx, vy = float(pt.x()), float(pt.y())
                                        if abs(vx) <= 180.0 and abs(vy) <= 90.0:
                                            ring.append((round(vy, 6), round(vx, 6)))
                                        else:
                                            lat_c, lon_c = _utm_to_latlon(vx, vy)
                                            ring.append((round(lat_c, 6), round(lon_c, 6)))
                                    if len(ring) >= 3:
                                        bnd_rings.append(ring)
                except Exception:
                    pass

            # Robust fallback: If boundary was not derived or missing, compute field boundary envelope from observations
            if not bnd_rings:
                try:
                    wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                    src_crs = (
                        self.current_prepared_layer.crs()
                        if (hasattr(self, "current_prepared_layer") and self.current_prepared_layer and self.current_prepared_layer.crs().isValid())
                        else QgsCoordinateReferenceSystem(analysis_crs)
                    )
                    need_xform = src_crs.isValid() and src_crs.authid() != "EPSG:4326"
                    xform = QgsCoordinateTransform(src_crs, wgs84_crs, QgsProject.instance()) if need_xform else None

                    pts = []
                    for obs in obs_list:
                        px, py = obs.get("x"), obs.get("y")
                        if px is not None and py is not None:
                            try:
                                pt = QgsPointXY(float(px), float(py))
                                if xform is not None:
                                    pt = xform.transform(pt)
                                pts.append(pt)
                            except Exception:
                                pass

                    if pts:
                        hull = QgsGeometry.fromMultiPointXY(pts).convexHull().buffer(0.00025, 6)
                        if hull and not hull.isEmpty():
                            poly = hull.asPolygon()
                            if poly and poly[0]:
                                bnd_rings = [[(round(float(p.y()), 6), round(float(p.x()), 6)) for p in poly[0]]]
                except Exception:
                    pass

            grid_size = float(self.grid_size_spin.value() if hasattr(self, "grid_size_spin") else 30.0)

            gpkg = (
                Path(self.current_run_paths["geopackage"])
                if (self.current_run_paths and "geopackage" in self.current_run_paths)
                else (self.current_run_folder / f"{self.current_run_folder.name}_yield_data.gpkg")
            )

            summary = write_run_package(
                output_dir=self.current_run_folder,
                run_name=self.current_run_folder.name,
                field_name=field_name,
                crop_code=self.current_crop_code,
                unit_profile=self.current_unit_profile,
                observations=obs_list,
                cleaning_result=cleaning_result,
                recipe=recipe,
                analysis_crs=analysis_crs,
                source_crs=self.crs_text.text().strip() or "Unknown",
                grid_size_ft=grid_size,
                boundary_coords=bnd_rings,
            )
            self.current_review_html_path = Path(summary.review_html_path)

            # Build in-modal clean map preview layer with updated statuses and attributes
            preview_layer = QgsVectorLayer(
                f"Point?crs={analysis_crs}",
                f"{field_name} - Observations",
                "memory",
            )
            pr = preview_layer.dataProvider()
            fields = QgsFields(self.current_prepared_layer.fields())
            if fields.indexFromName("clean_status") == -1:
                fields.append(QgsField("clean_status", qgis_field_type("string")))
            if fields.indexFromName("filter_reasons") == -1:
                fields.append(QgsField("filter_reasons", qgis_field_type("string")))
            if fields.indexFromName("source_index") == -1:
                fields.append(QgsField("source_index", qgis_field_type("int")))

            pr.addAttributes(list(fields))
            preview_layer.updateFields()

            preview_feats = []
            status_idx = fields.indexFromName("clean_status")
            reasons_idx = fields.indexFromName("filter_reasons")
            src_idx = fields.indexFromName("source_index")

            for i, orig_feat in enumerate(self.current_prepared_layer.getFeatures()):
                upd = cleaning_result.observation_updates[i] if i < len(cleaning_result.observation_updates) else {}
                feat = QgsFeature(preview_layer.fields())
                feat.setGeometry(orig_feat.geometry())
                for fld in self.current_prepared_layer.fields():
                    f_idx = fields.indexFromName(fld.name())
                    if f_idx != -1:
                        feat.setAttribute(f_idx, orig_feat[fld.name()])
                feat.setAttribute(status_idx, str(upd.get("clean_status", "accepted")))
                feat.setAttribute(reasons_idx, str(upd.get("filter_reasons", "")))
                feat.setAttribute(src_idx, i)
                preview_feats.append(feat)

            pr.addFeatures(preview_feats)
            preview_layer.updateExtents()
            self.current_clean_preview_layer = preview_layer

            if self.clean_map_canvas is not None and self.current_clean_preview_layer.isValid():
                self.clean_map_canvas.setLayers([self.current_clean_preview_layer])
                self.clean_map_canvas.setExtent(self.current_clean_preview_layer.extent())
                self.clean_map_canvas.refresh()
                self._update_clean_scale()
                self._apply_clean_preview_styling()
                self._toggle_clean_selection_tool(True)

            # Update live individual filter deleted counts
            counts = cleaning_result.reason_counts
            self.flow_delay_count_lbl.setText(f"{counts.get('flow_delay', 0):,}")
            self.moisture_delay_count_lbl.setText(f"{counts.get('moisture_delay', 0):,}")
            self.pass_start_count_lbl.setText(f"{counts.get('pass_start', 0):,}")
            self.pass_end_count_lbl.setText(f"{counts.get('pass_end', 0):,}")
            self.max_speed_count_lbl.setText(f"{counts.get('speed_above_max', 0):,}")
            self.min_speed_count_lbl.setText(f"{counts.get('speed_below_min', 0):,}")
            self.min_swath_count_lbl.setText(f"{counts.get('swath_below_min', 0):,}")
            self.max_yield_count_lbl.setText(f"{counts.get('yield_above_max', 0):,}")
            self.min_yield_count_lbl.setText(f"{counts.get('yield_below_min', 0):,}")
            self.outlier_count_lbl.setText(f"{counts.get('local_yield_outlier', 0):,}")
            self.overlap_count_lbl.setText(f"{counts.get('harvest_overlap', 0):,}")
            self.header_count_lbl.setText(f"{counts.get('header_disengaged', 0):,}")
            self.manual_deletes_count_lbl.setText(f"{len(self.manual_excluded_ids):,}")

            # Calculate raw and clean statistics
            tw = float(self.test_weight_spin.value() if hasattr(self, "test_weight_spin") else 56.0)
            is_metric = self.current_unit_profile == "metric"
            yield_unit = "kg/ha" if is_metric else "bu/ac"

            raw_vals = []
            clean_vals = []
            for i, obs in enumerate(obs_list):
                y = None
                for k in ("yield_dry_mass_area", "yield_wet_mass_area", "dry_yield_mass_area", "yield", "dry_yield"):
                    val = obs.get(k)
                    if val is not None:
                        try:
                            num = float(val)
                            if math.isfinite(num) and num > 0:
                                y = num
                                break
                        except (TypeError, ValueError):
                            pass
                if y is not None:
                    y_val = kg_per_hectare_to_bushels_per_acre(y, tw) if not is_metric else y
                    raw_vals.append(y_val)
                    if cleaning_result.observation_updates[i].get("clean_status") == "accepted":
                        clean_vals.append(y_val)

            import statistics
            def get_stats(vals):
                if not vals:
                    return {"mean": 0.0, "std": 0.0, "cv": 0.0, "n": 0, "min": 0.0, "max": 0.0}
                n_v = len(vals)
                mean_v = statistics.mean(vals)
                std_v = statistics.stdev(vals) if n_v > 1 else 0.0
                cv_v = (std_v / mean_v * 100.0) if mean_v > 0 else 0.0
                return {"mean": mean_v, "std": std_v, "cv": cv_v, "n": n_v, "min": min(vals), "max": max(vals)}

            raw_s = get_stats(raw_vals)
            clean_s = get_stats(clean_vals)
            diff_mean = clean_s["mean"] - raw_s["mean"]
            diff_std = clean_s["std"] - raw_s["std"]
            diff_cv = clean_s["cv"] - raw_s["cv"]
            exc_pts = raw_s["n"] - clean_s["n"]
            exc_pct = (exc_pts / raw_s["n"] * 100.0) if raw_s["n"] > 0 else 0.0

            stats_html = f"""
            <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 13px;">
              <tr style="background-color: #f1f5f9; text-align: left;">
                <th>Metric</th><th>Cleaned Dataset</th><th>Raw / Source Data</th><th>Difference / Excluded</th>
              </tr>
              <tr>
                <td><b>Mean Yield</b></td>
                <td><b style="color: #2e7d32;">{clean_s['mean']:.2f} {yield_unit}</b></td>
                <td>{raw_s['mean']:.2f} {yield_unit}</td>
                <td>{diff_mean:+.2f} {yield_unit}</td>
              </tr>
              <tr>
                <td><b>Std Dev (STD)</b></td>
                <td>{clean_s['std']:.2f} {yield_unit}</td>
                <td>{raw_s['std']:.2f} {yield_unit}</td>
                <td>{diff_std:+.2f} {yield_unit}</td>
              </tr>
              <tr>
                <td><b>Coeff of Variation (CV)</b></td>
                <td>{clean_s['cv']:.1f} %</td>
                <td>{raw_s['cv']:.1f} %</td>
                <td>{diff_cv:+.1f} %</td>
              </tr>
              <tr>
                <td><b>Observations (N)</b></td>
                <td><b style="color: #2e7d32;">{clean_s['n']:,}</b></td>
                <td>{raw_s['n']:,}</td>
                <td><b style="color: #d32f2f;">{exc_pts:,} ({exc_pct:.1f}%)</b></td>
              </tr>
              <tr>
                <td><b>Yield Range</b></td>
                <td>{clean_s['min']:.1f} - {clean_s['max']:.1f} {yield_unit}</td>
                <td>{raw_s['min']:.1f} - {raw_s['max']:.1f} {yield_unit}</td>
                <td>-</td>
              </tr>
            </table>
            """

            self.clean_status.setHtml(stats_html)
            self.execute_button.setEnabled(True)
            self._style_button_completed(self.execute_button, "✓ Cleaning Completed (Click to Re-run)")

            self.open_review_button.setEnabled(True)
            self.open_log_button.setEnabled(True)
            self.open_folder_button.setEnabled(True)
            self.export_adapt_button.setEnabled(True)

        except Exception as exc:
            if hasattr(self, "execute_button"):
                self.execute_button.setEnabled(True)
                self._style_button_action_needed(self.execute_button, "Execute Cleaning Pipeline / Apply Filters")
            QMessageBox.warning(self, PLUGIN_NAME, f"Cleaning failed: {exc}")
        finally:
            if hasattr(self, "clean_progress"):
                self.clean_progress.setVisible(False)
            QApplication.restoreOverrideCursor()

    def _open_html_review(self):
        if self.current_review_html_path and self.current_review_html_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_review_html_path.resolve())))
        else:
            QMessageBox.warning(self, PLUGIN_NAME, "HTML review report file not found.")

    def _open_run_log(self):
        if self.current_run_folder and self.current_run_folder.exists():
            log_path = self.current_run_folder / f"{self.current_run_folder.name}_run_log.txt"
            if log_path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path.resolve())))
                return
        QMessageBox.warning(self, PLUGIN_NAME, "Run log file not found.")

    def _open_run_folder(self):
        if self.current_run_folder and self.current_run_folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_run_folder.resolve())))
        else:
            QMessageBox.warning(self, PLUGIN_NAME, "Run folder not found.")

    def _export_adapt_package(self):
        if not self.current_observations:
            QMessageBox.warning(self, PLUGIN_NAME, "No cleaned observations available to export.")
            return
        destination = QFileDialog.getExistingDirectory(
            self,
            "Select destination directory for ADAPT Standard Package",
            str(self.current_run_folder or ""),
        )
        if not destination:
            return
        try:
            field_name = self.field_name.text().strip() or "Field"
            analysis_crs = (
                self.current_prepared_layer.crs().authid()
                if (self.current_prepared_layer and self.current_prepared_layer.crs().isValid())
                else "EPSG:4326"
            )
            pkg = export_adapt_standard_package(
                target_dir=Path(destination),
                field_name=field_name,
                crop_code=self.current_crop_code,
                observations=self.current_observations,
                cleaning_result=self.current_cleaning_result,
                analysis_crs=analysis_crs,
            )
            QMessageBox.information(
                self,
                PLUGIN_NAME,
                f"ADAPT Standard package exported successfully to:\n{pkg.package_dir}",
            )
        except Exception as exc:
            QMessageBox.warning(self, PLUGIN_NAME, f"ADAPT export failed: {exc}")

    def _reset_tool(self):
        """Reset all inputs, preview canvases, prepared datasets, mappings, and results to start over fresh."""
        # 1. Reset all state attributes
        self.current_columns = []
        self.current_suggestions = []
        self.current_crs_authid = None
        self.current_run_folder = None
        self.current_run_paths = None
        self.current_prepared_layer = None
        self.current_prepared_boundary_layer = None
        self.current_preview_boundary_layer = None
        self.original_boundary_geometries = {}
        self.current_cleaning_result = None
        self.current_cleaned_layer = None
        self.current_observations = []
        self.current_obs_list = []
        self.current_sample_values = {}
        self.last_run_package_path = None
        self.last_run_log_path = None
        self.current_source_crs = None
        self.current_detected_crop = None
        self.manual_excluded_ids = set()
        self.manual_restored_ids = set()

        # 2. Reset Tab 1 (Source & CRS)
        if hasattr(self, "loaded_radio"):
            self.loaded_radio.setChecked(True)
        if hasattr(self, "file_radio"):
            self.file_radio.setChecked(False)
        if hasattr(self, "file_path"):
            self.file_path.clear()
        if hasattr(self, "crs_text"):
            self.crs_text.clear()
        if hasattr(self, "crop_combo") and self.crop_combo.count() > 0:
            self.crop_combo.setCurrentIndex(0)
        if hasattr(self, "units_combo") and self.units_combo.count() > 0:
            self.units_combo.setCurrentIndex(0)
        if hasattr(self, "test_weight_spin"):
            self.test_weight_spin.setValue(56.0)
        if hasattr(self, "standard_moisture_spin"):
            self.standard_moisture_spin.setValue(15.5)
        if hasattr(self, "results"):
            self.results.setHtml(
                "<h3>No input inspected</h3>"
                "<p>Column suggestions and CRS evidence will appear here.</p>"
            )
        if hasattr(self, "inspect_progress"):
            self.inspect_progress.setVisible(False)
        if hasattr(self, "inspect_button"):
            self._style_button_action_needed(self.inspect_button, "Inspect input")
            self.inspect_button.setEnabled(True)
        if hasattr(self, "input_continue_button"):
            self._style_button_action_needed(self.input_continue_button, "Continue to Field Boundary")
            self.input_continue_button.setEnabled(False)

        # Reset mapping table
        if hasattr(self, "mapping_table"):
            for row in range(self.mapping_table.rowCount()):
                col_combo = self.mapping_table.cellWidget(row, 1)
                if isinstance(col_combo, QComboBox):
                    col_combo.clear()
                unit_combo = self.mapping_table.cellWidget(row, 2)
                if isinstance(unit_combo, QComboBox) and unit_combo.count() > 0:
                    unit_combo.setCurrentIndex(0)
                val_item = self.mapping_table.item(row, 3)
                if val_item:
                    val_item.setText("—")
                ev_item = self.mapping_table.item(row, 4)
                if ev_item:
                    ev_item.setText("Not inspected")

        self._refresh_layers()

        # 3. Reset Tab 2 (Boundary)
        if hasattr(self, "boundary_mode") and self.boundary_mode.count() > 0:
            self.boundary_mode.setCurrentIndex(0)
        if hasattr(self, "boundary_file_path"):
            self.boundary_file_path.clear()
        if hasattr(self, "use_inspected_source"):
            self.use_inspected_source.setChecked(True)
        if hasattr(self, "boundary_point_file"):
            self.boundary_point_file.clear()
        if hasattr(self, "default_width"):
            self.default_width.setValue(30.0)
        if hasattr(self, "gap_closing"):
            self.gap_closing.setValue(3.28)
        if hasattr(self, "concavity"):
            self.concavity.setValue(0.3)
        if hasattr(self, "import_create_boundary_button"):
            self._style_button_action_needed(self.import_create_boundary_button, "Import / Create Boundary")
            self.import_create_boundary_button.setEnabled(True)
        if hasattr(self, "boundary_map_canvas") and self.boundary_map_canvas:
            self.boundary_map_canvas.setLayers([])
            self.boundary_map_canvas.refresh()
        if hasattr(self, "bnd_vertex_count_label"):
            self.bnd_vertex_count_label.setText("")
        if hasattr(self, "edit_vertices_btn"):
            self.edit_vertices_btn.setChecked(False)
        if hasattr(self, "vertex_guide_label"):
            self.vertex_guide_label.setVisible(False)
        if hasattr(self, "boundary_continue_button"):
            self._style_button_action_needed(self.boundary_continue_button, "Continue to Prepare Dataset")
            self.boundary_continue_button.setEnabled(False)

        # 4. Reset Tab 3 (Prepare Dataset)
        if hasattr(self, "field_name"):
            self.field_name.clear()
        if hasattr(self, "output_crs"):
            self.output_crs.clear()
        if hasattr(self, "run_name_preview"):
            self.run_name_preview.setText("")
        if hasattr(self, "prepare_progress"):
            self.prepare_progress.setVisible(False)
            self.prepare_progress.setValue(0)
        if hasattr(self, "create_dataset_button"):
            self._style_button_action_needed(self.create_dataset_button, "Create prepared yield dataset")
            self.create_dataset_button.setEnabled(True)
        if hasattr(self, "prepare_continue_button"):
            self._style_button_action_needed(self.prepare_continue_button, "Continue to Clean & Review")
            self.prepare_continue_button.setEnabled(False)
        if hasattr(self, "prepare_map_canvas") and self.prepare_map_canvas:
            self.prepare_map_canvas.setLayers([])
            self.prepare_map_canvas.refresh()
        if hasattr(self, "prepare_scale_label"):
            self.prepare_scale_label.setText("📏 <b>Scale:</b> 1:— &bull; <b>Display Units:</b> — &bull; <b>CRS:</b> —")
        if hasattr(self, "prepare_attribute_combo") and self.prepare_attribute_combo.count() > 0:
            self.prepare_attribute_combo.setCurrentIndex(0)
        if hasattr(self, "prepare_ramp_combo") and self.prepare_ramp_combo.count() > 0:
            self.prepare_ramp_combo.setCurrentIndex(0)

        # 5. Reset Tab 4 (Clean & Review)
        if hasattr(self, "execute_button"):
            self._style_button_action_needed(self.execute_button, "Execute Cleaning Pipeline")
            self.execute_button.setEnabled(True)
        if hasattr(self, "cleaning_progress"):
            self.cleaning_progress.setVisible(False)
            self.cleaning_progress.setValue(0)
        if hasattr(self, "filter_table"):
            self.filter_table.setRowCount(0)
        if hasattr(self, "clean_map_canvas") and self.clean_map_canvas:
            self.clean_map_canvas.setLayers([])
            self.clean_map_canvas.refresh()
        if hasattr(self, "clean_map_group"):
            self.clean_map_group.setVisible(False)
        if hasattr(self, "clean_scale_label"):
            self.clean_scale_label.setText("📏 <b>Scale:</b> 1:— &bull; <b>Display Units:</b> — &bull; <b>CRS:</b> —")
        if hasattr(self, "open_review_button"):
            self.open_review_button.setEnabled(False)
        if hasattr(self, "open_log_button"):
            self.open_log_button.setEnabled(False)
        if hasattr(self, "open_folder_button"):
            self.open_folder_button.setEnabled(False)
        if hasattr(self, "export_adapt_button"):
            self.export_adapt_button.setEnabled(False)

        # Reset recipe defaults
        self._reset_recipe_defaults()

        # 6. Switch back to first tab
        self.tabs.setCurrentIndex(0)
        self._update_help(0)


