# SPDX-License-Identifier: GPL-3.0-or-later
"""Small dependency-free QGIS 3/QGIS 4 compatibility helpers."""

from __future__ import annotations

from typing import Any

from qgis.PyQt.QtCore import QMetaType, QVariant


def enum_member(owner: Any, enum_name: str, member_name: str) -> Any:
    scoped = getattr(owner, enum_name, None)
    if scoped is not None and hasattr(scoped, member_name):
        return getattr(scoped, member_name)
    return getattr(owner, member_name)


def qgis_field_type(name: str) -> Any:
    """Return the modern QMetaType field type with a Qt5 fallback."""

    modern_names = {
        "string": "QString",
        "integer": "LongLong",
        "double": "Double",
        "boolean": "Bool",
    }
    legacy_names = {
        "string": "String",
        "integer": "LongLong",
        "double": "Double",
        "boolean": "Bool",
    }
    scope = getattr(QMetaType, "Type", None)
    modern = modern_names[name]
    if scope is not None and hasattr(scope, modern):
        return getattr(scope, modern)
    return getattr(QVariant, legacy_names[name])
