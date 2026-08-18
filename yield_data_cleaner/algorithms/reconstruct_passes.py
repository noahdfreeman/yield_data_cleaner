# SPDX-License-Identifier: GPL-3.0-or-later
"""Reconstruct or validate harvest passes from point observations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)

from ..compat import enum_member, qgis_field_type
from ..core.pass_reconstruction import (
    PassReconstructionConfig,
    reconstruct_passes,
    validate_source_passes,
)


class ReconstructPassesAlgorithm(QgsProcessingAlgorithm):
    POINTS = "POINTS"
    MAX_TIME_GAP = "MAX_TIME_GAP"
    MAX_DISTANCE_GAP = "MAX_DISTANCE_GAP"
    TURN_ANGLE = "TURN_ANGLE"
    MIN_POINTS = "MIN_POINTS"
    SPLIT_ON_HEADER = "SPLIT_ON_HEADER"
    USE_SOURCE_PASSES = "USE_SOURCE_PASSES"
    OUTPUT_POINTS = "OUTPUT_POINTS"
    PASS_LINES = "PASS_LINES"  # nosec B105
    SUMMARY = "SUMMARY"

    @staticmethod
    def tr(message: str) -> str:
        return QCoreApplication.translate("ReconstructPassesAlgorithm", message)

    def name(self) -> str:
        return "reconstruct_passes"

    def displayName(self) -> str:
        return self.tr("Reconstruct harvest passes")

    def group(self) -> str:
        return self.tr("Passes")

    def groupId(self) -> str:
        return "passes"

    def shortHelpString(self) -> str:
        return self.tr(
            "Segment yield observations into contiguous harvest passes using turn detection, "
            "time gaps, distance jumps, and header state transitions. Produces updated observation "
            "points and a pass line layer with summary statistics."
        )

    def createInstance(self) -> ReconstructPassesAlgorithm:
        return ReconstructPassesAlgorithm()

    def initAlgorithm(self, config=None):
        del config
        point_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPoint")
        line_type = enum_member(QgsProcessing, "SourceType", "TypeVectorLine")

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINTS,
                self.tr("Yield point observations"),
                types=[point_type],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_TIME_GAP,
                self.tr("Maximum time gap between points in pass (seconds)"),
                type=enum_member(QgsProcessingParameterNumber, "Type", "Double"),
                defaultValue=30.0,
                minValue=1.0,
                maxValue=3600.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_DISTANCE_GAP,
                self.tr("Maximum distance gap between points in pass (meters)"),
                type=enum_member(QgsProcessingParameterNumber, "Type", "Double"),
                defaultValue=35.0,
                minValue=1.0,
                maxValue=1000.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TURN_ANGLE,
                self.tr("Turn detection threshold (degrees)"),
                type=enum_member(QgsProcessingParameterNumber, "Type", "Double"),
                defaultValue=50.0,
                minValue=10.0,
                maxValue=180.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_POINTS,
                self.tr("Minimum points per pass"),
                type=enum_member(QgsProcessingParameterNumber, "Type", "Integer"),
                defaultValue=3,
                minValue=1,
                maxValue=100,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SPLIT_ON_HEADER,
                self.tr("Split pass when header is disengaged"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.USE_SOURCE_PASSES,
                self.tr("Validate source pass IDs when present instead of reconstructing"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_POINTS,
                self.tr("Observations with assigned passes"),
                type=point_type,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.PASS_LINES,
                self.tr("Harvest pass lines"),
                type=line_type,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.SUMMARY,
                self.tr("Pass reconstruction summary"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="pass_reconstruction_summary.json",
            )
        )

    @staticmethod
    def _output_point_fields(source_fields: QgsFields) -> QgsFields:
        fields = QgsFields(source_fields)
        existing = {f.name().lower() for f in fields}
        for name, field_type in (
            ("pass_id", "string"),
            ("pass_source", "string"),
            ("pass_confidence", "double"),
            ("heading_deg", "double"),
        ):
            if name.lower() not in existing:
                fields.append(QgsField(name, qgis_field_type(field_type)))
        return fields

    @staticmethod
    def _pass_line_fields() -> QgsFields:
        fields = QgsFields()
        fields.append(QgsField("pass_id", qgis_field_type("string")))
        fields.append(QgsField("pass_source", qgis_field_type("string")))
        fields.append(QgsField("point_count", qgis_field_type("int")))
        fields.append(QgsField("length_m", qgis_field_type("double")))
        fields.append(QgsField("duration_s", qgis_field_type("double")))
        fields.append(QgsField("mean_heading_deg", qgis_field_type("double")))
        fields.append(QgsField("confidence", qgis_field_type("double")))
        fields.append(QgsField("split_reason", qgis_field_type("string")))
        fields.append(QgsField("start_time", qgis_field_type("string")))
        fields.append(QgsField("end_time", qgis_field_type("string")))
        return fields

    def processAlgorithm(self, parameters, context, feedback):
        points = self.parameterAsSource(parameters, self.POINTS, context)
        if points is None:
            raise QgsProcessingException("Point observations layer is required")

        config = PassReconstructionConfig(
            max_time_gap_s=self.parameterAsDouble(parameters, self.MAX_TIME_GAP, context),
            max_distance_gap_m=self.parameterAsDouble(parameters, self.MAX_DISTANCE_GAP, context),
            turn_angle_threshold_deg=self.parameterAsDouble(parameters, self.TURN_ANGLE, context),
            min_points_per_pass=self.parameterAsInt(parameters, self.MIN_POINTS, context),
            split_on_header_disengage=self.parameterAsBool(
                parameters, self.SPLIT_ON_HEADER, context
            ),
        )
        use_source = self.parameterAsBool(parameters, self.USE_SOURCE_PASSES, context)

        # Collect features and extract observation dictionaries
        features: list[QgsFeature] = []
        obs_list: list[dict[str, Any]] = []

        field_names = [f.name() for f in points.fields()]
        has_source_pass = "source_pass_id" in field_names

        for idx, feat in enumerate(points.getFeatures()):
            if feedback.isCanceled():
                break
            features.append(feat)
            geom = feat.geometry()
            pt_coord = (
                (geom.asPoint().x(), geom.asPoint().y()) if (geom and not geom.isEmpty()) else None
            )

            obs: dict[str, Any] = {"source_index": idx}
            if pt_coord:
                obs["x"] = pt_coord[0]
                obs["y"] = pt_coord[1]

            for fname in field_names:
                val = feat[fname]
                if val is not None:
                    obs[fname] = val

            obs_list.append(obs)

        if use_source and has_source_pass:
            result = validate_source_passes(obs_list, config)
        else:
            result = reconstruct_passes(obs_list, config)

        # Setup sinks
        out_point_fields = self._output_point_fields(points.fields())
        points_sink, points_dest = self.parameterAsSink(
            parameters,
            self.OUTPUT_POINTS,
            context,
            out_point_fields,
            points.wkbType(),
            points.sourceCrs(),
        )
        if points_sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_POINTS))

        line_fields = self._pass_line_fields()
        line_wkb = enum_member(QgsWkbTypes, "Type", "LineString")
        lines_sink, lines_dest = self.parameterAsSink(
            parameters,
            self.PASS_LINES,
            context,
            line_fields,
            line_wkb,
            points.sourceCrs(),
        )
        if lines_sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.PASS_LINES))

        fast_insert = enum_member(QgsFeatureSink, "Flag", "FastInsert")

        # Write output points
        for idx, feat in enumerate(features):
            if feedback.isCanceled():
                break
            update = (
                result.observation_updates[idx] if idx < len(result.observation_updates) else {}
            )
            out_feat = QgsFeature(out_point_fields)
            out_feat.setGeometry(feat.geometry())
            for fname in field_names:
                out_feat[fname] = feat[fname]
            for key, val in update.items():
                if val is not None:
                    out_feat[key] = val
            points_sink.addFeature(out_feat, fast_insert)

        # Write pass line features
        for seg in result.passes:
            if feedback.isCanceled():
                break
            if len(seg.line_coords) >= 2:
                qgis_pts = [QgsPointXY(x, y) for x, y in seg.line_coords]
                line_geom = QgsGeometry.fromPolylineXY(qgis_pts)
            else:
                line_geom = QgsGeometry()

            line_feat = QgsFeature(line_fields)
            line_feat.setGeometry(line_geom)
            line_feat["pass_id"] = seg.pass_id
            line_feat["pass_source"] = seg.pass_source
            line_feat["point_count"] = seg.point_count
            line_feat["length_m"] = seg.length_m
            line_feat["duration_s"] = seg.duration_s
            line_feat["mean_heading_deg"] = seg.mean_heading_deg
            line_feat["confidence"] = seg.confidence
            line_feat["split_reason"] = seg.split_reason
            line_feat["start_time"] = seg.start_time
            line_feat["end_time"] = seg.end_time
            lines_sink.addFeature(line_feat, fast_insert)

        summary_data = result.to_dict()
        summary_path = Path(self.parameterAsFileOutput(parameters, self.SUMMARY, context))
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")

        return {
            self.OUTPUT_POINTS: points_dest,
            self.PASS_LINES: lines_dest,
            self.SUMMARY: str(summary_path),
        }
