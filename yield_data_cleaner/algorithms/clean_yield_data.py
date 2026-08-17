# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless QGIS Processing algorithm for non-destructive yield cleaning."""

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
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
)

from ..compat import enum_member, qgis_field_type
from ..core.filter_engine import run_cleaning_filters
from ..core.recipe import CleaningRecipe, default_recipe_for_crop
from ..review.builder import generate_html_review


class CleanYieldDataAlgorithm(QgsProcessingAlgorithm):
    POINTS = "POINTS"
    RECIPE_FILE = "RECIPE_FILE"
    CROP = "CROP"
    ALL_OBSERVATIONS = "ALL_OBSERVATIONS"
    ACCEPTED_OBSERVATIONS = "ACCEPTED_OBSERVATIONS"
    EXCLUDED_OBSERVATIONS = "EXCLUDED_OBSERVATIONS"
    BOUNDARY = "BOUNDARY"
    SUMMARY_JSON = "SUMMARY_JSON"
    RECIPE_JSON = "RECIPE_JSON"
    REVIEW_HTML = "REVIEW_HTML"

    CROPS = ("corn", "soybean", "wheat")

    @staticmethod
    def tr(message: str) -> str:
        return QCoreApplication.translate("CleanYieldDataAlgorithm", message)

    def name(self) -> str:
        return "clean_yield_data"

    def displayName(self) -> str:
        return self.tr("Clean yield monitor data")

    def group(self) -> str:
        return self.tr("Cleaning")

    def groupId(self) -> str:
        return "cleaning"

    def shortHelpString(self) -> str:
        return self.tr(
            "Execute deterministic, non-destructive yield cleaning filters using a versioned recipe. "
            "Preserves every input observation while separating accepted points and recording "
            "standard reason codes for excluded points."
        )

    def createInstance(self) -> CleanYieldDataAlgorithm:
        return CleanYieldDataAlgorithm()

    def initAlgorithm(self, config=None):
        del config
        point_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPoint")
        polygon_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPolygon")
        file_behavior = enum_member(QgsProcessingParameterFile, "Behavior", "File")

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINTS,
                self.tr("Prepared point observations"),
                types=[point_type],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BOUNDARY,
                self.tr("Field boundary polygon (Optional)"),
                types=[polygon_type],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.RECIPE_FILE,
                self.tr("Optional cleaning recipe JSON file"),
                behavior=file_behavior,
                fileFilter=self.tr("JSON files (*.json)"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CROP,
                self.tr("Crop type (used if recipe file not specified)"),
                options=[self.tr("Corn"), self.tr("Soybean"), self.tr("Wheat")],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.ALL_OBSERVATIONS,
                self.tr("All observations with cleaning flags"),
                type=point_type,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.ACCEPTED_OBSERVATIONS,
                self.tr("Accepted observations (cleaned output)"),
                type=point_type,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.EXCLUDED_OBSERVATIONS,
                self.tr("Excluded observations with reason codes"),
                type=point_type,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.SUMMARY_JSON,
                self.tr("Cleaning summary JSON"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="cleaning_summary.json",
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.RECIPE_JSON,
                self.tr("Applied cleaning recipe JSON"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="applied_recipe.json",
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.REVIEW_HTML,
                self.tr("Portable HTML cleaning review report"),
                fileFilter=self.tr("HTML files (*.html)"),
                defaultValue="yield_cleaning_review.html",
            )
        )

    @staticmethod
    def _output_fields(source_fields: QgsFields) -> QgsFields:
        fields = QgsFields(source_fields)
        existing = {f.name().lower() for f in fields}
        for name in ("clean_status", "filter_flags", "filter_reasons"):
            if name.lower() not in existing:
                fields.append(QgsField(name, qgis_field_type("string")))
        return fields

    def processAlgorithm(self, parameters, context, feedback):
        points = self.parameterAsSource(parameters, self.POINTS, context)
        if points is None:
            raise QgsProcessingException("Point observations layer is required")

        recipe_path_str = self.parameterAsFile(parameters, self.RECIPE_FILE, context)
        if recipe_path_str and Path(recipe_path_str).exists():
            recipe = CleaningRecipe.from_json(Path(recipe_path_str).read_text(encoding="utf-8"))
        else:
            crop_idx = self.parameterAsEnum(parameters, self.CROP, context)
            crop_code = self.CROPS[crop_idx] if 0 <= crop_idx < len(self.CROPS) else "corn"
            recipe = default_recipe_for_crop(crop_code)

        field_names = [f.name() for f in points.fields()]
        features: list[QgsFeature] = []
        obs_list: list[dict[str, Any]] = []

        for idx, feat in enumerate(points.getFeatures()):
            if feedback.isCanceled():
                break
            features.append(feat)
            obs: dict[str, Any] = {"source_index": idx}
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                obs["x"] = geom.asPoint().x()
                obs["y"] = geom.asPoint().y()
            for fname in field_names:
                v = feat[fname]
                if v is None or v == "" or str(v) == "NULL":
                    obs[fname] = None
                elif hasattr(v, "isNull") and v.isNull():
                    obs[fname] = None
                elif hasattr(v, "toString"):
                    obs[fname] = str(v.toString())
                elif hasattr(v, "isoformat"):
                    obs[fname] = str(v.isoformat())
                else:
                    obs[fname] = v
            obs_list.append(obs)

        result = run_cleaning_filters(obs_list, recipe)

        out_fields = self._output_fields(points.fields())
        all_sink, all_dest = self.parameterAsSink(
            parameters,
            self.ALL_OBSERVATIONS,
            context,
            out_fields,
            points.wkbType(),
            points.sourceCrs(),
        )
        acc_sink, acc_dest = self.parameterAsSink(
            parameters,
            self.ACCEPTED_OBSERVATIONS,
            context,
            out_fields,
            points.wkbType(),
            points.sourceCrs(),
        )
        exc_sink, exc_dest = self.parameterAsSink(
            parameters,
            self.EXCLUDED_OBSERVATIONS,
            context,
            out_fields,
            points.wkbType(),
            points.sourceCrs(),
        )

        fast_insert = enum_member(QgsFeatureSink, "Flag", "FastInsert")

        for idx, feat in enumerate(features):
            if feedback.isCanceled():
                break
            update = result.observation_updates[idx]
            out_feat = QgsFeature(out_fields)
            out_feat.setGeometry(feat.geometry())
            for fname in field_names:
                out_feat[fname] = feat[fname]
            for key, val in update.items():
                out_feat[key] = val

            all_sink.addFeature(out_feat, fast_insert)
            if update.get("clean_status") == "accepted":
                acc_sink.addFeature(out_feat, fast_insert)
            else:
                exc_sink.addFeature(out_feat, fast_insert)

        summary_path = Path(self.parameterAsFileOutput(parameters, self.SUMMARY_JSON, context))
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")

        recipe_out_path = Path(self.parameterAsFileOutput(parameters, self.RECIPE_JSON, context))
        recipe_out_path.parent.mkdir(parents=True, exist_ok=True)
        recipe_out_path.write_text(recipe.to_json(), encoding="utf-8")

        boundary_source = self.parameterAsSource(parameters, self.BOUNDARY, context)
        bnd_coords = None
        if boundary_source:
            try:
                from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
                wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                xform = QgsCoordinateTransform(boundary_source.sourceCrs(), wgs84_crs, QgsProject.instance())
                bnd_coords = []
                for b_feat in boundary_source.getFeatures():
                    geom = b_feat.geometry()
                    if geom and not geom.isEmpty():
                        geom_wgs = QgsGeometry(geom)
                        geom_wgs.transform(xform)
                        if geom_wgs.isMultipart():
                            for poly in geom_wgs.asMultiPolygon():
                                if poly and poly[0]:
                                    bnd_coords.append([(round(pt.y(), 6), round(pt.x(), 6)) for pt in poly[0]])
                        else:
                            poly = geom_wgs.asPolygon()
                            if poly and poly[0]:
                                bnd_coords.append([(round(pt.y(), 6), round(pt.x(), 6)) for pt in poly[0]])
            except Exception:
                bnd_coords = None

        review_out_path = Path(self.parameterAsFileOutput(parameters, self.REVIEW_HTML, context))
        review_out_path.parent.mkdir(parents=True, exist_ok=True)
        html_report = generate_html_review(
            run_name="Cleaning Run",
            field_name="Field",
            crop_code=recipe.crop_code,
            unit_profile=recipe.unit_profile,
            observations=obs_list,
            cleaning_result=result,
            analysis_crs=points.sourceCrs().authid() if points.sourceCrs().isValid() else "Unknown",
            boundary_coords=bnd_coords,
        )
        review_out_path.write_text(html_report, encoding="utf-8")

        return {
            self.ALL_OBSERVATIONS: all_dest,
            self.ACCEPTED_OBSERVATIONS: acc_dest,
            self.EXCLUDED_OBSERVATIONS: exc_dest,
            self.SUMMARY_JSON: str(summary_path),
            self.RECIPE_JSON: str(recipe_out_path),
            self.REVIEW_HTML: str(review_out_path),
        }
