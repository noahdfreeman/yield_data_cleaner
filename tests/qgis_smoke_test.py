# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless installed-runtime smoke for the 0.1.0 plugin foundation."""

from __future__ import annotations

import json
import gc
import os
import shutil
import sys
import tempfile
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsVectorLayer,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def trace(message: str) -> None:
    print(f"YDC_SMOKE_STAGE {message}", flush=True)


def main() -> None:
    trace("start")
    prefix = os.environ.get("QGIS_PREFIX_PATH")
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
        plugins_path = Path(prefix) / "python" / "plugins"
        if plugins_path.is_dir() and str(plugins_path) not in sys.path:
            sys.path.insert(0, str(plugins_path))
    app = QgsApplication([], False)
    app.initQgis()
    trace("qgis-initialized")
    provider = None
    cleanup_directory = None
    try:
        from processing.core.Processing import Processing
        import processing

        Processing.initialize()
        trace("processing-initialized")
        from yield_data_cleaner.algorithms.inspect_yield_columns import InspectYieldDataAlgorithm

        trace("algorithm-imported")
        from yield_data_cleaner.provider import YieldDataCleanerProvider

        trace("provider-imported")
        from yield_data_cleaner.ui.inspection_dialog import YieldInputInspectionDialog

        trace("dialog-imported")

        trace("algorithm-probe-constructing")
        probe = InspectYieldDataAlgorithm()
        trace("algorithm-probe-constructed")
        probe.initAlgorithm()
        trace("algorithm-probe-initialized")

        trace("provider-constructing")
        provider = YieldDataCleanerProvider()
        trace("provider-constructed")
        QgsApplication.processingRegistry().addProvider(provider)
        trace("provider-added")
        algorithm_ids = {algorithm.id() for algorithm in provider.algorithms()}
        if "yield_data_cleaner:inspect_yield_data" not in algorithm_ids:
            raise AssertionError(
                f"Processing algorithm was not registered: {sorted(algorithm_ids)}"
            )
        if "yield_data_cleaner:create_canonical_audit" not in algorithm_ids:
            raise AssertionError(
                f"Canonical audit algorithm was not registered: {sorted(algorithm_ids)}"
            )
        if "yield_data_cleaner:prepare_field_boundary" not in algorithm_ids:
            raise AssertionError(f"Boundary algorithm was not registered: {sorted(algorithm_ids)}")
        if "yield_data_cleaner:classify_by_boundary" not in algorithm_ids:
            raise AssertionError(
                f"Boundary classification was not registered: {sorted(algorithm_ids)}"
            )

        dialog = YieldInputInspectionDialog(None)
        trace("dialog-created")
        if "Yield Data Cleaner 0.1.0" not in dialog.windowTitle():
            raise AssertionError("Guided dialog title/version is incorrect")
        expected_tabs = (
            "1. Input & Mapping",
            "2. Canonical Audit",
            "3. Field Boundary",
        )
        actual_tabs = tuple(dialog.tabs.tabText(index) for index in range(dialog.tabs.count()))
        if actual_tabs != expected_tabs:
            raise AssertionError(f"Guided workflow tabs are incorrect: {actual_tabs}")
        if dialog.findChild(type(dialog.help_panel), "yieldDataCleanerHelpPanel") is None:
            raise AssertionError("Guided workflow help panel is missing")
        for index, expected_help in enumerate(("Input & Mapping", "Canonical Audit", "Field Boundary")):
            dialog.tabs.setCurrentIndex(index)
            if expected_help not in dialog.help_panel.toPlainText():
                raise AssertionError(f"Help content did not update for {expected_help}")
        if dialog.findChild(type(dialog.tabs), "yieldDataCleanerWorkflowTabs") is None:
            raise AssertionError("Guided workflow tab widget is missing")
        dialog.close()
        dialog.deleteLater()

        with tempfile.TemporaryDirectory(
            prefix="yield_cleaner_smoke_", ignore_cleanup_errors=True
        ) as directory:
            cleanup_directory = directory
            directory_path = Path(directory)
            input_path = directory_path / "yield.csv"
            report_path = directory_path / "inspection.json"
            input_path.write_text(
                "Longitude,Latitude,Dry Yield (bu/ac),Moisture %,Ground Speed,Swath Width\n"
                "-86.1000,40.2000,205.5,16.2,4.8,30\n",
                encoding="utf-8",
            )
            algorithm = InspectYieldDataAlgorithm()
            algorithm.initAlgorithm()
            trace("algorithm-running")
            result = algorithm.processAlgorithm(
                {
                    algorithm.INPUT_FILE: str(input_path),
                    algorithm.REPORT: str(report_path),
                },
                QgsProcessingContext(),
                QgsProcessingFeedback(),
            )
            if Path(result[algorithm.REPORT]) != report_path or not report_path.is_file():
                raise AssertionError("Inspection algorithm did not create its report")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            mapping = {
                item["canonical_field"]: item["source_column"]
                for item in report["mapping_suggestions"]
            }
            if (
                mapping.get("x") != "Longitude"
                or mapping.get("yield_dry_mass_area") != "Dry Yield (bu/ac)"
            ):
                raise AssertionError(f"Unexpected mapping report: {mapping}")
            if report.get("input_modified") is not False:
                raise AssertionError("Inspection report does not assert read-only behavior")

            audit_path = directory_path / "canonical_audit.gpkg"
            audit_sink = YieldInputInspectionDialog._gpkg_sink_uri(
                audit_path, "canonical_observations"
            )
            mapping_path = directory_path / "applied_mapping.json"
            manifest_path = directory_path / "run_manifest.json"
            audit_result = processing.run(
                "yield_data_cleaner:create_canonical_audit",
                {
                    "INPUT_FILE": str(input_path),
                    "CROP": 0,
                    "UNIT_PROFILE": 0,
                    "MAPPING_REPORT": str(mapping_path),
                    "RUN_MANIFEST": str(manifest_path),
                    "OUTPUT": audit_sink,
                },
            )
            audit_layer = QgsVectorLayer(audit_result["OUTPUT"], "canonical_audit", "ogr")
            if not audit_layer.isValid() or audit_layer.featureCount() != 1:
                raise AssertionError("Canonical audit GeoPackage was not created")
            if audit_layer.crs().authid() != "EPSG:32616":
                raise AssertionError(
                    f"Unexpected automatic analysis CRS: {audit_layer.crs().authid()}"
                )
            audit_feature = next(audit_layer.getFeatures())
            if abs(float(audit_feature["yield_dry_mass_area"]) - 12898.755) > 0.01:
                raise AssertionError("Canonical corn yield conversion is incorrect")
            if audit_feature["clean_status"] != "unavailable":
                raise AssertionError("Canonical audit incorrectly claims a cleaning decision")
            mapping_report = json.loads(mapping_path.read_text(encoding="utf-8"))
            if mapping_report["analysis_crs"] != "EPSG:32616":
                raise AssertionError("Applied mapping report does not record analysis CRS")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["cleaning_applied"] is not False:
                raise AssertionError("Preparation manifest incorrectly claims cleaning")
            if not manifest["source"]["signature"]["sha256"]:
                raise AssertionError("Preparation manifest has no input signature")

            loaded_layer = QgsVectorLayer(
                "Point?crs=EPSG:4326&field=Yield:double&field=Moisture:double",
                "loaded_yield",
                "memory",
            )
            loaded_feature = QgsFeature(loaded_layer.fields())
            loaded_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-86.1, 40.2)))
            loaded_feature["Yield"] = 210.0
            loaded_feature["Moisture"] = 15.8
            loaded_layer.dataProvider().addFeature(loaded_feature)
            loaded_result = processing.run(
                "yield_data_cleaner:create_canonical_audit",
                {
                    "SOURCE": loaded_layer,
                    "CROP": 0,
                    "UNIT_PROFILE": 0,
                    "MAPPING_REPORT": str(directory_path / "loaded_mapping.json"),
                    "RUN_MANIFEST": str(directory_path / "loaded_manifest.json"),
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
            loaded_output = loaded_result["OUTPUT"]
            if not loaded_output.isValid() or loaded_output.featureCount() != 1:
                raise AssertionError("Loaded QGIS layer was not canonicalized")
            if loaded_output.crs().authid() != "EPSG:32616":
                raise AssertionError("Loaded layer was not transformed to local UTM")

            boundary_points = QgsVectorLayer(
                "Point?crs=EPSG:4326&field=swath_width_m:double",
                "boundary_points",
                "memory",
            )
            boundary_features = []
            for longitude, latitude in (
                (-86.1000, 40.2000),
                (-86.09995, 40.2000),
                (-86.09995, 40.20005),
                (-86.1000, 40.20005),
            ):
                feature = QgsFeature(boundary_points.fields())
                feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(longitude, latitude)))
                feature["swath_width_m"] = 9.144
                boundary_features.append(feature)
            boundary_points.dataProvider().addFeatures(boundary_features)
            boundary_result = processing.run(
                "yield_data_cleaner:prepare_field_boundary",
                {
                    "MODE": 1,
                    "YIELD_POINTS": boundary_points,
                    "WIDTH_FIELD": "swath_width_m",
                    "DEFAULT_WIDTH": 0.0,
                    "PROVENANCE": str(directory_path / "boundary_provenance.json"),
                    "OUTPUT": YieldInputInspectionDialog._gpkg_sink_uri(
                        audit_path, "field_boundary"
                    ),
                },
            )
            boundary_output = QgsVectorLayer(
                boundary_result["OUTPUT"], "field_boundary", "ogr"
            )
            if not boundary_output.isValid() or boundary_output.featureCount() != 1:
                raise AssertionError("Operational boundary was not derived")
            boundary_feature = next(boundary_output.getFeatures())
            if boundary_feature["requires_review"] is not True:
                raise AssertionError("Derived boundary does not require review")
            boundary_provenance = json.loads(
                (directory_path / "boundary_provenance.json").read_text(encoding="utf-8")
            )
            if boundary_provenance["method"] != "point_footprint_union":
                raise AssertionError("Boundary derivation did not use available swath widths")
            if boundary_provenance["legal_boundary"] is not False:
                raise AssertionError("Derived extent was incorrectly labeled as a legal boundary")
            existing_result = processing.run(
                "yield_data_cleaner:prepare_field_boundary",
                {
                    "MODE": 0,
                    "EXISTING_BOUNDARY": boundary_output,
                    "PROVENANCE": str(directory_path / "existing_boundary.json"),
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
            existing_output = existing_result["OUTPUT"]
            existing_feature = next(existing_output.getFeatures())
            if existing_feature["method"] != "existing_polygon":
                raise AssertionError("Existing polygon was not preserved as the boundary source")
            if existing_feature["requires_review"] is not False:
                raise AssertionError(
                    "Existing accepted polygon was marked as automatically derived"
                )
            classified_points = QgsVectorLayer(
                "Point?crs=EPSG:32616&field=source_id:integer",
                "classified_points",
                "memory",
            )
            center = boundary_feature.geometry().pointOnSurface().asPoint()
            classified_features = []
            for source_id, point in (
                (1, QgsPointXY(center)),
                (2, QgsPointXY(center.x() + 1000.0, center.y() + 1000.0)),
            ):
                feature = QgsFeature(classified_points.fields())
                feature.setGeometry(QgsGeometry.fromPointXY(point))
                feature["source_id"] = source_id
                classified_features.append(feature)
            classified_points.dataProvider().addFeatures(classified_features)
            classification_result = processing.run(
                "yield_data_cleaner:classify_by_boundary",
                {
                    "POINTS": classified_points,
                    "BOUNDARY": boundary_output,
                    "TOLERANCE": 0.0,
                    "SUMMARY": str(directory_path / "boundary_classification.json"),
                    "ALL_OBSERVATIONS": QgsProcessing.TEMPORARY_OUTPUT,
                    "INSIDE_OBSERVATIONS": QgsProcessing.TEMPORARY_OUTPUT,
                    "OUTSIDE_OBSERVATIONS": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
            all_classified = classification_result["ALL_OBSERVATIONS"]
            inside_classified = classification_result["INSIDE_OBSERVATIONS"]
            outside_classified = classification_result["OUTSIDE_OBSERVATIONS"]
            if all_classified.featureCount() != 2:
                raise AssertionError("Boundary audit output did not retain all observations")
            if inside_classified.featureCount() != 1 or outside_classified.featureCount() != 1:
                raise AssertionError("Boundary classification counts are incorrect")
            statuses = {feature["boundary_status"] for feature in all_classified.getFeatures()}
            if statuses != {"inside_boundary", "outside_boundary"}:
                raise AssertionError(f"Unexpected boundary statuses: {statuses}")
            del outside_classified
            del inside_classified
            del all_classified
            del classified_features
            del classified_points
            del existing_feature
            del existing_output
            del boundary_feature
            del boundary_output
            del boundary_features
            del boundary_points
            del loaded_output
            del loaded_layer
            del loaded_feature
            del audit_feature
            audit_layer.deleteLater()
            del audit_layer
            gc.collect()
            app.processEvents()
        trace("algorithm-complete")
        print(f"YIELD_DATA_CLEANER_QGIS_SMOKE_OK {Qgis.QGIS_VERSION}")
    finally:
        trace("cleanup")
        if provider is not None:
            QgsApplication.processingRegistry().removeProvider(provider)
        app.exitQgis()
        if cleanup_directory:
            shutil.rmtree(cleanup_directory, ignore_errors=True)


if __name__ == "__main__":
    main()
