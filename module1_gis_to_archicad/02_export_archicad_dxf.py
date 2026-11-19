"""
Lesson 2: Convert Local-Meter GIS Layers into Archicad-Ready DXF Files
(Both Clean 2D Context Plan + 3D Building Massing Model).

Key Concepts for Architecture / BIM:
1. CAD Layer Structure: Architects turn layers on/off constantly (e.g., hide minor roads
   or green hatches on a massing diagram). Every feature class gets its own named layer.
2. Metric Units ($INSUNITS = 6): Ensures Archicad imports 1 drawing unit = 1 meter
   with zero manual scaling errors.
3. 3D Massing (3DFACE): Extruding building footprints to real or estimated heights lets
   Archicad 29 import surrounding urban context as a 3D reference object/morph for sun,
   shadow, and skyline studies.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import ezdxf
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon


# Layer definitions: (Layer Name, AutoCAD ACI Color Index)
# ACI Reference: 1=Red, 2=Yellow, 3=Green, 4=Cyan, 5=Blue, 6=Magenta, 7=White/Black, 8=DarkGray, 9=LightGray
LAYERS = {
    "SITE_BOUNDARY": ("01-SITE-BOUNDARY", 1),
    "ROADS_MAJOR": ("02-ROADS-MAJOR", 7),
    "ROADS_MINOR": ("02-ROADS-MINOR", 8),
    "ROADS_PEDESTRIAN": ("02-ROADS-PEDESTRIAN", 9),
    "BUILDINGS_2D": ("03-BUILDINGS-FOOTPRINT", 4),
    "BUILDINGS_3D": ("03-BUILDINGS-3D-MASSING", 4),
    "BUILDINGS_TXT": ("03-BUILDINGS-HEIGHT-TXT", 2),
    "GREENS": ("04-LANDSCAPE-GREEN", 3),
    "WATER": ("05-WATER", 5),
    "ANNOTATIONS": ("06-ANNOTATIONS", 6),
}

MAJOR_ROAD_TYPES = {"motorway", "trunk", "primary", "secondary", "tertiary", "primary_link", "secondary_link"}
PEDESTRIAN_ROAD_TYPES = {"footway", "path", "pedestrian", "cycleway", "steps"}

DEFAULT_FLOOR_HEIGHT_M = 3.2  # Standard Indian residential/institutional floor-to-floor height
DEFAULT_FALLBACK_HEIGHT_M = 9.0  # ~3 storeys when OSM has no height or level tag


def init_dxf_document() -> ezdxf.document.Drawing:
    """Create an R2010 metric DXF document with architectural layers pre-configured."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # Meters
    doc.header["$MEASUREMENT"] = 1  # Metric
    if "Standard" in doc.styles:
        doc.styles.get("Standard").dxf.font = "Arial.ttf"
    for layer_name, color in LAYERS.values():
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=color)
    return doc


def parse_building_height(height_val: str, levels_val: str) -> tuple[float, bool]:
    """
    Estimate building height in meters from OSM tags.
    Returns (height_meters, is_estimated_fallback).
    """
    if height_val:
        match = re.search(r"(\d+(?:\.\d+)?)", str(height_val))
        if match:
            h = float(match.group(1))
            if 2.0 <= h <= 300.0:
                return h, False

    if levels_val:
        match = re.search(r"(\d+(?:\.\d+)?)", str(levels_val))
        if match:
            levels = float(match.group(1))
            if 0.5 <= levels <= 100.0:
                return round(levels * DEFAULT_FLOOR_HEIGHT_M, 2), False

    return DEFAULT_FALLBACK_HEIGHT_M, True


def add_polygon_2d(msp, geom, layer_name: str) -> int:
    """Write Polygon or MultiPolygon exterior and interior rings as closed 2D LWPOLYLINEs."""
    count = 0
    polys = [geom] if isinstance(geom, Polygon) else (list(geom.geoms) if isinstance(geom, MultiPolygon) else [])
    for poly in polys:
        ext_coords = list(poly.exterior.coords)
        if len(ext_coords) >= 4:
            pts = [(float(x), float(y)) for x, y in ext_coords[:-1]]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer_name})
            count += 1
        for interior in poly.interiors:
            int_coords = list(interior.coords)
            if len(int_coords) >= 4:
                pts = [(float(x), float(y)) for x, y in int_coords[:-1]]
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer_name})
    return count


