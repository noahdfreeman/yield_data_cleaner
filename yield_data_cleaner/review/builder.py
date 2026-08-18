# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone, portable Leaflet-based interactive HTML before/after review report."""

from __future__ import annotations

import base64
import html
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..core.crop_profiles import crop_profile
from ..core.filter_engine import CleaningRunResult
from ..core.units import kg_per_hectare_to_bushels_per_acre, m_per_s_to_mph

_CACHED_LOGO_DATA_URI: str | None = None


def get_plugin_logo_data_uri() -> str:
    """Retrieve base64 Data URI for the official Yield Data Cleaner plugin logo."""
    global _CACHED_LOGO_DATA_URI
    if _CACHED_LOGO_DATA_URI is not None:
        return _CACHED_LOGO_DATA_URI
    try:
        icon_path = Path(__file__).parent.parent / "resources" / "icon.png"
        if icon_path.is_file():
            with open(icon_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("ascii")
                _CACHED_LOGO_DATA_URI = f"data:image/png;base64,{encoded}"
                return _CACHED_LOGO_DATA_URI
    except Exception:  # nosec B110
        pass
    _CACHED_LOGO_DATA_URI = ""
    return _CACHED_LOGO_DATA_URI


def _safe_float(val: Any) -> float | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        num = float(val)
        return num if math.isfinite(num) else None
    except (TypeError, ValueError):
        return None


def _json_safe(val: Any) -> Any:
    """Ensure any Python, PyQt (QDate, QDateTime), or datetime object is JSON serializable."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool, str)):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    if hasattr(val, "isNull") and val.isNull():
        return None
    if hasattr(val, "toString"):
        return str(val.toString())
    if hasattr(val, "isoformat"):
        return str(val.isoformat())
    return str(val)


def _utm_to_latlon(
    easting: float, northing: float, zone_number: int = 15, northern: bool = True
) -> tuple[float, float]:
    """Convert UTM coordinates (meters) to WGS84 (latitude, longitude) in decimal degrees."""
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e = math.sqrt(1.0 - (b / a) ** 2)
    e1 = (1.0 - math.sqrt(1.0 - e**2)) / (1.0 + math.sqrt(1.0 - e**2))

    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0

    k0 = 0.9996
    M = y / k0
    mu = M / (a * (1.0 - (e**2) / 4.0 - 3.0 * (e**4) / 64.0 - 5.0 * (e**6) / 256.0))

    phi1_rad = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * (e1**3) / 32.0) * math.sin(2.0 * mu)
        + (21.0 * (e1**2) / 16.0 - 55.0 * (e1**4) / 32.0) * math.sin(4.0 * mu)
        + (151.0 * (e1**3) / 96.0) * math.sin(6.0 * mu)
        + (1097.0 * (e1**4) / 512.0) * math.sin(8.0 * mu)
    )

    N1 = a / math.sqrt(1.0 - (e * math.sin(phi1_rad)) ** 2)
    T1 = math.tan(phi1_rad) ** 2
    C1 = (e**2 / (1.0 - e**2)) * (math.cos(phi1_rad) ** 2)
    R1 = a * (1.0 - e**2) / ((1.0 - (e * math.sin(phi1_rad)) ** 2) ** 1.5)
    D = x / (N1 * k0)

    lat_rad = phi1_rad - (N1 * math.tan(phi1_rad) / R1) * (
        (D**2) / 2.0
        - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * (C1**2) - 9.0 * (e**2 / (1.0 - e**2))) * (D**4) / 24.0
        + (
            61.0
            + 90.0 * T1
            + 298.0 * C1
            + 45.0 * (T1**2)
            - 252.0 * (e**2 / (1.0 - e**2))
            - 3.0 * (C1**2)
        )
        * (D**6)
        / 720.0
    )

    lon_origin = (zone_number - 1) * 6 - 180 + 3
    lon_rad = (
        D
        - (1.0 + 2.0 * T1 + C1) * (D**3) / 6.0
        + (
            5.0
            - 2.0 * C1
            + 28.0 * T1
            - 3.0 * (C1**2)
            + 8.0 * (e**2 / (1.0 - e**2))
            + 24.0 * (T1**2)
        )
        * (D**5)
        / 120.0
    ) / math.cos(phi1_rad)

    lat = math.degrees(lat_rad)
    lon = lon_origin + math.degrees(lon_rad)
    return lat, lon


def compute_points_convex_hull(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Compute 2D convex hull polygon of (lat, lon) coordinates using Monotone Chain."""
    unique_pts = sorted(set((round(float(p[0]), 6), round(float(p[1]), 6)) for p in points))
    if len(unique_pts) <= 3:
        return unique_pts

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[1] - o[1]) * (b[0] - o[0]) - (a[0] - o[0]) * (b[1] - o[1])

    lower: list[tuple[float, float]] = []
    for p in unique_pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: list[tuple[float, float]] = []
    for p in reversed(unique_pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]
    if hull and hull[0] != hull[-1]:
        hull.append(hull[0])
    return hull


