# SPDX-License-Identifier: GPL-3.0-or-later
"""Processing algorithm to export cleaned yield data to AgGateway ADAPT Standard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)

from ..compat import enum_member
from ..core.filter_engine import CleaningRunResult
from ..exporters.adapt_standard import export_adapt_standard_package


class ExportAdaptAlgorithm(QgsProcessingAlgorithm):
    POINTS = "POINTS"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    FIELD_NAME = "FIELD_NAME"
    CROP = "CROP"
    GROWER_NAME = "GROWER_NAME"
    FARM_NAME = "FARM_NAME"

    CROPS = ("corn", "soybean", "wheat")

    @staticmethod
    def tr(message: str) -> str:
        return QCoreApplication.translate("ExportAdaptAlgorithm", message)

    def name(self) -> str:
        return "export_adapt"

    def displayName(self) -> str:
        return self.tr("Export cleaned yield data to ADAPT Standard")

    def group(self) -> str:
        return self.tr("Export")

    def groupId(self) -> str:
        return "export"

    def shortHelpString(self) -> str:
        return self.tr(
            "Export cleaned yield observations, swath coverage footprints, and operation "
            "metadata as an AgGateway ADAPT Standard JSON package."
        )

    def createInstance(self) -> ExportAdaptAlgorithm:
        return ExportAdaptAlgorithm()

    def initAlgorithm(self, config=None):
        del config
        point_type = enum_member(QgsProcessing, "SourceType", "TypeVectorPoint")

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINTS,
                self.tr("Cleaned or canonical yield observations"),
                types=[point_type],
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.FIELD_NAME,
                self.tr("Field name"),
                defaultValue="Field_1",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CROP,
                self.tr("Crop type"),
                options=[self.tr("Corn"), self.tr("Soybean"), self.tr("Wheat")],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.GROWER_NAME,
                self.tr("Grower name"),
                defaultValue="Default Grower",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.FARM_NAME,
                self.tr("Farm name"),
                defaultValue="Default Farm",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_FOLDER,
                self.tr("ADAPT package manifest output"),
                fileFilter=self.tr("JSON files (*.json)"),
                defaultValue="adapt_manifest.json",
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        points = self.parameterAsSource(parameters, self.POINTS, context)
        if points is None:
            raise QgsProcessingException("Point observations layer is required")

        field_name = self.parameterAsString(parameters, self.FIELD_NAME, context)
        crop_idx = self.parameterAsEnum(parameters, self.CROP, context)
        crop_code = self.CROPS[crop_idx] if 0 <= crop_idx < len(self.CROPS) else "corn"
        grower = self.parameterAsString(parameters, self.GROWER_NAME, context) or "Default Grower"
        farm = self.parameterAsString(parameters, self.FARM_NAME, context) or "Default Farm"

        manifest_out = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_FOLDER, context))
        target_dir = manifest_out.parent if manifest_out.name == "adapt_manifest.json" else manifest_out

        field_names = [f.name() for f in points.fields()]
        obs_list: list[dict[str, Any]] = []

        for idx, feat in enumerate(points.getFeatures()):
            if feedback.isCanceled():
                break
            obs: dict[str, Any] = {"source_index": idx}
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                obs["x"] = geom.asPoint().x()
                obs["y"] = geom.asPoint().y()
            for fname in field_names:
                obs[fname] = feat[fname]
            obs_list.append(obs)

        # Build simulated cleaning result if not already marked
        updates = []
        for obs in obs_list:
            st = obs.get("clean_status", "accepted")
            updates.append({"clean_status": st})

        cleaning_res = CleaningRunResult(
            total_observations=len(obs_list),
            accepted_count=sum(1 for u in updates if u["clean_status"] == "accepted"),
            excluded_count=sum(1 for u in updates if u["clean_status"] != "accepted"),
            observation_updates=updates,
        )

        summary = export_adapt_standard_package(
            target_dir=target_dir,
            field_name=field_name,
            crop_code=crop_code,
            observations=obs_list,
            cleaning_result=cleaning_res,
            grower_name=grower,
            farm_name=farm,
            analysis_crs=points.sourceCrs().authid() if points.sourceCrs().isValid() else "EPSG:4326",
        )

        return {
            self.OUTPUT_FOLDER: summary.manifest_path,
        }
