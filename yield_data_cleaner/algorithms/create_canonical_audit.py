# SPDX-License-Identifier: GPL-3.0-or-later
"""Create a canonical, non-destructive audit point layer."""

from __future__ import annotations

import csv
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
    QgsProcessingParameterCrs,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsVectorLayer,
    QgsWkbTypes,
)

from ..compat import enum_member, qgis_field_type
from ..core.canonical_schema import CANONICAL_FIELDS, CrsConfidence
from ..core.canonicalizer import canonicalize_attributes
from ..core.column_detection import detect_columns
from ..core.crs_service import choose_analysis_crs, recognize_crs
from ..core.delimited_text import inspect_delimited_file
from ..core.mapping_profile import MappingProfile, load_mapping_profile
from ..core.manifest import build_manifest, file_signature


class CreateCanonicalAuditAlgorithm(QgsProcessingAlgorithm):
    SOURCE = "SOURCE"
    INPUT_FILE = "INPUT_FILE"
    MAPPING_PROFILE = "MAPPING_PROFILE"
    CROP = "CROP"
    UNIT_PROFILE = "UNIT_PROFILE"
    SOURCE_CRS = "SOURCE_CRS"
    OUTPUT_CRS = "OUTPUT_CRS"
    MAPPING_REPORT = "MAPPING_REPORT"
    RUN_MANIFEST = "RUN_MANIFEST"
    OUTPUT = "OUTPUT"

    CROPS = ("corn", "soybean", "wheat")
    UNIT_PROFILES = ("imperial", "metric")

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("CreateCanonicalAuditAlgorithm", message)

    def name(self):
        return "create_canonical_audit"

    def displayName(self):
        return self.tr("Prepare yield data for cleaning")

    def group(self):
        return self.tr("Input and preparation")

    def groupId(self):
        return "input_preparation"

    def shortHelpString(self):
        return self.tr(
            "Prepare a point layer that preserves source fields and adds normalized, "
            "vendor-neutral fields. Choose either a loaded point source or a "
            "local CSV/vector file. Geographic coordinates are transformed to a local "
            "projected CRS unless an output CRS is supplied. No cleaning is performed."
        )

    def createInstance(self):
        return CreateCanonicalAuditAlgorithm()

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
            QgsProcessingParameterFile(
                self.MAPPING_PROFILE,
                self.tr("Reviewed mapping profile (optional JSON)"),
                behavior=file_behavior,
                extension="json",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(self.CROP, self.tr("Crop"), self.CROPS, defaultValue=0)
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.UNIT_PROFILE,
                self.tr("Source unit profile"),
                ("Imperial", "Metric"),
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterCrs(
                self.SOURCE_CRS,
                self.tr("Source CRS override for files without CRS metadata"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterCrs(
                self.OUTPUT_CRS,
                self.tr("Output/analysis CRS (optional; local projected CRS chosen automatically)"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.MAPPING_REPORT,
                self.tr("Applied mapping and CRS report"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="applied_column_mapping.json",
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.RUN_MANIFEST,
                self.tr("Preparation run manifest"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="run_manifest.json",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Prepared yield observations"),
                type=point_type,
            )
        )

    @staticmethod
    def _sample_source(source, limit=50):
        columns = [field.name() for field in source.fields()]
        rows = []
        for index, feature in enumerate(source.getFeatures()):
            rows.append({name: feature[name] for name in columns})
            if index + 1 >= limit:
                break
        return columns, rows

    @staticmethod
    def _profile(parameters, algorithm, context, columns, rows, source_crs_authid):
        mapping_path = algorithm.parameterAsFile(
            parameters, algorithm.MAPPING_PROFILE, context
        ).strip()
        if mapping_path:
            profile = load_mapping_profile(mapping_path)
            errors = profile.validate(columns)
            if errors:
                raise QgsProcessingException("; ".join(errors))
            if source_crs_authid and not profile.source_crs:
                profile.source_crs = source_crs_authid
            return profile, "reviewed_profile"
        crop_index = algorithm.parameterAsEnum(parameters, algorithm.CROP, context)
        unit_index = algorithm.parameterAsEnum(parameters, algorithm.UNIT_PROFILE, context)
        suggestions = detect_columns(columns, rows)
        return (
            MappingProfile(
                mapping={item.canonical_field: item.source_column for item in suggestions},
                crop_code=algorithm.CROPS[crop_index],
                unit_profile=algorithm.UNIT_PROFILES[unit_index],
                source_crs=source_crs_authid,
                profile_name="Automatic mapping - review recommended",
            ),
            "automatic",
        )

    @staticmethod
    def _canonical_qgis_fields():
        type_map = {
            "text": qgis_field_type("string"),
            "integer": qgis_field_type("integer"),
            "number": qgis_field_type("double"),
            "boolean": qgis_field_type("boolean"),
            "datetime": qgis_field_type("string"),
        }
        return [QgsField(item.name, type_map[item.value_type]) for item in CANONICAL_FIELDS]

    @classmethod
    def _output_fields(cls, source_fields):
        output = QgsFields()
        canonical_names_lower = {field.name.lower() for field in CANONICAL_FIELDS} | {
            "geometry_original"
        }
        used_lower: set[str] = set()
        source_names: dict[str, str] = {}
        for source_field in source_fields:
            original = source_field.name()
            candidate = f"src_{original}" if original.lower() in canonical_names_lower else original
            base = candidate
            suffix = 2
            while candidate.lower() in used_lower or candidate.lower() in canonical_names_lower:
                candidate = f"{base}_{suffix}"
                suffix += 1
            copied = QgsField(source_field)
            copied.setName(candidate)
            output.append(copied)
            source_names[original] = candidate
            used_lower.add(candidate.lower())
        for field in cls._canonical_qgis_fields():
            output.append(field)
            used_lower.add(field.name().lower())
        output.append(QgsField("geometry_original", qgis_field_type("string")))
        return output, source_names

    @staticmethod
    def _analysis_crs(source_crs, output_override, sample_points, transform_context):
        if output_override.isValid():
            return output_override
        if not source_crs.isValid():
            raise QgsProcessingException(
                "Source CRS is unresolved; select a source CRS before import"
            )
        if not source_crs.isGeographic():
            return source_crs
        if not sample_points:
            raise QgsProcessingException(
                "Cannot choose a projected analysis CRS from an empty input"
            )
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, wgs84, transform_context)
        lon_lat = [transform.transform(point) for point in sample_points]
        longitude = sum(point.x() for point in lon_lat) / len(lon_lat)
        latitude = sum(point.y() for point in lon_lat) / len(lon_lat)
        return QgsCoordinateReferenceSystem(choose_analysis_crs("EPSG:4326", (longitude, latitude)))

    @staticmethod
    def _feature_point(geometry):
        if geometry is None or geometry.isNull() or geometry.isEmpty():
            return None
        if geometry.isMultipart():
            points = geometry.asMultiPoint()
            return points[0] if points else None
        return geometry.asPoint()

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.SOURCE, context)
        input_file = self.parameterAsFile(parameters, self.INPUT_FILE, context).strip()
        if (source is None) == (not input_file):
            raise QgsProcessingException(
                self.tr("Choose exactly one input: a loaded point source or a local file.")
            )

        csv_inspection = None
        source_label = ""
        if source is None:
            path = Path(input_file)
            if path.suffix.lower() in {".csv", ".txt", ".tsv"}:
                csv_inspection = inspect_delimited_file(path)
                columns = list(csv_inspection.columns)
                sample_rows = list(csv_inspection.sample_rows)
                source_label = str(path.resolve())
                source_fields = QgsFields()
                for name in columns:
                    source_fields.append(QgsField(name, qgis_field_type("string")))
            else:
                vector_layer = QgsVectorLayer(str(path), path.stem, "ogr")
                if not vector_layer.isValid():
                    raise QgsProcessingException(self.tr(f"QGIS could not open {path}"))
                point_geometry = enum_member(QgsWkbTypes, "GeometryType", "PointGeometry")
                if QgsWkbTypes.geometryType(vector_layer.wkbType()) != point_geometry:
                    raise QgsProcessingException(
                        self.tr("The selected vector file is not a point layer")
                    )
                source = vector_layer
                columns, sample_rows = self._sample_source(source)
                source_fields = source.fields()
                source_label = str(path.resolve())
        else:
            columns, sample_rows = self._sample_source(source)
            source_fields = source.fields()
            source_label = source.sourceName()

        declared_crs = source.sourceCrs() if source is not None else QgsCoordinateReferenceSystem()
        override_crs = self.parameterAsCrs(parameters, self.SOURCE_CRS, context)
        source_crs = declared_crs if declared_crs.isValid() else override_crs
        source_authid = source_crs.authid() if source_crs.isValid() else None
        profile, profile_source = self._profile(
            parameters, self, context, columns, sample_rows, source_authid
        )

        crs_confidence = (
            CrsConfidence.DECLARED if declared_crs.isValid() else CrsConfidence.UNRESOLVED
        )
        if profile.source_crs:
            profile_crs = QgsCoordinateReferenceSystem(profile.source_crs)
            if not profile_crs.isValid():
                raise QgsProcessingException(
                    f"Mapping profile CRS is invalid: {profile.source_crs}"
                )
            source_crs = profile_crs
            crs_confidence = (
                CrsConfidence.DECLARED if declared_crs.isValid() else CrsConfidence.USER_CONFIRMED
            )
        elif override_crs.isValid():
            source_crs = override_crs
            profile.source_crs = override_crs.authid()
            crs_confidence = CrsConfidence.USER_CONFIRMED
        elif csv_inspection is not None:
            x_name, y_name = profile.mapping.get("x"), profile.mapping.get("y")
            if not x_name or not y_name:
                raise QgsProcessingException("CSV import requires reviewed X and Y column mappings")
            recognition = recognize_crs(
                (row.get(x_name) for row in sample_rows),
                (row.get(y_name) for row in sample_rows),
                x_name,
                y_name,
            )
            if not recognition.authid or recognition.requires_confirmation:
                raise QgsProcessingException(
                    f"CRS requires confirmation: {recognition.reason}. "
                    "Set the source CRS parameter."
                )
            source_crs = QgsCoordinateReferenceSystem(recognition.authid)
            profile.source_crs = recognition.authid
            crs_confidence = CrsConfidence.RECOGNIZED

        if not source_crs.isValid():
            raise QgsProcessingException(
                "Source CRS is unresolved; select a source CRS before import"
            )

        sample_points = []
        if csv_inspection is not None:
            x_name, y_name = profile.mapping.get("x"), profile.mapping.get("y")
            for row in sample_rows:
                try:
                    sample_points.append(QgsPointXY(float(row[x_name]), float(row[y_name])))
                except (KeyError, TypeError, ValueError):
                    continue
        else:
            for feature in source.getFeatures():
                point = self._feature_point(feature.geometry())
                if point is not None:
                    sample_points.append(QgsPointXY(point))
                if len(sample_points) >= 50:
                    break

        output_override = self.parameterAsCrs(parameters, self.OUTPUT_CRS, context)
        analysis_crs = self._analysis_crs(
            source_crs, output_override, sample_points, context.transformContext()
        )
        transform = QgsCoordinateTransform(source_crs, analysis_crs, context.transformContext())
        output_fields, source_field_names = self._output_fields(source_fields)
        wkb_type = QgsWkbTypes.Point if csv_inspection is not None else source.wkbType()
        sink, destination_id = self.parameterAsSink(
            parameters, self.OUTPUT, context, output_fields, wkb_type, analysis_crs
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        def write_record(source_index, attributes, geometry):
            if feedback.isCanceled():
                return False
            if geometry is None or geometry.isNull() or geometry.isEmpty():
                feedback.reportError(f"Skipped source record {source_index}: missing geometry")
                return True
            original_wkt = geometry.asWkt()
            transformed = QgsGeometry(geometry)
            try:
                transformed.transform(transform)
            except Exception as exc:
                feedback.reportError(
                    f"Skipped source record {source_index}: CRS transform failed: {exc}"
                )
                return True
            canonical = canonicalize_attributes(
                attributes,
                source_label,
                source_index,
                profile,
                analysis_crs.authid(),
                crs_confidence,
            )
            output_feature = QgsFeature(output_fields)
            output_feature.setGeometry(transformed)
            for original_name, output_name in source_field_names.items():
                output_feature[output_name] = attributes.get(original_name)
            for name, value in canonical.items():
                if output_fields.indexOf(name) >= 0:
                    output_feature[name] = value
            output_feature["geometry_original"] = original_wkt
            fast_insert = enum_member(QgsFeatureSink, "Flag", "FastInsert")
            if not sink.addFeature(output_feature, fast_insert):
                raise QgsProcessingException(f"Failed to write source record {source_index}")
            return True

        processed = 0
        if csv_inspection is not None:
            path = Path(input_file)
            with path.open("r", encoding=csv_inspection.encoding, newline="") as stream:
                reader = csv.DictReader(stream, delimiter=csv_inspection.delimiter)
                x_name, y_name = profile.mapping["x"], profile.mapping["y"]
                for source_index, row in enumerate(reader):
                    try:
                        geometry = QgsGeometry.fromPointXY(
                            QgsPointXY(float(row[x_name]), float(row[y_name]))
                        )
                    except (KeyError, TypeError, ValueError):
                        feedback.reportError(
                            f"Skipped source record {source_index}: invalid coordinates"
                        )
                        continue
                    if not write_record(source_index, row, geometry):
                        break
                    processed += 1
        else:
            for source_index, feature in enumerate(source.getFeatures()):
                attributes = {field.name(): feature[field.name()] for field in source.fields()}
                if not write_record(source_index, attributes, feature.geometry()):
                    break
                processed += 1

        report = {
            "profile_source": profile_source,
            "profile": profile.to_dict(),
            "source_name": source_label,
            "source_crs": source_crs.authid(),
            "analysis_crs": analysis_crs.authid(),
            "crs_confidence": crs_confidence.value,
            "source_field_names_in_output": source_field_names,
            "processed_records": processed,
            "input_modified": False,
        }
        report_path = Path(self.parameterAsFileOutput(parameters, self.MAPPING_REPORT, context))
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        input_signature = None
        if input_file:
            input_signature = file_signature(input_file)
        manifest = build_manifest(
            source_label,
            "delimited_text" if csv_inspection is not None else "qgis_feature_source",
            source_crs.authid(),
            analysis_crs.authid(),
            profile.crop_code,
            profile.unit_profile,
            profile_source,
            processed,
            input_signature,
        )
        manifest_path = Path(self.parameterAsFileOutput(parameters, self.RUN_MANIFEST, context))
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        feedback.pushInfo(f"Prepared yield layer uses {analysis_crs.authid()}")
        return {
            self.OUTPUT: destination_id,
            self.MAPPING_REPORT: str(report_path),
            self.RUN_MANIFEST: str(manifest_path),
        }