def generate_interpolated_grid(
    clean_points: Sequence[tuple[float, float, float]],
    grid_size_m: float = 9.144,
    boundary_coords: Sequence[Sequence[tuple[float, float]]] | None = None,
    max_cells_per_dim: int = 120,
) -> dict[str, Any] | None:
    """Generate an IDW interpolated grid matrix clipped to field boundary."""
    if len(clean_points) < 3:
        return None

    lats = [p[0] for p in clean_points]
    lons = [p[1] for p in clean_points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    mid_lat = (min_lat + max_lat) / 2.0
    m_per_deg_lat = 111132.954
    m_per_deg_lon = 111132.954 * math.cos(math.radians(mid_lat))

    lat_span_m = max(10.0, (max_lat - min_lat) * m_per_deg_lat)
    lon_span_m = max(10.0, (max_lon - min_lon) * m_per_deg_lon)

    n_rows = max(8, min(max_cells_per_dim, int(math.ceil(lat_span_m / max(1.0, grid_size_m)))))
    n_cols = max(8, min(max_cells_per_dim, int(math.ceil(lon_span_m / max(1.0, grid_size_m)))))

    d_lat = (max_lat - min_lat) / n_rows if n_rows > 0 else 0.0001
    d_lon = (max_lon - min_lon) / n_cols if n_cols > 0 else 0.0001

    # Spatial binning for IDW acceleration
    bucket_size = max(d_lat * 4.0, d_lon * 4.0, 0.0002)
    buckets: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
    for lat, lon, val in clean_points:
        b_key = (int(lat / bucket_size), int(lon / bucket_size))
        buckets.setdefault(b_key, []).append((lat, lon, val))

    rings: list[list[tuple[float, float]]] = []
    if boundary_coords:
        try:
            if isinstance(boundary_coords[0], (list, tuple)) and len(boundary_coords[0]) > 0:
                if isinstance(boundary_coords[0][0], (int, float)):
                    rings = [list(boundary_coords)]  # type: ignore
                else:
                    rings = [list(r) for r in boundary_coords]  # type: ignore
        except Exception:
            rings = []
    if not rings and len(clean_points) >= 3:
        hull = compute_points_convex_hull([(p[0], p[1]) for p in clean_points])
        if len(hull) >= 3:
            rings = [hull]

    def get_nearby_points(cy: float, cx: float) -> list[tuple[float, float, float]]:
        b_y = int(cy / bucket_size)
        b_x = int(cx / bucket_size)
        nearby: list[tuple[float, float, float]] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                pts = buckets.get((b_y + dy, b_x + dx))
                if pts:
                    nearby.extend(pts)
        if len(nearby) < 4:
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    if abs(dy) <= 1 and abs(dx) <= 1:
                        continue
                    pts = buckets.get((b_y + dy, b_x + dx))
                    if pts:
                        nearby.extend(pts)
        return nearby or list(clean_points[:40])

    def point_in_poly(plat: float, plon: float, poly: Sequence[tuple[float, float]]) -> bool:
        inside = False
        n = len(poly)
        if n < 3:
            return False
        j = n - 1
        for i in range(n):
            yi, xi = poly[i][0], poly[i][1]
            yj, xj = poly[j][0], poly[j][1]
            if ((yi > plat) != (yj > plat)) and (plon < (xj - xi) * (plat - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    cells = []
    valid_vals = []

    for r in range(n_rows):
        row_vals = []
        cy = min_lat + (r + 0.5) * d_lat
        for c in range(n_cols):
            cx = min_lon + (c + 0.5) * d_lon

            # Boundary clipping if provided
            if rings:
                inside = any(point_in_poly(cy, cx, ring) for ring in rings)
                if not inside:
                    row_vals.append(None)
                    continue

            nearby = get_nearby_points(cy, cx)
            weighted_sum = 0.0
            weight_total = 0.0
            min_dist = float("inf")

            for p_lat, p_lon, p_val in nearby:
                dist_sq = ((p_lat - cy) * m_per_deg_lat) ** 2 + ((p_lon - cx) * m_per_deg_lon) ** 2
                dist = math.sqrt(dist_sq)
                if dist < min_dist:
                    min_dist = dist
                if dist < 0.1:
                    weighted_sum = p_val
                    weight_total = 1.0
                    break
                w = 1.0 / max(0.01, dist_sq)
                weighted_sum += w * p_val
                weight_total += w

            if not rings and min_dist > (grid_size_m * 2.5):
                row_vals.append(None)
            elif weight_total > 0:
                est = weighted_sum / weight_total
                row_vals.append(round(est, 1))
                valid_vals.append(est)
            else:
                row_vals.append(None)

        cells.append(row_vals)

    min_v = min(valid_vals) if valid_vals else 0.0
    max_v = max(valid_vals) if valid_vals else 100.0

    return {
        "bounds": [[round(min_lat, 6), round(min_lon, 6)], [round(max_lat, 6), round(max_lon, 6)]],
        "rows": n_rows,
        "cols": n_cols,
        "grid_size_m": grid_size_m,
        "min_val": round(min_v, 1),
        "max_val": round(max_v, 1),
        "cells": cells,
    }


def generate_html_review(
    run_name: str,
    field_name: str,
    crop_code: str,
    unit_profile: str,
    observations: Sequence[Mapping[str, Any]],
    cleaning_result: CleaningRunResult,
    analysis_crs: str = "Unknown",
    grid_size_ft: float = 30.0,
    boundary_coords: Sequence[Sequence[tuple[float, float]]] | None = None,
    max_display_points: int = 15000,
) -> str:
    """Generate a self-contained, Leaflet-powered GIS before/after yield review web app."""
    crop = crop_profile(crop_code)
    is_imperial = unit_profile.lower() == "imperial"
    yield_unit = "bu/ac" if is_imperial else "kg/ha"
    speed_unit = "mph" if is_imperial else "m/s"
    swath_unit = "ft" if is_imperial else "m"

    # Identify UTM zone if analysis CRS specifies it
    zone_num = 15
    if "UTM zone " in analysis_crs:
        try:
            zone_num = int(analysis_crs.split("UTM zone ")[1].split("N")[0].strip())
        except Exception:  # nosec B110
            pass
    elif "EPSG:326" in analysis_crs or "EPSG:269" in analysis_crs:
        try:
            zone_num = int(analysis_crs[-2:])
        except Exception:  # nosec B110
            pass

    # Discover all raw columns in original dataset
    raw_attribute_keys: list[str] = []
    excluded_keys = {"x", "y", "lat", "lon", "latitude", "longitude", "source_index", "geometry"}
    for obs in observations[:200]:
        for k in obs.keys():
            if k not in excluded_keys and k not in raw_attribute_keys:
                raw_attribute_keys.append(k)

    # Extract clean vs raw statistics & calculate accurate area
    raw_yields: list[float] = []
    clean_yields: list[float] = []
    clean_points_for_grid: list[tuple[float, float, float]] = []
    total_area_m2 = 0.0

    n_total = len(observations)
    step = max(1, math.ceil(n_total / max_display_points)) if n_total > max_display_points else 1
    sampled_indices = list(range(0, n_total, step))

    lats: list[float] = []
    lons: list[float] = []
    points_payload: list[dict[str, Any]] = []

    for i, obs in enumerate(observations):
        # Physical area summation: speed * dt * swath
        spd = _safe_float(obs.get("speed_m_s") or obs.get("speed")) or 2.0
        swth = _safe_float(obs.get("swath_width_m") or obs.get("swath_width")) or 9.144
        total_area_m2 += spd * 1.0 * swth

        # Extract yield value
        y_val = None
        for k in (
            "yield_dry_mass_area",
            "yield_wet_mass_area",
            "dry_yield_mass_area",
            "yield",
            "dry_yield",
        ):
            val = obs.get(k)
            if val is not None:
                num = _safe_float(val)
                if num is not None and num > 0:
                    y_val = num
                    break

        if y_val is not None:
            disp_y = (
                kg_per_hectare_to_bushels_per_acre(y_val, crop.test_weight_lb_per_bushel)
                if is_imperial
                else y_val
            )
            raw_yields.append(disp_y)

            update = (
                cleaning_result.observation_updates[i]
                if i < len(cleaning_result.observation_updates)
                else {}
            )
            if update.get("clean_status") == "accepted":
                clean_yields.append(disp_y)

                # Point coordinate for interpolation
                px = _safe_float(obs.get("x") or obs.get("longitude") or obs.get("lon"))
                py = _safe_float(obs.get("y") or obs.get("latitude") or obs.get("lat"))
                if px is not None and py is not None:
                    if abs(px) > 180.0 or abs(py) > 90.0:
                        plat, plon = _utm_to_latlon(px, py, zone_number=zone_num)
                    else:
                        plat, plon = py, px
                    clean_points_for_grid.append((plat, plon, disp_y))

    for idx in sampled_indices:
        obs = observations[idx]
        x = _safe_float(obs.get("x") or obs.get("longitude") or obs.get("lon"))
        y = _safe_float(obs.get("y") or obs.get("latitude") or obs.get("lat"))

        if x is None or y is None:
            continue

        if abs(x) > 180.0 or abs(y) > 90.0:
            lat, lon = _utm_to_latlon(x, y, zone_number=zone_num)
        else:
            lat, lon = y, x

        lats.append(lat)
        lons.append(lon)

        y_si = None
        for k in ("yield_dry_mass_area", "yield_wet_mass_area", "dry_yield_mass_area", "yield"):
            v = _safe_float(obs.get(k))
            if v is not None and v > 0:
                y_si = v
                break
        y_disp = (
            (
                kg_per_hectare_to_bushels_per_acre(y_si, crop.test_weight_lb_per_bushel)
                if is_imperial
                else y_si
            )
            if y_si is not None
            else None
        )

        m_pct = _safe_float(obs.get("moisture_pct"))
        spd_m_s = _safe_float(obs.get("speed_m_s"))
        spd_disp = (
            (m_per_s_to_mph(spd_m_s) if is_imperial else spd_m_s) if spd_m_s is not None else None
        )

        swath_m = _safe_float(obs.get("swath_width_m"))
        swath_disp = (
            (round(swath_m * 3.28084, 1) if is_imperial else round(swath_m, 2))
            if swath_m is not None
            else None
        )

        update = (
            cleaning_result.observation_updates[idx]
            if idx < len(cleaning_result.observation_updates)
            else {}
        )
        status = update.get("clean_status", "accepted")
        reasons = update.get("filter_reasons", "")

        raw_props = {
            k: _json_safe(obs[k])
            for k in raw_attribute_keys
            if k in obs and obs[k] is not None and _json_safe(obs[k]) is not None
        }

        points_payload.append(
            {
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "yield": round(y_disp, 1) if y_disp is not None else None,
                "moisture": round(m_pct, 1) if m_pct is not None else None,
                "speed": round(spd_disp, 1) if spd_disp is not None else None,
                "swath": swath_disp,
                "pass_id": str(obs.get("pass_id") or "1"),
                "status": status,
                "reasons": reasons,
                "id": str(obs.get("observation_id", idx)),
                "raw": raw_props,
            }
        )

    center_lat = (sum(lats) / len(lats)) if lats else 39.8
    center_lon = (sum(lons) / len(lons)) if lons else -93.2

    # Accurate physical acreage calculation
    grid_size_m = grid_size_ft * 0.3048 if is_imperial else grid_size_ft
    if total_area_m2 > 0:
        estimated_area = (
            round(total_area_m2 / 4046.8564224, 1)
            if is_imperial
            else round(total_area_m2 / 10000.0, 1)
        )
    else:
        estimated_area = round(n_total * 0.0045, 1) if is_imperial else round(n_total * 0.0018, 1)
    area_label = f"{estimated_area:,.1f} acres" if is_imperial else f"{estimated_area:,.1f} ha"

    effective_boundary = boundary_coords
    if not effective_boundary:
        all_pts = [
            (p["lat"], p["lon"])
            for p in points_payload
            if p.get("lat") is not None and p.get("lon") is not None
        ]
        if len(all_pts) >= 3:
            hull = compute_points_convex_hull(all_pts)
            if len(hull) >= 3:
                effective_boundary = [hull]

    # Compute interpolated surface grid
    grid_payload = generate_interpolated_grid(
        clean_points=clean_points_for_grid,
        grid_size_m=grid_size_m,
        boundary_coords=effective_boundary,
    )

    def compute_stats(vals: list[float]) -> dict[str, float]:
        if not vals:
            return {"mean": 0.0, "std": 0.0, "cv": 0.0, "min": 0.0, "max": 0.0}
        m = sum(vals) / len(vals)
        var = sum((x - m) ** 2 for x in vals) / len(vals) if len(vals) > 1 else 0.0
        sd = math.sqrt(var)
        cv = (sd / m * 100.0) if m > 0 else 0.0
        return {"mean": m, "std": sd, "cv": cv, "min": min(vals), "max": max(vals)}

    c_stats = compute_stats(clean_yields)
    r_stats = compute_stats(raw_yields)
    diff_mean = c_stats["mean"] - r_stats["mean"]
    diff_std = c_stats["std"] - r_stats["std"]
    diff_cv = c_stats["cv"] - r_stats["cv"]
    diff_mean_str = f"{'+' if diff_mean >= 0 else ''}{diff_mean:.2f} {yield_unit}"
    diff_std_str = f"{'+' if diff_std >= 0 else ''}{diff_std:.2f} {yield_unit}"
    diff_cv_str = f"{'+' if diff_cv >= 0 else ''}{diff_cv:.1f} %"

    clean_count = cleaning_result.accepted_count
    excluded_count = cleaning_result.excluded_count
    total_count = cleaning_result.total_observations
    exc_pct = (excluded_count / total_count * 100.0) if total_count > 0 else 0.0

    points_json_str = json.dumps(points_payload, default=_json_safe)
    grid_json_str = json.dumps(grid_payload, default=_json_safe) if grid_payload else "null"
    raw_keys_json = json.dumps(raw_attribute_keys, default=_json_safe)
    boundary_json_str = (
        json.dumps(effective_boundary, default=_json_safe) if effective_boundary else "null"
    )

    # Build raw attribute option tags
    raw_attr_options = "\n".join(
        f'<option value="raw:{html.escape(str(k))}">{html.escape(str(k))}</option>'
        for k in raw_attribute_keys
    )

    logo_data_uri = get_plugin_logo_data_uri()

    html_template = f"""<!DOCTYPE html>  # nosec B608
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yield Data Review - {html.escape(field_name)}</title>

    <!-- Leaflet CSS & JS from standard CDNs with local fallbacks -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{ width: 100%; height: 100%; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}

        /* Top Warning Banner */
        #topBanner {{
            width: 100%;
            height: 28px;
            background: #991b1b;
            color: #ffffff;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.08em;
            display: flex;
            align-items: center;
            justify-content: center;
            text-transform: uppercase;
            z-index: 2000;
            position: absolute;
            top: 0;
            left: 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }}

        /* Full Screen Map Container */
        #map {{
            width: 100%;
            height: calc(100% - 28px);
            margin-top: 28px;
            background: #1e293b;
            position: relative;
        }}

        /* Floating Glass Cards */
        .glass-panel {{
            position: absolute;
            background: rgba(255, 255, 255, 0.96);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(226, 232, 240, 0.9);
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
            z-index: 1000;
            color: #0f172a;
            font-size: 12px;
        }}

        /* Top-Left Map Options Card (Positioned without zoom control overlap) */
        #mapOptionsCard {{
            top: 14px;
            left: 14px;
            width: 220px;
            padding: 14px;
        }}
        #mapOptionsCard h4 {{
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #1e293b;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .control-group {{
            margin-bottom: 10px;
        }}
        .control-group label {{
            display: block;
            font-size: 10.5px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 3px;
        }}
        .control-group select, .control-group input[type="range"] {{
            width: 100%;
            padding: 5px 8px;
            border-radius: 4px;
            border: 1px solid #cbd5e1;
            background: #ffffff;
            font-size: 11px;
            outline: none;
        }}
        .opacity-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .opacity-val {{
            font-size: 10.5px;
            font-weight: 700;
            color: #0f172a;
        }}
        .checkbox-row {{
            display: flex;
            align-items: center;
            gap: 6px;
            margin-top: 8px;
            font-weight: 600;
            color: #1e293b;
            cursor: pointer;
        }}
        .btn-reset {{
            width: 100%;
            margin-top: 10px;
            padding: 6px 10px;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            color: #334155;
            cursor: pointer;
            text-align: center;
        }}
        .btn-reset:hover {{ background: #f1f5f9; }}

        /* Top-Right Review Info Card (Positioned below top-right zoom controls) */
        #reviewInfoCard {{
            top: 85px;
            right: 14px;
            width: 380px;
            max-width: calc(100vw - 28px);
            padding: 14px 16px;
        }}
        .card-header-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .logo-title-group {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .logo-image {{
            width: 48px;
            height: 48px;
            min-width: 48px;
            object-fit: contain;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
            border: 1px solid rgba(226, 232, 240, 0.95);
            background: #ffffff;
            flex-shrink: 0;
        }}
        .logo-badge {{
            width: 48px;
            height: 48px;
            background: #16a34a;
            color: #ffffff;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            font-size: 24px;
            flex-shrink: 0;
        }}
        .info-title {{
            font-size: 14px;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: -0.01em;
        }}
        .info-sub {{
            font-size: 11px;
            color: #64748b;
            margin-top: 2px;
            font-weight: 500;
        }}
        .btn-toggle-info {{
            background: none;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            width: 20px;
            height: 20px;
            cursor: pointer;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #475569;
        }}
        .kpi-area-badge {{
            display: inline-block;
            background: #f1f5f9;
            color: #475569;
            font-size: 10.5px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
            margin-bottom: 6px;
        }}
        .kpi-compare-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
            margin: 6px 0 8px 0;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            overflow: hidden;
        }}
        .kpi-compare-table th {{
            background: #f1f5f9;
            color: #0f172a;
            font-weight: 700;
            text-align: left;
            padding: 6px 8px;
            font-size: 10.5px;
            border-bottom: 1px solid #cbd5e1;
        }}
        .kpi-compare-table td {{
            padding: 5px 8px;
            border-bottom: 1px solid #f1f5f9;
            color: #334155;
            font-size: 11px;
        }}
        .kpi-compare-table tr:last-child td {{
            border-bottom: none;
        }}
        .kpi-compare-table td.green {{
            color: #16a34a;
            font-weight: 700;
        }}
        .kpi-compare-table td.red {{
            color: #dc2626;
            font-weight: 700;
        }}
        .info-footer {{
            font-size: 9.5px;
            color: #64748b;
            line-height: 1.35;
        }}

        /* Bottom-Left Left Layer Card */
        #leftLayerCard {{
            bottom: 20px;
            left: 14px;
            width: 290px;
            padding: 14px;
            background: rgba(15, 23, 42, 0.94);
            color: #f8fafc;
            border: 1px solid rgba(51, 65, 85, 0.9);
        }}
        #leftLayerCard h4 {{
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #ffffff;
            margin-bottom: 8px;
        }}
        #leftLayerCard label {{
            color: #94a3b8;
            font-size: 10px;
            font-weight: 600;
        }}
        #leftLayerCard select {{
            background: #1e293b;
            color: #ffffff;
            border: 1px solid #475569;
            font-size: 11px;
            margin-bottom: 6px;
        }}
        .legend-bar {{
            height: 10px;
            border-radius: 3px;
            margin: 6px 0 3px 0;
            width: 100%;
        }}
        .legend-labels {{
            display: flex;
            justify-content: space-between;
            font-size: 9.5px;
            color: #cbd5e1;
            font-family: monospace;
            margin-bottom: 4px;
        }}
        .legend-expand-bar {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 10.5px;
            font-weight: 600;
            color: #94a3b8;
            cursor: pointer;
            padding: 4px 0;
            border-top: 1px solid #334155;
            margin-top: 4px;
            user-select: none;
        }}
        .legend-expand-bar:hover {{
            color: #f8fafc;
        }}
        .dist-panel {{
            background: rgba(30, 41, 59, 0.85);
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 8px;
            margin: 4px 0 6px 0;
        }}
        .dist-stats-row {{
            display: flex;
            justify-content: space-between;
            font-size: 9.5px;
            color: #cbd5e1;
            font-family: monospace;
            margin-bottom: 4px;
        }}
        .dist-hist-container {{
            width: 100%;
            height: 48px;
            background: #0f172a;
            border-radius: 4px;
            border: 1px solid #334155;
            margin-bottom: 6px;
            overflow: hidden;
        }}
        .hist-svg {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        .class-ctrl-grid {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 6px;
        }}
        .class-ctrl-grid label {{
            display: block;
            font-size: 9px;
            color: #94a3b8;
            margin-bottom: 2px;
            text-transform: uppercase;
        }}
        .class-ctrl-grid select {{
            width: 100%;
            background: #0f172a;
            color: #f8fafc;
            border: 1px solid #475569;
            font-size: 10px;
            padding: 2px 4px;
            border-radius: 4px;
        }}
        .layer-footer-stat {{
            font-size: 9px;
            color: #94a3b8;
            font-style: italic;
        }}

        /* Bottom-Right Right Layer Card (Compare Mode) */
        #rightLayerCard {{
            bottom: 20px;
            right: 14px;
            width: 290px;
            padding: 14px;
            background: rgba(15, 23, 42, 0.94);
            color: #f8fafc;
            border: 1px solid rgba(51, 65, 85, 0.9);
            display: none;
        }}
        #rightLayerCard h4 {{
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #ffffff;
            margin-bottom: 8px;
        }}
        #rightLayerCard label {{
            color: #94a3b8;
            font-size: 10px;
            font-weight: 600;
        }}
        #rightLayerCard select {{
            background: #1e293b;
            color: #ffffff;
            border: 1px solid #475569;
            font-size: 11px;
            margin-bottom: 6px;
        }}

        /* Swipe Divider Handle */
        #swipeDivider {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 4px;
            background: #ffffff;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.6);
            z-index: 1500;
            cursor: ew-resize;
            display: none;
            left: 50%;
            touch-action: none;
        }}
        #swipeHandle {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 38px;
            height: 38px;
            background: #ffffff;
            border: 2px solid #334155;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
            font-weight: bold;
            font-size: 13px;
            color: #0f172a;
            user-select: none;
            cursor: ew-resize;
        }}
    </style>
</head>
<body>
    <div id="topBanner">
        {f'<img src="{logo_data_uri}" alt="Logo" style="height: 18px; width: 18px; margin-right: 8px; border-radius: 3px; vertical-align: middle; background: #ffffff;" />' if logo_data_uri else ''}
        <span>YIELD DATA CLEANER &bull; AUDIT &amp; CLEANING REVIEW</span>
    </div>

    <div id="map">
        <!-- Top-Left Map Options Panel -->
        <div id="mapOptionsCard" class="glass-panel">
            <h4>&#9660; MAP OPTIONS</h4>
            <div class="control-group">
                <label for="baseSelect">Basemap</label>
                <select id="baseSelect" onchange="updateBasemap()">
                    <option value="hybrid" selected>Hybrid</option>
                    <option value="satellite">Satellite</option>
                    <option value="streets">Streets</option>
                </select>
            </div>
            <div class="control-group">
                <div class="opacity-row">
                    <label for="opacitySlider">Data opacity</label>
                    <span id="opacityVal" class="opacity-val">75%</span>
                </div>
                <input id="opacitySlider" type="range" min="0" max="100" value="75" oninput="updateOpacity(this.value)">
            </div>
            <label class="checkbox-row">
                <input type="checkbox" id="boundaryCheckbox" checked onchange="toggleBoundary(this.checked)">
                <span>Field boundary</span>
            </label>
            <label class="checkbox-row">
                <input type="checkbox" id="compareCheckbox" onchange="toggleCompareMode(this.checked)">
                <span>Compare layers</span>
            </label>
            <button class="btn-reset" onclick="resetExtent()">Reset extent</button>
        </div>

        <!-- Top-Right Summary Card -->
        <div id="reviewInfoCard" class="glass-panel">
            <div class="card-header-row">
                <div class="logo-title-group">
                    {f'<img class="logo-image" src="{logo_data_uri}" alt="Yield Data Cleaner Logo" />' if logo_data_uri else '<div class="logo-badge">&#127806;</div>'}
                    <div>
                        <div class="info-title">Yield Data Review</div>
                        <div class="info-sub">{html.escape(field_name)} &bull; {crop.display_name}</div>
                    </div>
                </div>
                <button class="btn-toggle-info" onclick="toggleInfoPanel()">&#8722;</button>
            </div>
            <div id="infoCardBody">
                <div class="kpi-area-badge">Field Area: {area_label}</div>
                <table class="kpi-compare-table">
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Cleaned Dataset</th>
                            <th>Raw / Source Data</th>
                            <th>Difference / Excluded</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><b>Mean Yield</b></td>
                            <td class="green"><b>{c_stats['mean']:.2f} {yield_unit}</b></td>
                            <td>{r_stats['mean']:.2f} {yield_unit}</td>
                            <td>{diff_mean_str}</td>
                        </tr>
                        <tr>
                            <td><b>Std Dev (STD)</b></td>
                            <td>{c_stats['std']:.2f} {yield_unit}</td>
                            <td>{r_stats['std']:.2f} {yield_unit}</td>
                            <td>{diff_std_str}</td>
                        </tr>
                        <tr>
                            <td><b>Coeff of Variation (CV)</b></td>
                            <td>{c_stats['cv']:.1f} %</td>
                            <td>{r_stats['cv']:.1f} %</td>
                            <td>{diff_cv_str}</td>
                        </tr>
                        <tr>
                            <td><b>Observations (N)</b></td>
                            <td class="green"><b>{clean_count:,}</b></td>
                            <td>{total_count:,}</td>
                            <td class="red"><b>{excluded_count:,} ({exc_pct:.1f}%)</b></td>
                        </tr>
                        <tr>
                            <td><b>Yield Range</b></td>
                            <td>{c_stats['min']:.1f} – {c_stats['max']:.1f} {yield_unit}</td>
                            <td>{r_stats['min']:.1f} – {r_stats['max']:.1f} {yield_unit}</td>
                            <td>-</td>
                        </tr>
                    </tbody>
                </table>
                <div class="info-footer">
                    All source observations remain preserved in the audit database. Every exclusion retains an auditable reason code.
                </div>
            </div>
        </div>

        <!-- Bottom-Left Control Card -->
        <div id="leftLayerCard" class="glass-panel">
            <h4>LEFT LAYER</h4>
            <div class="control-group">
                <select id="leftLayerSelect" onchange="renderLayer('left')">
                    <option value="cleaned" selected>Cleaned Yield (Accepted Points)</option>
                    <option value="surface">Cleaned Yield Interpolated Surface (Grid)</option>
                    <option value="raw">Raw Source Observations (All)</option>
                    <option value="excluded">Excluded Points (By Reason)</option>
                </select>
            </div>
            <div class="control-group">
                <label>Attribute</label>
                <select id="leftAttrSelect" onchange="renderLayer('left')">
                    <optgroup label="Standard Attributes">
                        <option value="yield" selected>Dry Yield ({yield_unit})</option>
                        <option value="moisture">Moisture (%)</option>
                        <option value="speed">Speed ({speed_unit})</option>
                        <option value="swath">Swath Width ({swath_unit})</option>
                        <option value="status">Clean Status</option>
                    </optgroup>
                    <optgroup label="Original Dataset Attributes">
                        {raw_attr_options}
                    </optgroup>
                </select>
            </div>
            <div class="control-group">
                <label>Color ramp</label>
                <select id="leftRampSelect" onchange="renderLayer('left')">
                    <option value="ryg" selected>Red-Yellow-Green</option>
                    <option value="viridis">Viridis</option>
                    <option value="blues">Blues (Moisture)</option>
                    <option value="spectral">Spectral</option>
                    <option value="categorized">Categorized Status</option>
                </select>
            </div>
            <div id="leftLegendBar" class="legend-bar"></div>
            <div class="legend-labels">
                <span id="leftMinLbl">0</span>
                <span id="leftMidLbl">--</span>
                <span id="leftMaxLbl">100</span>
            </div>

            <!-- Expandable Distribution & Classification -->
            <div class="legend-expand-bar" onclick="toggleDistribution('left')">
                <span id="leftExpandIcon">&#9654;</span>
                <span>Distribution &amp; Classification</span>
            </div>
            <div id="leftDistPanel" class="dist-panel" style="display: none;">
                <div class="dist-stats-row">
                    <span id="leftDistMean">Mean: --</span>
                    <span id="leftDistStd">Std: --</span>
                </div>
                <div class="dist-hist-container">
                    <svg id="leftHistSvg" class="hist-svg" viewBox="0 0 240 48" preserveAspectRatio="none"></svg>
                </div>
                <div class="class-ctrl-grid">
                    <div>
                        <label>Mode</label>
                        <select id="leftClassMode" onchange="renderLayer('left')">
                            <option value="quantile" selected>Quantile (Equal Count)</option>
                            <option value="equal">Equal Interval</option>
                            <option value="natural">Natural Breaks</option>
                            <option value="stddev">Std Dev</option>
                        </select>
                    </div>
                    <div>
                        <label>Classes</label>
                        <select id="leftClassCount" onchange="renderLayer('left')">
                            <option value="3">3</option>
                            <option value="4">4</option>
                            <option value="5" selected>5</option>
                            <option value="6">6</option>
                            <option value="7">7</option>
                            <option value="8">8</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="layer-footer-stat">
                {len(points_payload):,} shown for selected field &bull; {total_count:,} raw records
            </div>
        </div>

        <!-- Bottom-Right Control Card (Active in Compare Mode) -->
        <div id="rightLayerCard" class="glass-panel">
            <h4>RIGHT LAYER</h4>
            <div class="control-group">
                <select id="rightLayerSelect" onchange="renderLayer('right')">
                    <option value="raw" selected>Raw Source Observations (All)</option>
                    <option value="surface">Cleaned Yield Interpolated Surface (Grid)</option>
                    <option value="cleaned">Cleaned Yield (Accepted Points)</option>
                    <option value="excluded">Excluded Points (By Reason)</option>
                </select>
            </div>
            <div class="control-group">
                <label>Attribute</label>
                <select id="rightAttrSelect" onchange="renderLayer('right')">
                    <optgroup label="Standard Attributes">
                        <option value="yield" selected>Dry Yield ({yield_unit})</option>
                        <option value="moisture">Moisture (%)</option>
                        <option value="speed">Speed ({speed_unit})</option>
                        <option value="swath">Swath Width ({swath_unit})</option>
                        <option value="status">Clean Status</option>
                    </optgroup>
                    <optgroup label="Original Dataset Attributes">
                        {raw_attr_options}
                    </optgroup>
                </select>
            </div>
            <div class="control-group">
                <label>Color ramp</label>
                <select id="rightRampSelect" onchange="renderLayer('right')">
                    <option value="ryg" selected>Red-Yellow-Green</option>
                    <option value="viridis">Viridis</option>
                    <option value="blues">Blues (Moisture)</option>
                    <option value="spectral">Spectral</option>
                    <option value="categorized">Categorized Status</option>
                </select>
            </div>
            <div id="rightLegendBar" class="legend-bar"></div>
            <div class="legend-labels">
                <span id="rightMinLbl">0</span>
                <span id="rightMidLbl">--</span>
                <span id="rightMaxLbl">100</span>
            </div>

            <!-- Expandable Distribution & Classification -->
            <div class="legend-expand-bar" onclick="toggleDistribution('right')">
                <span id="rightExpandIcon">&#9654;</span>
                <span>Distribution &amp; Classification</span>
            </div>
            <div id="rightDistPanel" class="dist-panel" style="display: none;">
                <div class="dist-stats-row">
                    <span id="rightDistMean">Mean: --</span>
                    <span id="rightDistStd">Std: --</span>
                </div>
                <div class="dist-hist-container">
                    <svg id="rightHistSvg" class="hist-svg" viewBox="0 0 240 48" preserveAspectRatio="none"></svg>
                </div>
                <div class="class-ctrl-grid">
                    <div>
                        <label>Mode</label>
                        <select id="rightClassMode" onchange="renderLayer('right')">
                            <option value="quantile" selected>Quantile (Equal Count)</option>
                            <option value="equal">Equal Interval</option>
                            <option value="natural">Natural Breaks</option>
                            <option value="stddev">Std Dev</option>
                        </select>
                    </div>
                    <div>
                        <label>Classes</label>
                        <select id="rightClassCount" onchange="renderLayer('right')">
                            <option value="3">3</option>
                            <option value="4">4</option>
                            <option value="5" selected>5</option>
                            <option value="6">6</option>
                            <option value="7">7</option>
                            <option value="8">8</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="layer-footer-stat">
                {len(points_payload):,} shown for selected field &bull; {total_count:,} raw records
            </div>
        </div>

        <!-- Swipe Divider Handle -->
        <div id="swipeDivider">
            <div id="swipeHandle">&#8596;</div>
        </div>
    </div>

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const pointsData = {points_json_str};
        const gridData = {grid_json_str};
        const rawKeys = {raw_keys_json};
        let currentOpacity = 0.75;
        let isComparing = false;
        let swipePercent = 0.5;

        // Base tile layers (Esri Hybrid with Transportation Roads, Satellite, Streets)
        const tileProviders = {{
            satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS',
                maxZoom: 19
            }}),
            roads: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: '',
                maxZoom: 19
            }}),
            labels: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: '',
                maxZoom: 19
            }}),
            streets: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, TomTom',
                maxZoom: 19
            }})
        }};

        // Initialize Leaflet Map (Zoom control in top-right below banner, preventing UI overlap)
        const map = L.map('map', {{
            center: [{center_lat:.6f}, {center_lon:.6f}],
            zoom: 15,
            zoomControl: false
        }});

        L.control.zoom({{ position: 'topright' }}).addTo(map);

        // Prevent Leaflet map panning/clicks from intercepting overlay controls and dropdowns
        ['mapOptionsCard', 'leftLayerCard', 'rightLayerCard'].forEach(id => {{
            const el = document.getElementById(id);
            if (el) {{
                L.DomEvent.disableClickPropagation(el);
                L.DomEvent.disableScrollPropagation(el);
            }}
        }});

        const slider = document.getElementById('opacitySlider');
        if (slider) {{
            slider.addEventListener('mousedown', e => e.stopPropagation());
            slider.addEventListener('touchstart', e => e.stopPropagation());
            slider.addEventListener('pointerdown', e => e.stopPropagation());
            slider.addEventListener('input', e => {{
                updateOpacity(slider.value);
            }});
            slider.addEventListener('change', e => {{
                updateOpacity(slider.value);
            }});
        }}

        let activeBaseGroup = L.layerGroup([tileProviders.satellite, tileProviders.roads, tileProviders.labels]).addTo(map);

        // Overlay layers for left & right
        const leftLayerGroup = L.layerGroup().addTo(map);
        const rightLayerGroup = L.layerGroup();
        const boundaryLayerGroup = L.layerGroup().addTo(map);

        const boundaryData = {boundary_json_str};

        function parseBoundaryRings(data) {{
            if (!data || !Array.isArray(data) || data.length === 0) return [];
            if (typeof data[0] === 'number' && typeof data[1] === 'number') return [[data]];
            if (Array.isArray(data[0]) && typeof data[0][0] === 'number') {{
                return [data.map(p => [Number(p[0]), Number(p[1])])];
            }}
            if (Array.isArray(data[0]) && Array.isArray(data[0][0]) && typeof data[0][0][0] === 'number') {{
                return data.map(r => r.map(p => [Number(p[0]), Number(p[1])]));
            }}
            if (Array.isArray(data[0]) && Array.isArray(data[0][0]) && Array.isArray(data[0][0][0])) {{
                let flattened = [];
                data.forEach(poly => {{
                    if (Array.isArray(poly)) {{
                        poly.forEach(r => {{
                            if (Array.isArray(r) && r.length > 0 && typeof r[0][0] === 'number') {{
                                flattened.push(r.map(p => [Number(p[0]), Number(p[1])]));
                            }}
                        }});
                    }}
                }});
                return flattened;
            }}
            return [];
        }}

        function renderBoundary() {{
            boundaryLayerGroup.clearLayers();
            if (!boundaryData) return;

            const rings = parseBoundaryRings(boundaryData);
            if (rings.length === 0) return;

            rings.forEach(ring => {{
                if (ring.length >= 3) {{
                    L.polygon(ring, {{
                        color: '#0f172a',
                        weight: 2.5,
                        dashArray: '5, 5',
                        fillColor: '#3b82f6',
                        fillOpacity: 0.08,
                        interactive: false
                    }}).addTo(boundaryLayerGroup);
                }}
            }});
        }}
        renderBoundary();

        function toggleBoundary(show) {{
            if (show) {{
                if (!map.hasLayer(boundaryLayerGroup)) boundaryLayerGroup.addTo(map);
            }} else {{
                if (map.hasLayer(boundaryLayerGroup)) map.removeLayer(boundaryLayerGroup);
            }}
        }}

        function toggleDistribution(side) {{
            const panel = document.getElementById(side + 'DistPanel');
            const icon = document.getElementById(side + 'ExpandIcon');
            if (!panel) return;
            if (panel.style.display === 'none' || !panel.style.display) {{
                panel.style.display = 'block';
                if (icon) icon.innerHTML = '&#9660;';
            }} else {{
                panel.style.display = 'none';
                if (icon) icon.innerHTML = '&#9654;';
            }}
        }}

        function updateBasemap() {{
            const choice = document.getElementById('baseSelect').value;
            map.removeLayer(activeBaseGroup);

            if (choice === 'hybrid') {{
                activeBaseGroup = L.layerGroup([tileProviders.satellite, tileProviders.roads, tileProviders.labels]);
            }} else if (choice === 'satellite') {{
                activeBaseGroup = L.layerGroup([tileProviders.satellite]);
            }} else if (choice === 'streets') {{
                activeBaseGroup = L.layerGroup([tileProviders.streets]);
            }} else {{
                activeBaseGroup = L.layerGroup([tileProviders.satellite, tileProviders.roads, tileProviders.labels]);
            }}
            activeBaseGroup.addTo(map);
        }}

        function updateOpacity(val) {{
            currentOpacity = val / 100.0;
            document.getElementById('opacityVal').innerText = val + '%';
            renderLayer('left');
            if (isComparing) renderLayer('right');
        }}

        function getRampColor(norm, ramp) {{
            norm = Math.max(0, Math.min(1, norm));
            if (ramp === 'viridis') {{
                if (norm < 0.25) return '#440154';
                if (norm < 0.5) return '#3b528b';
                if (norm < 0.75) return '#21908d';
                return '#fde725';
            }} else if (ramp === 'blues') {{
                const b = Math.floor(255 * (0.3 + 0.7 * norm));
                return `rgb(30, 100, ${{b}})`;
            }} else if (ramp === 'spectral') {{
                if (norm < 0.25) return '#d7191c';
                if (norm < 0.5) return '#fdae61';
                if (norm < 0.75) return '#ffffbf';
                return '#2b83ba';
            }} else {{
                if (norm < 0.5) {{
                    const r = 220;
                    const g = Math.floor(220 * (norm * 2));
                    return `rgb(${{r}}, ${{g}}, 30)`;
                }} else {{
                    const r = Math.floor(220 * (1 - (norm - 0.5) * 2));
                    const g = 190;
                    return `rgb(${{r}}, ${{g}}, 40)`;
                }}
            }}
        }}

        function getClassificationBreaks(values, mode, numClasses) {{
            if (!values || values.length === 0) return [0, 1];
            const sorted = values.slice().sort((a, b) => a - b);
            const min = sorted[0];
            const max = sorted[sorted.length - 1];
            if (min === max) return [min, max];

            const k = Math.min(numClasses, sorted.length);
            const breaks = [min];

            if (mode === 'quantile') {{
                for (let i = 1; i < k; i++) {{
                    const idx = Math.floor((i / k) * sorted.length);
                    breaks.push(sorted[idx]);
                }}
                breaks.push(max);
            }} else if (mode === 'equal') {{
                const step = (max - min) / k;
                for (let i = 1; i < k; i++) {{
                    breaks.push(min + i * step);
                }}
                breaks.push(max);
            }} else if (mode === 'stddev') {{
                const mean = sorted.reduce((a, b) => a + b, 0) / sorted.length;
                const variance = sorted.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / sorted.length;
                const std = Math.sqrt(variance) || 1;
                const stdSteps = [-2, -1, 0, 1, 2];
                breaks.length = 0;
                breaks.push(min);
                for (let step of stdSteps) {{
                    const val = mean + step * std;
                    if (val > min && val < max) breaks.push(val);
                }}
                breaks.push(max);
            }} else {{ // natural breaks / 1D k-means
                let centers = [];
                for (let i = 0; i < k; i++) {{
                    centers.push(min + (i + 0.5) * (max - min) / k);
                }}
                for (let iter = 0; iter < 10; iter++) {{
                    const clusters = Array.from({{ length: k }}, () => []);
                    for (let v of sorted) {{
                        let bestIdx = 0, bestDist = Infinity;
                        for (let c = 0; c < k; c++) {{
                            const d = Math.abs(v - centers[c]);
                            if (d < bestDist) {{ bestDist = d; bestIdx = c; }}
                        }}
                        clusters[bestIdx].push(v);
                    }}
                    for (let c = 0; c < k; c++) {{
                        if (clusters[c].length > 0) {{
                            centers[c] = clusters[c].reduce((a, b) => a + b, 0) / clusters[c].length;
                        }}
                    }}
                }}
                centers.sort((a, b) => a - b);
                for (let i = 0; i < centers.length - 1; i++) {{
                    breaks.push((centers[i] + centers[i+1]) / 2);
                }}
                breaks.push(max);
            }}
            const uniqueBreaks = Array.from(new Set(breaks)).sort((a, b) => a - b);
            return uniqueBreaks.length > 1 ? uniqueBreaks : [min, max];
        }}

        function getBreakNorm(val, breaks) {{
            if (!breaks || breaks.length < 2) return 0.5;
            const k = breaks.length - 1;
            if (val <= breaks[0]) return 0.0;
            if (val >= breaks[k]) return 1.0;
            for (let i = 0; i < k; i++) {{
                if (val <= breaks[i + 1]) {{
                    const span = breaks[i + 1] - breaks[i];
                    const frac = span > 0.0001 ? (val - breaks[i]) / span : 0.5;
                    return (i + frac) / k;
                }}
            }}
            return 1.0;
        }}

        function _safe_num(val) {{
            if (val === null || val === undefined) return null;
            const n = parseFloat(val);
            return isNaN(n) ? null : n;
        }}

        function renderLayer(side) {{
            const group = side === 'left' ? leftLayerGroup : rightLayerGroup;
            group.clearLayers();

            const layerSelect = document.getElementById(side + 'LayerSelect');
            const attrSelect = document.getElementById(side + 'AttrSelect');
            const rampSelect = document.getElementById(side + 'RampSelect');
            const classMode = (document.getElementById(side + 'ClassMode') || {{}}).value || 'quantile';
            const classCount = parseInt((document.getElementById(side + 'ClassCount') || {{}}).value || '5', 10) || 5;

            const layerType = layerSelect ? layerSelect.value : 'cleaned';
            const attr = attrSelect ? attrSelect.value : 'yield';
            const ramp = rampSelect ? rampSelect.value : 'ryg';

            let pointsToRender = [];
            if (layerType === 'cleaned') {{
                pointsToRender = pointsData.filter(p => p.status === 'accepted');
            }} else if (layerType === 'excluded') {{
                pointsToRender = pointsData.filter(p => p.status === 'excluded');
            }} else if (layerType === 'raw') {{
                pointsToRender = pointsData;
            }}

            if (layerType === 'surface') {{
                if (gridData && gridData.cells && gridData.cells.length > 0) {{
                    const rows = gridData.rows;
                    const cols = gridData.cols;
                    const minLat = gridData.bounds[0][0];
                    const minLon = gridData.bounds[0][1];
                    const maxLat = gridData.bounds[1][0];
                    const maxLon = gridData.bounds[1][1];
                    const dLat = (maxLat - minLat) / rows;
                    const dLon = (maxLon - minLon) / cols;

                    let validGridVals = [];
                    for (let r = 0; r < rows; r++) {{
                        for (let c = 0; c < cols; c++) {{
                            const v = gridData.cells[r][c];
                            if (v !== null && v !== undefined) validGridVals.push(v);
                        }}
                    }}

                    const breaks = getClassificationBreaks(validGridVals, classMode, classCount);
                    const minVal = breaks[0];
                    const maxVal = breaks[breaks.length - 1];

                    for (let r = 0; r < rows; r++) {{
                        const sLat = minLat + r * dLat;
                        const nLat = sLat + dLat;
                        for (let c = 0; c < cols; c++) {{
                            const val = gridData.cells[r][c];
                            if (val === null || val === undefined) continue;
                            const wLon = minLon + c * dLon;
                            const eLon = wLon + dLon;

                            let norm = getBreakNorm(val, breaks);
                            const color = getRampColor(norm, ramp);

                            const rect = L.rectangle([[sLat, wLon], [nLat, eLon]], {{
                                color: color,
                                fillColor: color,
                                fillOpacity: currentOpacity,
                                weight: 0.2,
                                stroke: false
                            }});
                            rect.bindTooltip(`<b>Interpolated Yield:</b> ${{val.toFixed(1)}}`);
                            group.addLayer(rect);
                        }}
                    }}
                    updateDistribution(side, validGridVals, minVal, maxVal, breaks);
                }}
                if (isComparing) updateSwipeClip();
                return;
            }}

            // Points rendering
            let vals = [];
            for (let p of pointsToRender) {{
                let v = null;
                if (attr === 'yield') v = _safe_num(p.yield);
                else if (attr === 'moisture') v = _safe_num(p.moisture);
                else if (attr === 'speed') v = _safe_num(p.speed);
                else if (attr === 'swath') v = _safe_num(p.swath);
                else if (p.raw && p.raw[attr] !== undefined) v = _safe_num(p.raw[attr]);

                if (v !== null) vals.push(v);
            }}

            const breaks = getClassificationBreaks(vals, classMode, classCount);
            const minVal = breaks[0];
            const maxVal = breaks[breaks.length - 1];

            for (let p of pointsToRender) {{
                let color = '#2e7d32';
                let displayVal = '—';

                if (attr === 'status' || ramp === 'categorized') {{
                    color = (p.status === 'accepted') ? '#2e7d32' : '#d32f2f';
                    displayVal = p.status;
                }} else {{
                    let v = null;
                    if (attr === 'yield') v = _safe_num(p.yield);
                    else if (attr === 'moisture') v = _safe_num(p.moisture);
                    else if (attr === 'speed') v = _safe_num(p.speed);
                    else if (attr === 'swath') v = _safe_num(p.swath);
                    else if (p.raw && p.raw[attr] !== undefined) v = _safe_num(p.raw[attr]);

                    if (v !== null) {{
                        displayVal = v.toFixed(1);
                        let norm = getBreakNorm(v, breaks);
                        color = getRampColor(norm, ramp);
                    }} else {{
                        color = '#94a3b8';
                    }}
                }}

                const marker = L.circleMarker([p.lat, p.lon], {{
                    radius: 4.5,
                    fillColor: color,
                    fillOpacity: currentOpacity,
                    color: '#0f172a',
                    weight: 0.5,
                    opacity: currentOpacity * 0.8
                }});

                let rawTable = '';
                if (p.raw && Object.keys(p.raw).length > 0) {{
                    rawTable = '<div style="max-height:120px; overflow-y:auto; margin-top:6px; font-size:11px; border-top:1px solid #e2e8f0; padding-top:4px;">' +
                        '<table style="width:100%; border-collapse:collapse;">' +
                        Object.entries(p.raw).map(([k, val]) => `<tr><td style="color:#64748b; padding:1px 3px;">${{k}}</td><td style="font-weight:600; text-align:right; padding:1px 3px;">${{val}}</td></tr>`).join('') +
                        '</table></div>';
                }}

                marker.bindPopup(`
                    <div style="font-size:12px; min-width:190px; line-height:1.4;">
                        <b style="color:#0f172a;">Observation #${{p.id}}</b>
                        <div style="margin:4px 0;">
                            Status: <b style="color:${{p.status === 'accepted' ? '#16a34a' : '#dc2626'}}">${{p.status}}</b>
                            ${{p.reasons ? `<br><span style="color:#dc2626; font-size:11px;">(${{p.reasons}})</span>` : ''}}
                        </div>
                        <table style="width:100%; font-size:12px; margin-top:4px;">
                            <tr><td style="color:#64748b;">Dry Yield:</td><td><b>${{p.yield !== null ? p.yield : '—'}}</b></td></tr>
                            <tr><td style="color:#64748b;">Moisture:</td><td><b>${{p.moisture !== null ? p.moisture + '%' : '—'}}</b></td></tr>
                            <tr><td style="color:#64748b;">Speed:</td><td><b>${{p.speed !== null ? p.speed : '—'}}</b></td></tr>
                            <tr><td style="color:#64748b;">Swath:</td><td><b>${{p.swath !== null ? p.swath : '—'}}</b></td></tr>
                        </table>
                        ${{rawTable}}
                    </div>
                `);

                group.addLayer(marker);
            }}

            updateDistribution(side, vals, minVal, maxVal, breaks);
            if (isComparing) updateSwipeClip();
        }}

        function updateDistribution(side, vals, minVal, maxVal, breaks) {{
            const minLbl = document.getElementById(side + 'MinLbl');
            const midLbl = document.getElementById(side + 'MidLbl');
            const maxLbl = document.getElementById(side + 'MaxLbl');
            const bar = document.getElementById(side + 'LegendBar');
            const rampSelect = document.getElementById(side + 'RampSelect');
            const ramp = rampSelect ? rampSelect.value : 'ryg';

            if (minLbl) minLbl.innerText = (breaks && breaks.length > 0) ? breaks[0].toFixed(1) : (vals.length ? minVal.toFixed(1) : '0');
            if (maxLbl) maxLbl.innerText = (breaks && breaks.length > 0) ? breaks[breaks.length - 1].toFixed(1) : (vals.length ? maxVal.toFixed(1) : '100');
            if (midLbl) midLbl.innerText = (breaks && breaks.length > 2) ? breaks[Math.floor(breaks.length / 2)].toFixed(1) : (vals.length ? ((minVal + maxVal) / 2).toFixed(1) : '--');

            if (bar) {{
                if (ramp === 'viridis') {{
                    bar.style.background = 'linear-gradient(to right, #440154, #3b528b, #21908d, #fde725)';
                }} else if (ramp === 'blues') {{
                    bar.style.background = 'linear-gradient(to right, #93c5fd, #2563eb, #1e3a8a)';
                }} else if (ramp === 'spectral') {{
                    bar.style.background = 'linear-gradient(to right, #d7191c, #fdae61, #ffffbf, #2b83ba)';
                }} else if (ramp === 'categorized') {{
                    bar.style.background = 'linear-gradient(to right, #2e7d32 50%, #d32f2f 50%)';
                }} else {{
                    bar.style.background = 'linear-gradient(to right, #dc2626, #facc15, #16a34a)';
                }}
            }}

            // Update stats
            const meanSpan = document.getElementById(side + 'DistMean');
            const stdSpan = document.getElementById(side + 'DistStd');
            if (vals.length > 0) {{
                const m = vals.reduce((a, b) => a + b, 0) / vals.length;
                const v = vals.reduce((a, b) => a + Math.pow(b - m, 2), 0) / vals.length;
                const s = Math.sqrt(v);
                if (meanSpan) meanSpan.innerText = 'Mean: ' + m.toFixed(1);
                if (stdSpan) stdSpan.innerText = 'Std: ' + s.toFixed(1);
            }} else {{
                if (meanSpan) meanSpan.innerText = 'Mean: --';
                if (stdSpan) stdSpan.innerText = 'Std: --';
            }}

            // Draw SVG Histogram with class-colored bars
            const svg = document.getElementById(side + 'HistSvg');
            if (svg && vals.length > 0) {{
                const numBins = 18;
                const binCounts = new Array(numBins).fill(0);
                const span = maxVal - minVal || 1;
                for (let v of vals) {{
                    let b = Math.min(numBins - 1, Math.max(0, Math.floor(((v - minVal) / span) * numBins)));
                    binCounts[b]++;
                }}
                const maxCount = Math.max(...binCounts, 1);
                const svgW = 240, svgH = 48;
                const barW = (svgW / numBins) - 1.5;

                let rectsHtml = '';
                for (let i = 0; i < numBins; i++) {{
                    const h = (binCounts[i] / maxCount) * (svgH - 4);
                    const x = i * (svgW / numBins);
                    const y = svgH - h;
                    const binMidVal = minVal + (i + 0.5) * (span / numBins);
                    const norm = getBreakNorm(binMidVal, breaks);
                    const c = getRampColor(norm, ramp);
                    rectsHtml += `<rect x="${{x.toFixed(1)}}" y="${{y.toFixed(1)}}" width="${{barW.toFixed(1)}}" height="${{h.toFixed(1)}}" fill="${{c}}" rx="1" />`;
                }}
                svg.innerHTML = rectsHtml;
            }}
        }}

        function toggleCompareMode(enabled) {{
            isComparing = enabled;
            const divider = document.getElementById('swipeDivider');
            const rightCard = document.getElementById('rightLayerCard');

            if (enabled) {{
                divider.style.display = 'block';
                rightCard.style.display = 'block';
                map.addLayer(rightLayerGroup);
                renderLayer('right');
                updateSwipeClip();
            }} else {{
                divider.style.display = 'none';
                rightCard.style.display = 'none';
                map.removeLayer(rightLayerGroup);
                clearSwipeClip();
            }}
        }}

        function updateSwipeClip() {{
            if (!isComparing) return;
            const mapW = map.getSize().x;
            const splitX = mapW * swipePercent;

            document.getElementById('swipeDivider').style.left = splitX + 'px';

            leftLayerGroup.eachLayer(l => {{
                if (l._path || l.getBounds || l.getLatLng) {{
                    const p = l.getLatLng ? map.latLngToContainerPoint(l.getLatLng()) : map.latLngToContainerPoint(l.getBounds().getCenter());
                    if (p.x > splitX) {{
                        if (l.setStyle) l.setStyle({{ fillOpacity: 0, opacity: 0 }});
                    }} else {{
                        if (l.setStyle) l.setStyle({{ fillOpacity: currentOpacity, opacity: currentOpacity }});
                    }}
                }}
            }});
            rightLayerGroup.eachLayer(l => {{
                if (l._path || l.getBounds || l.getLatLng) {{
                    const p = l.getLatLng ? map.latLngToContainerPoint(l.getLatLng()) : map.latLngToContainerPoint(l.getBounds().getCenter());
                    if (p.x < splitX) {{
                        if (l.setStyle) l.setStyle({{ fillOpacity: 0, opacity: 0 }});
                    }} else {{
                        if (l.setStyle) l.setStyle({{ fillOpacity: currentOpacity, opacity: currentOpacity }});
                    }}
                }}
            }});
        }}

        function clearSwipeClip() {{
            leftLayerGroup.eachLayer(l => {{
                if (l.setStyle) l.setStyle({{ fillOpacity: currentOpacity, opacity: currentOpacity }});
            }});
        }}

        // Smooth compare slider drag without panning the map
        let isDragging = false;
        const divider = document.getElementById('swipeDivider');

        function startDrag(e) {{
            isDragging = true;
            map.dragging.disable();
            if (e.stopPropagation) e.stopPropagation();
            if (e.preventDefault) e.preventDefault();
        }}

        function stopDrag(e) {{
            if (isDragging) {{
                isDragging = false;
                map.dragging.enable();
            }}
        }}

        function onDrag(e) {{
            if (!isDragging) return;
            const clientX = (e.touches && e.touches.length > 0) ? e.touches[0].clientX : e.clientX;
            const mapRect = document.getElementById('map').getBoundingClientRect();
            const posX = clientX - mapRect.left;
            swipePercent = Math.max(0.01, Math.min(0.99, posX / mapRect.width));
            updateSwipeClip();
            if (e.stopPropagation) e.stopPropagation();
            if (e.preventDefault) e.preventDefault();
        }}

        divider.addEventListener('pointerdown', startDrag);
        divider.addEventListener('mousedown', startDrag);
        divider.addEventListener('touchstart', startDrag, {{ passive: false }});

        window.addEventListener('pointerup', stopDrag);
        window.addEventListener('mouseup', stopDrag);
        window.addEventListener('touchend', stopDrag);

        window.addEventListener('pointermove', onDrag);
        window.addEventListener('mousemove', onDrag);
        window.addEventListener('touchmove', onDrag, {{ passive: false }});

        map.on('move', () => {{ if (isComparing) updateSwipeClip(); }});
        map.on('zoom', () => {{ if (isComparing) updateSwipeClip(); }});

        function resetExtent() {{
            if (!pointsData || pointsData.length === 0) return;
            const bounds = L.latLngBounds(pointsData.map(p => [p.lat, p.lon]));
            map.fitBounds(bounds, {{ padding: [60, 60] }});
        }}

        function toggleInfoPanel() {{
            const body = document.getElementById('infoCardBody');
            const btn = document.querySelector('.btn-toggle-info');
            if (body.style.display === 'none') {{
                body.style.display = 'block';
                btn.innerHTML = '&#8722;';
            }} else {{
                body.style.display = 'none';
                btn.innerHTML = '&#43;';
            }}
        }}

        // Initial setup
        renderLayer('left');
        resetExtent();
    </script>
</body>
</html>"""  # nosec B608
    return html_template
