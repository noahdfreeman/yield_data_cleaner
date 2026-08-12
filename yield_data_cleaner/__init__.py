# SPDX-License-Identifier: GPL-3.0-or-later
"""QGIS entry point for Yield Data Cleaner."""


def classFactory(iface):
    """Return the plugin lifecycle object requested by QGIS."""

    from .plugin import YieldDataCleanerPlugin

    return YieldDataCleanerPlugin(iface)
