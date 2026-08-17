# SPDX-License-Identifier: GPL-3.0-or-later
"""Interactive layer styling and symbology presets matching USDA Yield Editor."""

from __future__ import annotations

import math
from typing import Any

try:
    from qgis.PyQt.QtGui import QColor
except ImportError:
    try:
        from PyQt5.QtGui import QColor
    except ImportError:
        QColor = None


def get_status_symbol_config() -> dict[str, dict[str, Any]]:
    """Return styling configuration for clean status categories."""
    return {
        "accepted": {
            "label": "Accepted (Clean)",
            "color": "#2e7d32",
            "stroke": "#1b5e20",
            "size": 2.2,
        },
        "excluded": {
            "label": "Excluded (Filtered)",
            "color": "#d32f2f",
            "stroke": "#b71c1c",
            "size": 2.2,
        },
    }


def style_layer_with_attribute_and_ramp(
    layer: Any,
    target_field: str | None = None,
    ramp_name: str = "RdYlGn",
    classes: int = 5,
) -> bool:
    """Apply graduated symbology using a specific attribute and color ramp."""
    if layer is None or not hasattr(layer, "isValid") or not layer.isValid():
        return False

    try:
        from qgis.core import (
            QgsClassificationQuantile,
            QgsGradientColorRamp,
            QgsGraduatedSymbolRenderer,
            QgsMarkerSymbol,
            QgsRendererRange,
            QgsStyle,
        )

        layer_fields = [f.name() for f in layer.fields()]
        matched_field = None

        if target_field:
            for f in layer_fields:
                if f == target_field or f.lower() == target_field.lower():
                    matched_field = f
                    break

        if not matched_field:
            for candidate in (
                "yield_dry_mass_area",
                "dry_yield_mass_area",
                "yield_wet_mass_area",
                "wet_mass_area",
                "yield",
                "dry_yield",
                "elevation_m",
                "elevation",
                "moisture_pct",
                "speed_m_s",
                "swath_width_m",
            ):
                for f in layer_fields:
                    if f.lower() == candidate.lower():
                        matched_field = f
                        break
                if matched_field:
                    break

        if not matched_field:
            if layer_fields:
                matched_field = layer_fields[0]
            else:
                return False

        style = QgsStyle.defaultStyle()
        ramp = style.colorRamp(ramp_name)
        if ramp is None:
            ramp = style.colorRamp("RdYlGn")
        if ramp is None:
            ramp = QgsGradientColorRamp(QColor(239, 68, 68), QColor(34, 197, 94))

        renderer = QgsGraduatedSymbolRenderer()
        renderer.setClassAttribute(matched_field)
        renderer.setClassificationMethod(QgsClassificationQuantile())
        renderer.setSourceColorRamp(ramp.clone())
        renderer.updateClasses(layer, classes)

        ranges = renderer.ranges()
        if not ranges or len(ranges) < 2:
            # Manual quantile/equal-interval range fallback
            vals = []
            for feat in layer.getFeatures():
                v = feat[matched_field]
                if v is not None:
                    try:
                        num = float(v)
                        if not math.isnan(num) and not math.isinf(num):
                            vals.append(num)
                    except (ValueError, TypeError):
                        pass
            if vals:
                min_v = min(vals)
                max_v = max(vals)
                if min_v == max_v:
                    max_v += 1.0
                step = (max_v - min_v) / classes
                new_ranges = []
                for i in range(classes):
                    r_min = min_v + i * step
                    r_max = min_v + (i + 1) * step
                    ratio = (i + 0.5) / classes
                    c = ramp.color(ratio)
                    sym = QgsMarkerSymbol.createSimple({
                        "name": "circle",
                        "size": "2.2",
                        "color": c.name(),
                        "outline_color": "#1e293b",
                        "outline_width": "0.2",
                    })
                    new_ranges.append(QgsRendererRange(r_min, r_max, sym, f"{r_min:.2f} - {r_max:.2f}"))
                renderer = QgsGraduatedSymbolRenderer(matched_field, new_ranges)
                renderer.setSourceColorRamp(ramp.clone())
        else:
            for i, r in enumerate(ranges):
                ratio = (i + 0.5) / len(ranges)
                color = ramp.color(ratio)
                sym = QgsMarkerSymbol.createSimple({
                    "name": "circle",
                    "size": "2.2",
                    "color": color.name(),
                    "outline_color": "#1e293b",
                    "outline_width": "0.2",
                })
                r.setSymbol(sym)

        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return True
    except Exception:
        return False