def add_line_2d(msp, geom, layer_name: str) -> int:
    """Write LineString or MultiLineString as 2D LWPOLYLINEs."""
    count = 0
    lines = [geom] if isinstance(geom, LineString) else (list(geom.geoms) if isinstance(geom, MultiLineString) else [])
    for line in lines:
        coords = [(float(x), float(y)) for x, y in line.coords]
        if len(coords) >= 2:
            msp.add_lwpolyline(coords, close=False, dxfattribs={"layer": layer_name})
            count += 1
    return count


def add_extruded_building_3d(msp, geom, height_m: float, layer_name: str) -> int:
    """
    Extrude a building footprint polygon from Z=0 to Z=height_m using 3DFACE entities.
    Walls are vertical quads; the roof is triangulated via fan/earcut-safe quads or triangles.
    """
    faces_added = 0
    polys = [geom] if isinstance(geom, Polygon) else (list(geom.geoms) if isinstance(geom, MultiPolygon) else [])

    for poly in polys:
        # Simplify tiny collinear noise (< 0.15m) so the 3D mesh stays lightweight in Archicad
        clean_poly = poly.simplify(0.15, preserve_topology=True)
        if clean_poly.is_empty or not isinstance(clean_poly, Polygon):
            continue

        coords = list(clean_poly.exterior.coords)
        if len(coords) < 4:
            continue

        ring = [(float(x), float(y)) for x, y in coords[:-1]]
        n = len(ring)

        # 1. Vertical wall faces around perimeter
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            msp.add_3dface(
                [(x1, y1, 0.0), (x2, y2, 0.0), (x2, y2, height_m), (x1, y1, height_m)],
                dxfattribs={"layer": layer_name},
            )
            faces_added += 1

        # 2. Roof cap (simple ear-safe cap for convex/near-convex footprints + centroid fan)
        cx, cy = clean_poly.representative_point().x, clean_poly.representative_point().y
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            msp.add_3dface(
                [(x1, y1, height_m), (x2, y2, height_m), (cx, cy, height_m), (cx, cy, height_m)],
                dxfattribs={"layer": layer_name},
            )
            faces_added += 1

    return faces_added


def add_site_annotations(msp, meta: dict) -> None:
    """Draw site boundary circle, (0,0) Project Origin crosshair, North arrow, and Survey Point note."""
    radius = float(meta["radius_m"])
    b_layer = LAYERS["SITE_BOUNDARY"][0]
    a_layer = LAYERS["ANNOTATIONS"][0]

    # Boundary circle and center crosshair
    msp.add_circle((0.0, 0.0), radius=radius, dxfattribs={"layer": b_layer})
    msp.add_line((-15.0, 0.0), (15.0, 0.0), dxfattribs={"layer": b_layer})
    msp.add_line((0.0, -15.0), (0.0, 15.0), dxfattribs={"layer": b_layer})

    # Scale bar (100m total: two 50m segments) just below the circle
    sy = -radius - 25.0
    msp.add_lwpolyline([(-50.0, sy), (50.0, sy)], dxfattribs={"layer": a_layer})
    for tick_x, label in [(-50.0, "0 m"), (0.0, "50 m"), (50.0, "100 m")]:
        msp.add_line((tick_x, sy - 4.0), (tick_x, sy + 4.0), dxfattribs={"layer": a_layer})
        msp.add_text(label, dxfattribs={"layer": a_layer, "height": 5.0}).set_placement((tick_x - 6.0, sy - 12.0))

    # North arrow on the right
    nx, ny = radius + 30.0, 0.0
    msp.add_line((nx, ny - 20.0), (nx, ny + 25.0), dxfattribs={"layer": a_layer})
    msp.add_lwpolyline([(nx - 7.0, ny + 12.0), (nx, ny + 25.0), (nx + 7.0, ny + 12.0)], dxfattribs={"layer": a_layer})
    msp.add_text("N", dxfattribs={"layer": a_layer, "height": 10.0}).set_placement((nx - 3.5, ny + 30.0))

    # Metadata block for Archicad Survey Point setup
    info_lines = [
        f"SITE: {meta['site_name']}",
        f"WGS84: {meta['latitude']:.5f} N, {meta['longitude']:.5f} E",
        f"CRS: EPSG:{meta['utm_epsg']} (METERS)",
        f"ORIGIN (0,0) = UTM E {meta['utm_origin_easting_m']} m, N {meta['utm_origin_northing_m']} m",
        "UNITS: 1 DXF UNIT = 1.0 METER",
    ]
    ty = -radius - 50.0
    for idx, line in enumerate(info_lines):
        msp.add_text(line, dxfattribs={"layer": a_layer, "height": 4.5}).set_placement((-radius, ty - idx * 8.0))


