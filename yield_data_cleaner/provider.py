# SPDX-License-Identifier: GPL-3.0-or-later
"""Processing provider for Yield Data Cleaner."""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingProvider

from .algorithms.classify_by_boundary import ClassifyByBoundaryAlgorithm
from .algorithms.clean_yield_data import CleanYieldDataAlgorithm
from .algorithms.create_canonical_audit import CreateCanonicalAuditAlgorithm
from .algorithms.export_adapt import ExportAdaptAlgorithm
from .algorithms.inspect_yield_columns import InspectYieldDataAlgorithm
from .algorithms.prepare_field_boundary import PrepareFieldBoundaryAlgorithm
from .algorithms.reconstruct_passes import ReconstructPassesAlgorithm
from .core.settings import PROVIDER_ID, PROVIDER_NAME


class YieldDataCleanerProvider(QgsProcessingProvider):
    def id(self):
        return PROVIDER_ID

    def name(self):
        return QCoreApplication.translate("YieldDataCleanerProvider", PROVIDER_NAME)

    def longName(self):
        return self.name()

    def loadAlgorithms(self):
        self.addAlgorithm(InspectYieldDataAlgorithm())
        self.addAlgorithm(CreateCanonicalAuditAlgorithm())
        self.addAlgorithm(PrepareFieldBoundaryAlgorithm())
        self.addAlgorithm(ClassifyByBoundaryAlgorithm())
        self.addAlgorithm(ReconstructPassesAlgorithm())
        self.addAlgorithm(CleanYieldDataAlgorithm())
        self.addAlgorithm(ExportAdaptAlgorithm())
