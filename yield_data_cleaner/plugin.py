# SPDX-License-Identifier: GPL-3.0-or-later
"""QGIS plugin lifecycle and guided-workflow launch action."""

from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication

from .core.settings import PLUGIN_NAME
from .provider import YieldDataCleanerProvider
from .ui.inspection_dialog import YieldInputInspectionDialog


class YieldDataCleanerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.dialog = None

    def initProcessing(self):
        if self.provider is None:
            self.provider = YieldDataCleanerProvider()
            QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        if self.iface is None or self.action is not None:
            return
        icon = QIcon(str(Path(__file__).parent / "resources" / "icon.png"))
        self.action = QAction(icon, "Open Yield Data Cleaner...", self.iface.mainWindow())
        self.action.setObjectName("yieldDataCleanerInspectAction")
        self.action.setToolTip("Prepare yield monitor data for cleaning")
        self.action.triggered.connect(self.open_dialog)
        self.iface.addPluginToMenu(PLUGIN_NAME, self.action)
        self.iface.addToolBarIcon(self.action)

    def open_dialog(self):
        if self.dialog is None:
            self.dialog = YieldInputInspectionDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def unload(self):
        if self.dialog is not None:
            self.dialog.close()
            self.dialog.deleteLater()
            self.dialog = None
        if self.action is not None and self.iface is not None:
            self.iface.removePluginMenu(PLUGIN_NAME, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