def classify_road_layer(highway_val: str) -> str:
    hw = str(highway_val).lower().strip()
    if hw in MAJOR_ROAD_TYPES:
        return LAYERS["ROADS_MAJOR"][0]
    if hw in PEDESTRIAN_ROAD_TYPES:
        return LAYERS["ROADS_PEDESTRIAN"][0]
    return LAYERS["ROADS_MINOR"][0]


def export_archicad_dxfs(data_dir: Path) -> None:
    meta = json.loads((data_dir / "origin.json").read_text(encoding="utf-8"))
    roads = gpd.read_file(data_dir / "roads.geojson")
    buildings = gpd.read_file(data_dir / "buildings.geojson")
    greens = gpd.read_file(data_dir / "greens.geojson")
    water = gpd.read_file(data_dir / "water.geojson")

    # --- 1. 2D Context Plan DXF ---
    doc_2d = init_dxf_document()
    msp_2d = doc_2d.modelspace()
    add_site_annotations(msp_2d, meta)

    for _, row in roads.iterrows():
        layer = classify_road_layer(row.get("highway", ""))
        add_line_2d(msp_2d, row.geometry, layer)

    for _, row in greens.iterrows():
        add_polygon_2d(msp_2d, row.geometry, LAYERS["GREENS"][0])

    for _, row in water.iterrows():
        if row.geometry.geom_type in ("Polygon", "MultiPolygon"):
            add_polygon_2d(msp_2d, row.geometry, LAYERS["WATER"][0])
        else:
            add_line_2d(msp_2d, row.geometry, LAYERS["WATER"][0])

    known_height_count = 0
    for _, row in buildings.iterrows():
        add_polygon_2d(msp_2d, row.geometry, LAYERS["BUILDINGS_2D"][0])
        h_m, is_est = parse_building_height(row.get("height", ""), row.get("building:levels", ""))
        if not is_est:
            known_height_count += 1
            pt = row.geometry.representative_point()
            msp_2d.add_text(
                f"{h_m:.1f}m",
                dxfattribs={"layer": LAYERS["BUILDINGS_TXT"][0], "height": 2.2},
            ).set_placement((pt.x, pt.y))

    out_2d = data_dir / "site_context_2d.dxf"
    doc_2d.saveas(out_2d)

    # --- 2. 3D Urban Context Massing DXF ---
    doc_3d = init_dxf_document()
    msp_3d = doc_3d.modelspace()
    add_site_annotations(msp_3d, meta)

    for _, row in roads.iterrows():
        layer = classify_road_layer(row.get("highway", ""))
        add_line_2d(msp_3d, row.geometry, layer)

    total_faces = 0
    for _, row in buildings.iterrows():
        h_m, _ = parse_building_height(row.get("height", ""), row.get("building:levels", ""))
        total_faces += add_extruded_building_3d(msp_3d, row.geometry, h_m, LAYERS["BUILDINGS_3D"][0])

    out_3d = data_dir / "site_context_3d_massing.dxf"
    doc_3d.saveas(out_3d)

    print(f"Exported 2D Plan DXF:    {out_2d}")
    print(f"Exported 3D Massing DXF: {out_3d} ({total_faces} 3D faces)")
    print(f"Buildings with explicit OSM height/levels: {known_height_count} / {len(buildings)}")
    print(f"(Remaining buildings extruded to fallback {DEFAULT_FALLBACK_HEIGHT_M} m)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export local-meter GeoJSON layers to Archicad DXF.")
    parser.add_argument("--data-dir", type=Path, default=Path("output"), help="Directory containing GeoJSON + origin.json")
    args = parser.parse_args()
    export_archicad_dxfs(args.data_dir)


if __name__ == "__main__":
    main()
