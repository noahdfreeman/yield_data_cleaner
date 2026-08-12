# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect a loaded point source or browsed file without modifying it."""

from __future__ import annotations

import json
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsVectorLayer,
)

from ..compat import enum_member
from ..core.column_detection import detect_columns
from ..core.crs_service import recognize_crs
from ..core.delimited_text import inspect_delimited_file
from ..version import VERSION


class InspectYieldDataAlgorithm(QgsProcessingAlgorithm):
    SOURCE = "SOURCE"
    INPUT_FILE = "INPUT_FILE"
    REPORT = "REPORT"

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("InspectYieldDataAlgorithm", message)

    def name(self):
        return "inspect_yield_data"

    def displayName(self):
        return self.tr("Inspect yield monitor data")

    def group(self):
        return self.tr("Input and preparation")

    def groupId(self):
        return "input_preparation"

    def shortHelpString(self):
        return self.tr(
            "Inspect either a point source already available to QGIS or a local "
            "file. The algorithm writes a JSON report with fields, automatic "
            "mapping suggestions, and CRS information. It does not modify input data."
        )

    def createInstance(self):
        return InspectYieldDataAlgorithm()

    def initAlgorithm(self, config=None):
        del config
        point_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPoint")
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SOURCE,
                self.tr("Loaded point layer or QGIS-readable point source"),
                types=[point_type],
                optional=True,
            )
        )
        file_behavior = enum_member(QgsProcessingParameterFile, "Behavior", "File")
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FILE,
                self.tr("Or browse for a yield data file"),
                behavior=file_behavior,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.REPORT,
                self.tr("Inspection report"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="yield_input_inspection.json",
            )
        )

    @staticmethod
    def _inspect_feature_source(source, declared_crs: str | None) -> dict:
        columns = [field.name() for field in source.fields()]
        rows = []
        for index, feature in enumerate(source.getFeatures()):
            rows.append({name: feature[name] for name in columns})
            if index >= 49:
                break
        suggestions = detect_columns(columns, rows)
        mapping = {item.canonical_field: item.source_column for item in suggestions}
        x_name = mapping.get("x")
        y_name = mapping.get("y")
        recognition = None
        if x_name and y_name:
            recognition = recognize_crs(
                (row.get(x_name) for row in rows),
                (row.get(y_name) for row in rows),
                x_name,
                y_name,
                declared_authid=declared_crs,
            ).to_dict()
        elif declared_crs:
            recognition = recognize_crs((), (), declared_authid=declared_crs).to_dict()
        return {
            "source_kind": "vector",
            "columns": columns,
            "sample_count": len(rows),
            "mapping_suggestions": [item.to_dict() for item in suggestions],
            "crs_recognition": recognition,
        }

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.SOURCE, context)
        input_file = self.parameterAsFile(parameters, self.INPUT_FILE, context).strip()
        if (source is None) == (not input_file):
            raise QgsProcessingException(
                self.tr("Choose exactly one input: a loaded point source or a local file.")
            )

        if source is not None:
            source_crs = source.sourceCrs()
            declared = source_crs.authid() if source_crs.isValid() else None
            report = self._inspect_feature_source(source, declared)
            report["source_name"] = source.sourceName()
        else:
            path = Path(input_file)
            if path.suffix.lower() in {".csv", ".txt", ".tsv"}:
                inspection = inspect_delimited_file(path)
                report = inspection.to_dict()
                report["source_kind"] = "delimited_text"
            else:
                layer = QgsVectorLayer(str(path), path.stem, "ogr")
                if not layer.isValid():
                    raise QgsProcessingException(self.tr(f"QGIS could not open {path}"))
                declared = layer.crs().authid() if layer.crs().isValid() else None
                report = self._inspect_feature_source(layer, declared)
                report["source_name"] = str(path.resolve())

        report.update(
            {
                "plugin": "Yield Data Cleaner",
                "plugin_version": VERSION,
                "input_modified": False,
            }
        )
        destination = Path(self.parameterAsFileOutput(parameters, self.REPORT, context))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        feedback.pushInfo(self.tr(f"Inspection report written to {destination}"))
        return {self.REPORT: str(destination)}
