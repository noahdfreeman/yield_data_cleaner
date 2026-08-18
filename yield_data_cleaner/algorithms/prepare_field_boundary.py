# SPDX-License-Identifier: GPL-3.0-or-later
"""Select/validate or derive one reviewed field boundary."""

from __future__ import annotations

import json
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)

from ..boundaries.derivation import derive_operational_boundary, validate_boundary_geometry
from ..compat import enum_member, qgis_field_type
from ..core.crs_service import choose_analysis_crs


class PrepareFieldBoundaryAlgorithm(QgsProcessingAlgorithm):
    MODE = "MODE"
    EXISTING_BOUNDARY = "EXISTING_BOUNDARY"
    YIELD_POINTS = "YIELD_POINTS"
    WIDTH_FIELD = "WIDTH_FIELD"
    DEFAULT_WIDTH = "DEFAULT_WIDTH"
    GAP_CLOSING = "GAP_CLOSING"
    CONCAVITY = "CONCAVITY"
    PROVENANCE = "PROVENANCE"
    OUTPUT = "OUTPUT"

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("PrepareFieldBoundaryAlgorithm", message)

    def name(self):
        return "prepare_field_boundary"

    def displayName(self):
        return self.tr("Prepare field boundary")

    def group(self):
        return self.tr("Field boundary")

    def groupId(self):
        return "field_boundary"

    def shortHelpString(self):
        return self.tr(
            "Prepare one field boundary from an existing polygon or derive an "
            "operational harvest extent from yield points. Existing layers and "
            "files are both accepted by QGIS feature-source selectors. Derived "
            "boundaries require visual review and are not legal property boundaries."
        )

    def createInstance(self):
        return PrepareFieldBoundaryAlgorithm()

    def initAlgorithm(self, config=None):
        del config
        polygon_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPolygon")
        point_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPoint")
        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE,
                self.tr("Boundary mode"),
                ("Use one existing polygon", "Derive operational extent from yield points"),
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.EXISTING_BOUNDARY,
                self.tr("Existing boundary layer or file"),
                types=[polygon_type],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.YIELD_POINTS,
                self.tr("Yield points for boundary derivation"),
                types=[point_type],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.WIDTH_FIELD,
                self.tr("Canonical swath-width field in meters (optional)"),
                parentLayerParameterName=self.YIELD_POINTS,
                type=enum_member(QgsProcessingParameterField, "DataType", "Numeric"),
                optional=True,
                defaultValue="swath_width_m",
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_WIDTH,
                self.tr("Default swath width in meters (0 disables)"),
                type=enum_member(QgsProcessingParameterNumber, "Type", "Double"),
                defaultValue=9.144,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.GAP_CLOSING,
                self.tr("Gap-closing distance in meters"),
                type=enum_member(QgsProcessingParameterNumber, "Type", "Double"),
                defaultValue=1.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CONCAVITY,
                self.tr("Concave-hull target percent for fallback"),
                type=enum_member(QgsProcessingParameterNumber, "Type", "Double"),
                defaultValue=0.3,
                minValue=0.0,
                maxValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.PROVENANCE,
                self.tr("Boundary provenance report"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="field_boundary_provenance.json",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Prepared field boundary"),
                type=polygon_type,
            )
        )

    @staticmethod
    def _analysis_crs(source_crs, centroid, transform_context):
        if not source_crs.isValid():
            raise QgsProcessingException("Input CRS is unresolved")
        if not source_crs.isGeographic():
            return source_crs
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, wgs84, transform_context)
        lon_lat = transform.transform(centroid)
        authid = choose_analysis_crs("EPSG:4326", (lon_lat.x(), lon_lat.y()))
        return QgsCoordinateReferenceSystem(authid)

    @staticmethod
    def _fields():
        fields = QgsFields()
        fields.append(QgsField("boundary_source", qgis_field_type("string")))
        fields.append(QgsField("method", qgis_field_type("string")))
        fields.append(QgsField("confidence", qgis_field_type("double")))
        fields.append(QgsField("requires_review", qgis_field_type("boolean")))
        fields.append(QgsField("geometry_repaired", qgis_field_type("boolean")))
        fields.append(QgsField("area_m2", qgis_field_type("double")))
        fields.append(QgsField("source_crs", qgis_field_type("string")))
        fields.append(QgsField("analysis_crs", qgis_field_type("string")))
        return fields

    def processAlgorithm(self, parameters, context, feedback):
        mode = self.parameterAsEnum(parameters, self.MODE, context)
        existing = self.parameterAsSource(parameters, self.EXISTING_BOUNDARY, context)
        points = self.parameterAsSource(parameters, self.YIELD_POINTS, context)
        transform_context = context.transformContext()

        if mode == 0:
            if existing is None:
                raise QgsProcessingException("Select one existing polygon boundary")
            features = list(existing.getFeatures())
            if len(features) != 1:
                raise QgsProcessingException(
                    f"Existing-boundary mode requires exactly one feature; found {len(features)}"
                )
            source_crs = existing.sourceCrs()
            geometry = features[0].geometry()
            centroid = geometry.centroid().asPoint()
            analysis_crs = self._analysis_crs(source_crs, centroid, transform_context)
            geometry = QgsGeometry(geometry)
            geometry.transform(QgsCoordinateTransform(source_crs, analysis_crs, transform_context))
            geometry, repaired = validate_boundary_geometry(geometry)
            method = "existing_polygon"
            confidence = 1.0
            assumptions = ("One user-selected polygon feature",)
            point_count = None
            width_count = None
            boundary_source = existing.sourceName()
        else:
            if points is None:
                raise QgsProcessingException("Select yield points for boundary derivation")
            source_crs = points.sourceCrs()
            extent = points.sourceExtent()
            centroid = QgsPointXY(extent.center())
            analysis_crs = self._analysis_crs(source_crs, centroid, transform_context)
            transform = QgsCoordinateTransform(source_crs, analysis_crs, transform_context)
            width_field = self.parameterAsString(parameters, self.WIDTH_FIELD, context).strip()
            if width_field and points.fields().indexOf(width_field) < 0:
                width_field = ""
            point_values = []
            widths = []
            for feature in points.getFeatures():
                if feedback.isCanceled():
                    break
                geometry = feature.geometry()
                if geometry.isNull() or geometry.isEmpty():
                    continue
                point = geometry.asMultiPoint()[0] if geometry.isMultipart() else geometry.asPoint()
                point_values.append(transform.transform(QgsPointXY(point)))
                widths.append(feature[width_field] if width_field else None)
            default_width = self.parameterAsDouble(parameters, self.DEFAULT_WIDTH, context)
            result = derive_operational_boundary(
                point_values,
                widths,
                default_width or None,
                self.parameterAsDouble(parameters, self.GAP_CLOSING, context),
                self.parameterAsDouble(parameters, self.CONCAVITY, context),
            )
            geometry, repaired = validate_boundary_geometry(result.geometry)
            method = result.method
            confidence = result.confidence
            assumptions = result.assumptions
            point_count = result.point_count
            width_count = result.width_value_count
            boundary_source = points.sourceName()

        fields = self._fields()
        sink, destination_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Type.MultiPolygon,
            analysis_crs,
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        geometry.convertToMultiType()
        output = QgsFeature(fields)
        output.setGeometry(geometry)
        output["boundary_source"] = boundary_source
        output["method"] = method
        output["confidence"] = confidence
        output["requires_review"] = mode == 1
        output["geometry_repaired"] = repaired
        output["area_m2"] = geometry.area()
        output["source_crs"] = source_crs.authid()
        output["analysis_crs"] = analysis_crs.authid()
        fast_insert = enum_member(QgsFeatureSink, "Flag", "FastInsert")
        sink.addFeature(output, fast_insert)

        provenance = {
            "boundary_source": boundary_source,
            "method": method,
            "confidence": confidence,
            "requires_review": mode == 1,
            "geometry_repaired": repaired,
            "area_m2": geometry.area(),
            "source_crs": source_crs.authid(),
            "analysis_crs": analysis_crs.authid(),
            "point_count": point_count,
            "width_value_count": width_count,
            "assumptions": list(assumptions),
            "legal_boundary": False if mode == 1 else None,
        }
        provenance_path = Path(self.parameterAsFileOutput(parameters, self.PROVENANCE, context))
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        provenance_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        return {self.OUTPUT: destination_id, self.PROVENANCE: str(provenance_path)}
