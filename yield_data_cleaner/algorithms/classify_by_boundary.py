# SPDX-License-Identifier: GPL-3.0-or-later
"""Classify yield points against one accepted field boundary."""

from __future__ import annotations

import json
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
)

from ..boundaries.derivation import validate_boundary_geometry
from ..compat import enum_member, qgis_field_type


class ClassifyByBoundaryAlgorithm(QgsProcessingAlgorithm):
    POINTS = "POINTS"
    BOUNDARY = "BOUNDARY"
    TOLERANCE = "TOLERANCE"
    SUMMARY = "SUMMARY"
    ALL_OBSERVATIONS = "ALL_OBSERVATIONS"
    INSIDE_OBSERVATIONS = "INSIDE_OBSERVATIONS"
    OUTSIDE_OBSERVATIONS = "OUTSIDE_OBSERVATIONS"

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("ClassifyByBoundaryAlgorithm", message)

    def name(self):
        return "classify_by_boundary"

    def displayName(self):
        return self.tr("Classify observations by field boundary")

    def group(self):
        return self.tr("Field boundary")

    def groupId(self):
        return "field_boundary"

    def shortHelpString(self):
        return self.tr(
            "Flag point observations as inside or outside one accepted field "
            "boundary. All observations are retained in the prepared output; inside "
            "and outside subsets are additional outputs. Tolerance is recorded and "
            "applied in the projected point-layer CRS."
        )

    def createInstance(self):
        return ClassifyByBoundaryAlgorithm()

    def initAlgorithm(self, config=None):
        del config
        point_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPoint")
        polygon_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPolygon")
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINTS,
                self.tr("Canonical or source point observations"),
                types=[point_type],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BOUNDARY,
                self.tr("Accepted single-field boundary"),
                types=[polygon_type],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TOLERANCE,
                self.tr("Boundary tolerance in meters"),
                type=enum_member(QgsProcessingParameterNumber, "Type", "Double"),
                defaultValue=0.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.SUMMARY,
                self.tr("Boundary classification summary"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="boundary_classification.json",
            )
        )
        for name, description in (
            (self.ALL_OBSERVATIONS, self.tr("All observations with boundary status")),
            (self.INSIDE_OBSERVATIONS, self.tr("Inside-boundary observations")),
            (self.OUTSIDE_OBSERVATIONS, self.tr("Outside-boundary observations")),
        ):
            self.addParameter(QgsProcessingParameterFeatureSink(name, description, type=point_type))

    @staticmethod
    def _output_fields(source_fields):
        fields = QgsFields(source_fields)
        if fields.indexOf("boundary_status") < 0:
            fields.append(QgsField("boundary_status", qgis_field_type("string")))
        return fields

    @staticmethod
    def _copy_feature(source_feature, fields, status):
        output = QgsFeature(fields)
        output.setGeometry(source_feature.geometry())
        for field in source_feature.fields():
            output[field.name()] = source_feature[field.name()]
        output["boundary_status"] = status
        return output

    def processAlgorithm(self, parameters, context, feedback):
        points = self.parameterAsSource(parameters, self.POINTS, context)
        boundary = self.parameterAsSource(parameters, self.BOUNDARY, context)
        if points is None or boundary is None:
            raise QgsProcessingException("Point observations and one boundary are required")
        if not points.sourceCrs().isValid() or points.sourceCrs().isGeographic():
            raise QgsProcessingException(
                "Point observations require a valid projected CRS for meter-based boundary work"
            )
        boundary_features = list(boundary.getFeatures())
        if len(boundary_features) != 1:
            raise QgsProcessingException(
                f"Boundary input must contain exactly one feature; found {len(boundary_features)}"
            )
        boundary_geometry = QgsGeometry(boundary_features[0].geometry())
        if boundary.sourceCrs() != points.sourceCrs():
            transform = QgsCoordinateTransform(
                boundary.sourceCrs(), points.sourceCrs(), context.transformContext()
            )
            boundary_geometry.transform(transform)
        boundary_geometry, _ = validate_boundary_geometry(boundary_geometry)
        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        comparison_geometry = (
            boundary_geometry.buffer(tolerance, 8) if tolerance > 0 else boundary_geometry
        )

        fields = self._output_fields(points.fields())
        sinks = {}
        destinations = {}
        for name in (
            self.ALL_OBSERVATIONS,
            self.INSIDE_OBSERVATIONS,
            self.OUTSIDE_OBSERVATIONS,
        ):
            sink, destination = self.parameterAsSink(
                parameters,
                name,
                context,
                fields,
                points.wkbType(),
                points.sourceCrs(),
            )
            if sink is None:
                raise QgsProcessingException(self.invalidSinkError(parameters, name))
            sinks[name] = sink
            destinations[name] = destination

        inside_count = 0
        outside_count = 0
        fast_insert = enum_member(QgsFeatureSink, "Flag", "FastInsert")
        for feature in points.getFeatures():
            if feedback.isCanceled():
                break
            geometry = feature.geometry()
            is_inside = (
                not geometry.isNull()
                and not geometry.isEmpty()
                and comparison_geometry.intersects(geometry)
            )
            status = "inside_boundary" if is_inside else "outside_boundary"
            output = self._copy_feature(feature, fields, status)
            sinks[self.ALL_OBSERVATIONS].addFeature(output, fast_insert)
            if is_inside:
                sinks[self.INSIDE_OBSERVATIONS].addFeature(output, fast_insert)
                inside_count += 1
            else:
                sinks[self.OUTSIDE_OBSERVATIONS].addFeature(output, fast_insert)
                outside_count += 1

        summary = {
            "total_observations": inside_count + outside_count,
            "inside_boundary": inside_count,
            "outside_boundary": outside_count,
            "tolerance_m": tolerance,
            "point_crs": points.sourceCrs().authid(),
            "boundary_source_crs": boundary.sourceCrs().authid(),
            "outside_observations_retained": True,
        }
        summary_path = Path(self.parameterAsFileOutput(parameters, self.SUMMARY, context))
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return {**destinations, self.SUMMARY: str(summary_path)}