def style_layer_for_display(layer: Any, mode: str = "yield") -> bool:
    """Apply graduated or categorized symbology to a QGIS layer.
    
    Safe to call in both GUI and headless environments.
    """
    if layer is None or not hasattr(layer, "isValid") or not layer.isValid():
        return False

    try:
        from qgis.core import (
            QgsCategorizedSymbolRenderer,
            QgsMarkerSymbol,
            QgsRendererCategory,
        )

        fields = [f.name() for f in layer.fields()]

        if mode == "status" and "clean_status" in fields:
            categories = []
            cfg = get_status_symbol_config()
            for val, props in cfg.items():
                sym = QgsMarkerSymbol.createSimple({
                    "name": "circle",
                    "color": props["color"],
                    "outline_color": props["stroke"],
                    "outline_width": "0.4",
                    "size": str(props["size"]),
                })
                cat = QgsRendererCategory(val, sym, props["label"])
                categories.append(cat)
            renderer = QgsCategorizedSymbolRenderer("clean_status", categories)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
            return True

        # Graduated attribute modes
        target_field = None
        ramp_name = "RdYlGn"
        if mode == "yield":
            for candidate in (
                "yield_dry_mass_area",
                "dry_yield_mass_area",
                "yield_wet_mass_area",
                "wet_mass_area",
                "yield",
                "dry_yield",
            ):
                if candidate in fields:
                    target_field = candidate
                    ramp_name = "RdYlGn"
                    break
        elif mode == "moisture":
            for candidate in ("moisture_pct", "moisture"):
                if candidate in fields:
                    target_field = candidate
                    ramp_name = "Blues"
                    break
        elif mode == "velocity":
            for candidate in ("speed_m_s", "speed", "velocity"):
                if candidate in fields:
                    target_field = candidate
                    ramp_name = "Viridis"
                    break
        elif mode == "swath":
            for candidate in ("swath_width_m", "swath_width", "swath"):
                if candidate in fields:
                    target_field = candidate
                    ramp_name = "Spectral"
                    break

        return style_layer_with_attribute_and_ramp(layer, target_field, ramp_name)

    except Exception:
        return False


def get_layer_graduated_legend_items(layer: Any) -> list[dict[str, Any]]:
    """Extract legend items (color, label, lower, upper) from graduated or categorized layer renderer."""
    if layer is None or not hasattr(layer, "renderer") or not hasattr(layer, "isValid") or not layer.isValid():
        return []
    items = []
    try:
        renderer = layer.renderer()
        if hasattr(renderer, "ranges"):
            for r in renderer.ranges():
                color_hex = "#3388ff"
                sym = r.symbol()
                if sym and hasattr(sym, "color"):
                    color_hex = sym.color().name()
                label = r.label() or f"{r.lowerValue():.1f} – {r.upperValue():.1f}"
                items.append({
                    "color": color_hex,
                    "label": label,
                    "lower": r.lowerValue(),
                    "upper": r.upperValue(),
                })
        elif hasattr(renderer, "categories"):
            for cat in renderer.categories():
                color_hex = "#3388ff"
                sym = cat.symbol()
                if sym and hasattr(sym, "color"):
                    color_hex = sym.color().name()
                label = cat.label() or str(cat.value())
                items.append({
                    "color": color_hex,
                    "label": label,
                })
    except Exception:
        pass
    return items
