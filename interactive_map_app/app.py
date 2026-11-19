"""
INTERACTIVE ARCHITECTURAL SITE SELECTOR & ARCHICAD GENERATOR
==============================================================
A simple, interactive local web application for architects:
  1. Pick or draw any plot boundary on a live OpenStreetMap or Satellite map.
  2. Adjust municipal setback distance and proposed floor count.
  3. Real-time calculation of Ground Coverage %, FSI / FAR, and buildable envelope.
  4. 1-Click download of Archicad 29-ready 2D DXF, 3D Massing DXF, and Survey Point JSON.

How to Run:
  .venv\\Scripts\\python.exe interactive_map_app\\app.py
  (Then open http://localhost:8050 in your browser!)
"""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
import ezdxf
import ifcopenshell
import ifcopenshell.api
from pyproj import CRS, Transformer
from shapely.geometry import LineString, Polygon
from shapely.affinity import translate


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "index.html"
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8050

# In-memory session cache for downloads: token -> metadata dict
CACHE: dict[str, dict] = {}


def get_utm_epsg(lat: float, lon: float) -> tuple[int, int]:
    """Calculate UTM EPSG and zone number for any point on Earth."""
    zone = int((lon + 180.0) // 6.0) + 1
    base = 32600 if lat >= 0 else 32700
    return base + zone, zone


def configure_dxf_document(doc: ezdxf.document.Drawing) -> None:
    """Configure DXF document for Archicad with TrueType fonts (no missing txt.SHX dialog)."""
    doc.header["$INSUNITS"] = 6      # 6 = Meters
    doc.header["$MEASUREMENT"] = 1   # Metric

    # Remap default text style from legacy AutoCAD txt.shx to Windows Arial TrueType font
    if "Standard" in doc.styles:
        doc.styles.get("Standard").dxf.font = "Arial.ttf"


def fetch_real_roads(
    center_lat: float,
    center_lon: float,
    radius_m: int,
    to_utm: Transformer,
    to_wgs84: Transformer,
    origin_x: float,
    origin_y: float
) -> list[dict]:
    """Fetch ONLY real road/street centerlines from OpenStreetMap Overpass API.

    Buildings are NOT fetched from OSM because community-contributed building
    outlines in Indian cities are frequently inaccurate, outdated, or completely
    missing. Users trace neighbor rooftops manually on the satellite imagery
    for guaranteed accuracy.

    Roads in OSM India are well-maintained and highly accurate.
    """
    roads_out: list[dict] = []

    # Multiple Overpass mirrors for redundancy -- try each in order
    mirrors = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    # Query ONLY highways/roads -- no buildings
    query = f"""
    [out:json][timeout:20];
    (
      way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|service|unclassified|living_street|pedestrian|footway|cycleway|track|path)$"](around:{radius_m},{center_lat},{center_lon});
    );
    out body;
    >;
    out skel qt;
    """

    data = None
    last_error = ""
    for endpoint in mirrors:
        try:
            resp = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": "ArchSiteAnalyzer/2.0 (Academic Research)"},
                timeout=25
            )
            if resp.status_code == 200:
                parsed = resp.json()
                if parsed and "elements" in parsed and len(parsed["elements"]) > 0:
                    data = parsed
                    break
                else:
                    last_error = f"{endpoint}: returned 0 elements"
            else:
                last_error = f"{endpoint}: HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            last_error = f"{endpoint}: timed out"
            continue
        except Exception as e:
            last_error = f"{endpoint}: {e}"
            continue

    if not data:
        print(f"[ROADS] All Overpass mirrors failed. Last: {last_error}")
        return roads_out

    elements = data["elements"]
    node_map = {e["id"]: (e["lat"], e["lon"]) for e in elements if e["type"] == "node"}
    ways = [e for e in elements if e["type"] == "way"]

    for w in ways:
        tags = w.get("tags", {})
        way_nodes = w.get("nodes", [])
        if "highway" not in tags:
            continue

        latlngs = [node_map[nid] for nid in way_nodes if nid in node_map]
        if len(latlngs) < 2:
            continue

        local_coords = []
        for lat, lon in latlngs:
            ux, uy = to_utm.transform(lon, lat)
            local_coords.append((ux - origin_x, uy - origin_y))

        # Use the actual OSM name, never invent one
        rname = tags.get("name", "")
        rtype = tags.get("highway", "road")

        roads_out.append({
            "name": rname,
            "type": rtype,
            "local_pts": local_coords,
            "latlngs": latlngs
        })

    print(f"[ROADS] Fetched {len(roads_out)} real road segments from OpenStreetMap")
    return roads_out


def generate_dxf_2d(
    plot_local: Polygon,
    buildable_local: Polygon,
    meta: dict,
    out_path: Path,
    context_buildings: list[dict] | None = None,
    context_roads: list[dict] | None = None
) -> None:
    """Generate clean, publication-ready metric 2D Site Plan DXF for Archicad 29."""
    doc = ezdxf.new("R2010")
    configure_dxf_document(doc)

    # Studio Layers:
    # Color 1 = Red (Plot Boundary)
    # Color 5 = Deep Navy Blue (Municipal Setback / Buildable Envelope)
    # Color 7 = Black on White (Clean architectural text & dimensions)
    # Color 8 = Gray (Surrounding roads and neighboring buildings)
    doc.layers.add("01-SITE-PLOT-BOUNDARY", color=1)
    doc.layers.add("02-BUILDABLE-FOOTPRINT", color=5)
    doc.layers.add("03-ANNOTATIONS-TEXT", color=7)
    doc.layers.add("04-CONTEXT-ROADS", color=8)
    doc.layers.add("05-CONTEXT-BUILDINGS-2D", color=8)

    msp = doc.modelspace()

    # 1. Surrounding Context (Roads and Neighbor Buildings)
    if context_roads:
        for r in context_roads:
            pts = [(float(x), float(y)) for x, y in r.get("local_pts", [])]
            if len(pts) >= 2:
                msp.add_lwpolyline(pts, close=False, dxfattribs={"layer": "04-CONTEXT-ROADS"})

    if context_buildings:
        for b in context_buildings:
            poly = b.get("local_poly")
            if poly and not poly.is_empty:
                b_coords = [(float(x), float(y)) for x, y in poly.exterior.coords[:-1]]
                if len(b_coords) >= 3:
                    msp.add_lwpolyline(b_coords, close=True, dxfattribs={"layer": "05-CONTEXT-BUILDINGS-2D"})
                    cp = poly.representative_point()
                    msp.add_text(
                        f"+{b['height_m']:.1f}m",
                        dxfattribs={"layer": "03-ANNOTATIONS-TEXT", "height": 0.9}
                    ).set_placement((cp.x - 3.0, cp.y))

    # 2. Plot boundary polygon
    px_coords = [(float(x), float(y)) for x, y in plot_local.exterior.coords[:-1]]
    msp.add_lwpolyline(px_coords, close=True, dxfattribs={"layer": "01-SITE-PLOT-BOUNDARY"})

    # 3. Buildable setback envelope
    if not buildable_local.is_empty:
        bx_coords = [(float(x), float(y)) for x, y in buildable_local.exterior.coords[:-1]]
        msp.add_lwpolyline(bx_coords, close=True, dxfattribs={"layer": "02-BUILDABLE-FOOTPRINT"})

    # 4. North Arrow & Scale Bar (positioned neatly to the side)
    minx, miny, maxx, maxy = plot_local.bounds
    nx, ny = maxx + 12.0, maxy
    msp.add_line((nx, ny - 8.0), (nx, ny + 8.0), dxfattribs={"layer": "03-ANNOTATIONS-TEXT"})
    msp.add_lwpolyline([(nx - 2.5, ny + 3.0), (nx, ny + 8.0), (nx + 2.5, ny + 3.0)], dxfattribs={"layer": "03-ANNOTATIONS-TEXT"})
    msp.add_text("N", dxfattribs={"layer": "03-ANNOTATIONS-TEXT", "height": 3.0}).set_placement((nx - 1.2, ny + 10.0))

    # Scale bar (20m total)
    sy = miny - 10.0
    msp.add_lwpolyline([(minx, sy), (minx + 20.0, sy)], dxfattribs={"layer": "03-ANNOTATIONS-TEXT"})
    msp.add_line((minx, sy - 1.5), (minx, sy + 1.5), dxfattribs={"layer": "03-ANNOTATIONS-TEXT"})
    msp.add_line((minx + 10.0, sy - 1.5), (minx + 10.0, sy + 1.5), dxfattribs={"layer": "03-ANNOTATIONS-TEXT"})
    msp.add_line((minx + 20.0, sy - 1.5), (minx + 20.0, sy + 1.5), dxfattribs={"layer": "03-ANNOTATIONS-TEXT"})
    msp.add_text("0m", dxfattribs={"layer": "03-ANNOTATIONS-TEXT", "height": 1.2}).set_placement((minx - 1.0, sy - 4.0))
    msp.add_text("10m", dxfattribs={"layer": "03-ANNOTATIONS-TEXT", "height": 1.2}).set_placement((minx + 8.5, sy - 4.0))
    msp.add_text("20m", dxfattribs={"layer": "03-ANNOTATIONS-TEXT", "height": 1.2}).set_placement((minx + 18.5, sy - 4.0))

    # Clean title block with neat border box
    box_w = 48.0
    box_h = 28.0
    bx1 = minx
    by1 = sy - 8.0 - box_h
    bx2 = bx1 + box_w
    by2 = by1 + box_h
    msp.add_lwpolyline([(bx1, by1), (bx2, by1), (bx2, by2), (bx1, by2)], close=True, dxfattribs={"layer": "03-ANNOTATIONS-TEXT"})

    b_count = len(context_buildings) if context_buildings else 0
    r_count = len(context_roads) if context_roads else 0

    info_lines = [
        f"PROJECT: {meta['name']}",
        f"PLOT AREA: {meta['plot_area_sqm']:.1f} m2 ({meta['plot_area_sqft']:.0f} sq.ft)",
        f"SETBACK: {meta['setback_m']} m (Area Lost: {meta['setback_loss_sqm']:.1f} m2)",
        f"BUILDABLE FOOTPRINT: {meta['buildable_sqm']:.1f} m2",
        f"GROUND COVERAGE: {meta['coverage_pct']:.1f}%",
        f"PROPOSED FLOORS: {meta['floors']} | FSI: {meta['fsi']:.2f}",
        f"NEIGHBOR BUILDINGS (USER-MAPPED): {b_count}",
        f"SURROUNDING ROADS (OSM): {r_count}",
        f"SURVEY POINT: EPSG:{meta['utm_epsg']} E={meta['utm_origin_x']:.1f}m, N={meta['utm_origin_y']:.1f}m",
    ]
    for idx, line in enumerate(info_lines):
        msp.add_text(line, dxfattribs={"layer": "03-ANNOTATIONS-TEXT", "height": 1.2}).set_placement((bx1 + 1.5, by2 - 3.0 - idx * 2.8))

    doc.saveas(out_path)


def generate_dxf_3d(
    plot_local: Polygon,
    buildable_local: Polygon,
    total_height_m: float,
    meta: dict,
    out_path: Path,
    context_buildings: list[dict] | None = None,
    context_roads: list[dict] | None = None
) -> None:
    """Generate 3D Extruded Building Massing DXF with surrounding urban context using 3DFACE for Archicad 29."""
    doc = ezdxf.new("R2010")
    configure_dxf_document(doc)

    doc.layers.add("01-SITE-PLOT-BOUNDARY", color=1)      # Red
    doc.layers.add("02-PROPOSED-BUILDING-3D", color=4)    # Cyan
    doc.layers.add("03-CONTEXT-BUILDINGS-3D", color=8)    # Gray
    doc.layers.add("04-CONTEXT-ROADS", color=8)           # Gray

    msp = doc.modelspace()

    # 1. Surrounding Roads at Z=0
    if context_roads:
        for r in context_roads:
            pts = [(float(x), float(y)) for x, y in r.get("local_pts", [])]
            if len(pts) >= 2:
                msp.add_lwpolyline(pts, close=False, dxfattribs={"layer": "04-CONTEXT-ROADS"})

    # 2. Extrude Surrounding Neighbor Buildings in 3D
    if context_buildings:
        for b in context_buildings:
            poly = b.get("local_poly")
            bh = float(b.get("height_m", 9.6))
            if poly and not poly.is_empty:
                poly_clean = poly.simplify(0.1, preserve_topology=True)
                ring = [(float(x), float(y)) for x, y in poly_clean.exterior.coords[:-1]]
                n = len(ring)
                if n >= 3:
                    # Vertical walls
                    for i in range(n):
                        x1, y1 = ring[i]
                        x2, y2 = ring[(i + 1) % n]
                        msp.add_3dface(
                            [(x1, y1, 0.0), (x2, y2, 0.0), (x2, y2, bh), (x1, y1, bh)],
                            dxfattribs={"layer": "03-CONTEXT-BUILDINGS-3D"},
                        )
                    # Roof cap
                    cx, cy = poly_clean.representative_point().x, poly_clean.representative_point().y
                    for i in range(n):
                        x1, y1 = ring[i]
                        x2, y2 = ring[(i + 1) % n]
                        msp.add_3dface(
                            [(x1, y1, bh), (x2, y2, bh), (cx, cy, bh), (cx, cy, bh)],
                            dxfattribs={"layer": "03-CONTEXT-BUILDINGS-3D"},
                        )

    # 3. Ground boundary
    px_coords = [(float(x), float(y)) for x, y in plot_local.exterior.coords[:-1]]
    msp.add_lwpolyline(px_coords, close=True, dxfattribs={"layer": "01-SITE-PLOT-BOUNDARY"})

    # 4. Extrude Proposed Building Massing
    if not buildable_local.is_empty:
        poly = buildable_local.simplify(0.1, preserve_topology=True)
        ring = [(float(x), float(y)) for x, y in poly.exterior.coords[:-1]]
        n = len(ring)

        # Vertical walls
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            msp.add_3dface(
                [(x1, y1, 0.0), (x2, y2, 0.0), (x2, y2, total_height_m), (x1, y1, total_height_m)],
                dxfattribs={"layer": "02-PROPOSED-BUILDING-3D"},
            )

        # Roof cap (centroid fan)
        cx, cy = poly.representative_point().x, poly.representative_point().y
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            msp.add_3dface(
                [(x1, y1, total_height_m), (x2, y2, total_height_m), (cx, cy, total_height_m), (cx, cy, total_height_m)],
                dxfattribs={"layer": "02-PROPOSED-BUILDING-3D"},
            )

    doc.saveas(out_path)


def generate_ifc(
    plot_local: Polygon,
    buildable_local: Polygon,
    total_height_m: float,
    meta: dict,
    out_path: Path,
    context_buildings: list[dict] | None = None
) -> None:
    """Generate a native 3D Open BIM IFC model with surrounding neighborhood context for Archicad 29."""
    model = ifcopenshell.file(schema="IFC4")

    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name=meta["name"])
    ifcopenshell.api.run("unit.assign_unit", model, length={"is_metric": True, "raw": "METERS"})

    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body_ctx = ifcopenshell.api.run(
        "context.add_context", model,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=context
    )

    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Site_Plot")
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])

    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Proposed_Building")
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])

    # 1. Extrude Proposed Building
    if not buildable_local.is_empty:
        poly = buildable_local.simplify(0.05, preserve_topology=True)
        coords = [(float(x), float(y)) for x, y in poly.exterior.coords]
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        element = ifcopenshell.api.run(
            "root.create_entity", model,
            ifc_class="IfcBuildingElementProxy",
            name=f"Proposed_Design_{meta['floors']}_Storeys"
        )
        ifcopenshell.api.run("spatial.assign_container", model, relating_structure=building, products=[element])

        pts = [model.create_entity("IfcCartesianPoint", Coordinates=[x, y]) for x, y in coords]
        polyline = model.create_entity("IfcPolyline", Points=pts)
        profile = model.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=polyline)

        placement = model.create_entity(
            "IfcAxis2Placement3D",
            Location=model.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0]),
            Axis=model.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0]),
            RefDirection=model.create_entity("IfcDirection", DirectionRatios=[1.0, 0.0, 0.0])
        )
        solid = model.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=profile,
            Position=placement,
            ExtrudedDirection=model.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0]),
            Depth=float(total_height_m)
        )
        shape_rep = model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=body_ctx,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[solid]
        )
        element.Representation = model.create_entity("IfcProductDefinitionShape", Representations=[shape_rep])

    # 2. Add Surrounding Neighbor Buildings as Context BIM Elements
    if context_buildings:
        for idx, b in enumerate(context_buildings):
            b_poly = b.get("local_poly")
            bh = float(b.get("height_m", 9.6))
            if b_poly and not b_poly.is_empty:
                b_clean = b_poly.simplify(0.1, preserve_topology=True)
                b_coords = [(float(x), float(y)) for x, y in b_clean.exterior.coords]
                if b_coords[0] != b_coords[-1]:
                    b_coords.append(b_coords[0])

                if len(b_coords) >= 4:
                    c_elem = ifcopenshell.api.run(
                        "root.create_entity", model,
                        ifc_class="IfcBuildingElementProxy",
                        name=f"Context_{b['name']}_{b['levels']}Fl"
                    )
                    ifcopenshell.api.run("spatial.assign_container", model, relating_structure=building, products=[c_elem])

                    c_pts = [model.create_entity("IfcCartesianPoint", Coordinates=[x, y]) for x, y in b_coords]
                    c_pline = model.create_entity("IfcPolyline", Points=c_pts)
                    c_prof = model.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=c_pline)

                    c_place = model.create_entity(
                        "IfcAxis2Placement3D",
                        Location=model.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0]),
                        Axis=model.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0]),
                        RefDirection=model.create_entity("IfcDirection", DirectionRatios=[1.0, 0.0, 0.0])
                    )
                    c_solid = model.create_entity(
                        "IfcExtrudedAreaSolid",
                        SweptArea=c_prof,
                        Position=c_place,
                        ExtrudedDirection=model.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0]),
                        Depth=bh
                    )
                    c_rep = model.create_entity(
                        "IfcShapeRepresentation",
                        ContextOfItems=body_ctx,
                        RepresentationIdentifier="Body",
                        RepresentationType="SweptSolid",
                        Items=[c_solid]
                    )
                    c_elem.Representation = model.create_entity("IfcProductDefinitionShape", Representations=[c_rep])

    model.write(str(out_path))


class AppRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            content = TEMPLATE_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if path == "/api/download":
            qs = urllib.parse.parse_qs(parsed.query)
            token = qs.get("token", [None])[0]
            dl_type = qs.get("type", [None])[0]

            if not token or token not in CACHE:
                self.send_error(404, "Invalid or expired download token.")
                return

            meta = CACHE[token]
            token_dir = EXPORT_DIR / token

            if dl_type == "2d":
                file_path = token_dir / f"{meta['name']}_2D_Plan.dxf"
                mime = "application/dxf"
            elif dl_type == "3d":
                file_path = token_dir / f"{meta['name']}_3D_Massing.dxf"
                mime = "application/dxf"
            elif dl_type == "ifc":
                file_path = token_dir / f"{meta['name']}_Native_BIM.ifc"
                mime = "application/x-step"
            elif dl_type == "origin":
                file_path = token_dir / "origin.json"
                mime = "application/json"
            else:
                self.send_error(400, "Unknown download type.")
                return

            if not file_path.exists():
                self.send_error(404, "File not found.")
                return

            file_bytes = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
            self.send_header("Content-Length", str(len(file_bytes)))
            self.end_headers()
            self.wfile.write(file_bytes)
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        if self.path == "/api/analyze":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception as e:
                self.send_error(400, f"Malformed JSON: {e}")
                return

            coords_latlng = data.get("coordinates", [])
            if len(coords_latlng) < 3:
                self.send_error(400, "At least 3 coordinates are required.")
                return

            setback_m = float(data.get("setback_m", 3.0))
            floors = int(data.get("floors", 3))
            floor_height_m = float(data.get("floor_height_m", 3.2))
            name = str(data.get("name", "Plot_Project")).strip().replace(" ", "_") or "Plot_Project"

            # 1. Coordinate Projections (WGS84 -> UTM)
            # Input format: [[lat, lon], [lat, lon], ...]
            lats = [pt[0] for pt in coords_latlng]
            lons = [pt[1] for pt in coords_latlng]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)

            utm_epsg, utm_zone = get_utm_epsg(center_lat, center_lon)
            to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True)
            to_wgs84 = Transformer.from_crs(f"EPSG:{utm_epsg}", "EPSG:4326", always_xy=True)

            # Project site center to UTM -> This becomes the Archicad Survey Point!
            origin_x, origin_y = to_utm.transform(center_lon, center_lat)

            # Convert all polygon vertices to local meters centered at (0, 0)
            local_pts = []
            for lat, lon in coords_latlng:
                ux, uy = to_utm.transform(lon, lat)
                local_pts.append((ux - origin_x, uy - origin_y))

            plot_local = Polygon(local_pts)
            if not plot_local.is_valid:
                plot_local = plot_local.buffer(0)

            # 2. Geometric Calculations with Shapely
            plot_area_sqm = float(plot_local.area)
            plot_area_sqft = plot_area_sqm * 10.7639
            perimeter_m = float(plot_local.length)

            # Inward buffer for municipal setback
            buildable_local = plot_local.buffer(-setback_m)
            buildable_sqm = float(buildable_local.area) if not buildable_local.is_empty else 0.0
            setback_loss_sqm = max(0.0, plot_area_sqm - buildable_sqm)
            coverage_pct = (buildable_sqm / plot_area_sqm) * 100.0 if plot_area_sqm > 0 else 0.0

            total_height_m = floors * floor_height_m
            total_builtup_sqm = buildable_sqm * floors
            fsi = total_builtup_sqm / plot_area_sqm if plot_area_sqm > 0 else 0.0

            # Convert setback polygon vertices back to GPS Lat/Lon for Leaflet display
            setback_latlngs = []
            if not buildable_local.is_empty:
                poly_clean = buildable_local.simplify(0.05, preserve_topology=True)
                for lx, ly in poly_clean.exterior.coords[:-1]:
                    # Unshift back to UTM, then to WGS84
                    lon_restored, lat_restored = to_wgs84.transform(lx + origin_x, ly + origin_y)
                    setback_latlngs.append([lat_restored, lon_restored])

            # 3. Neighborhood Context
            # BUILDINGS: Only from user-traced rooftop polygons.
            # OSM building data in Indian cities is unreliable -- never auto-fetch it.
            user_neighbors_input = data.get("user_neighbors", [])
            context_buildings = []
            for idx, un in enumerate(user_neighbors_input):
                un_coords = un.get("coordinates", [])
                if len(un_coords) >= 3:
                    un_lv = int(un.get("floors", 3))
                    un_h = float(un.get("height_m", un_lv * 3.2))
                    un_name = str(un.get("name", f"Neighbor_Block_{idx + 1}")).strip() or f"Neighbor_Block_{idx + 1}"
                    un_local_pts = []
                    for lat, lon in un_coords:
                        ux, uy = to_utm.transform(lon, lat)
                        un_local_pts.append((ux - origin_x, uy - origin_y))
                    try:
                        poly = Polygon(un_local_pts)
                        if poly.is_valid and poly.area > 5.0:
                            context_buildings.append({
                                "id": un.get("id", f"un_{idx}"),
                                "name": un_name,
                                "height_m": un_h,
                                "levels": un_lv,
                                "local_poly": poly,
                                "latlngs": un_coords,
                                "is_user_traced": True
                            })
                    except Exception:
                        pass

            # ROADS: From OpenStreetMap (roads are well-maintained and accurate in India)
            include_roads = bool(data.get("include_context", False))
            context_radius = int(data.get("context_radius_m", 150))
            if include_roads:
                context_roads = fetch_real_roads(
                    center_lat, center_lon, context_radius, to_utm, to_wgs84, origin_x, origin_y
                )
            else:
                context_roads = []

            # 4. Generate Deliverable Files (2D DXF, 3D DXF, IFC, origin.json)
            token = secrets.token_hex(8)
            token_dir = EXPORT_DIR / token
            token_dir.mkdir(parents=True, exist_ok=True)

            meta = {
                "name": name,
                "token": token,
                "plot_area_sqm": plot_area_sqm,
                "plot_area_sqft": plot_area_sqft,
                "perimeter_m": perimeter_m,
                "setback_m": setback_m,
                "setback_loss_sqm": setback_loss_sqm,
                "buildable_sqm": buildable_sqm,
                "coverage_pct": coverage_pct,
                "floors": floors,
                "floor_height_m": floor_height_m,
                "total_height_m": total_height_m,
                "total_builtup_sqm": total_builtup_sqm,
                "fsi": fsi,
                "utm_epsg": utm_epsg,
                "utm_zone": utm_zone,
                "utm_origin_x": origin_x,
                "utm_origin_y": origin_y,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "context_buildings_count": len(context_buildings),
                "context_roads_count": len(context_roads),
            }
            CACHE[token] = meta

            # Write files
            dxf_2d_path = token_dir / f"{name}_2D_Plan.dxf"
            dxf_3d_path = token_dir / f"{name}_3D_Massing.dxf"
            ifc_path = token_dir / f"{name}_Native_BIM.ifc"
            origin_json_path = token_dir / "origin.json"

            generate_dxf_2d(plot_local, buildable_local, meta, dxf_2d_path, context_buildings, context_roads)
            generate_dxf_3d(plot_local, buildable_local, total_height_m, meta, dxf_3d_path, context_buildings, context_roads)
            generate_ifc(plot_local, buildable_local, total_height_m, meta, ifc_path, context_buildings)
            origin_json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

            # JSON response with serialized context geometry for Leaflet map display
            serializable_buildings = [{
                "name": b["name"],
                "height_m": b["height_m"],
                "levels": b["levels"],
                "latlngs": b["latlngs"]
            } for b in context_buildings]

            serializable_roads = [{
                "name": r["name"],
                "type": r["type"],
                "latlngs": r["latlngs"]
            } for r in context_roads]

            resp_payload = {
                **meta,
                "setback_latlngs": setback_latlngs,
                "context_buildings": serializable_buildings,
                "context_roads": serializable_roads,
            }
            resp_bytes = json.dumps(resp_payload).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        self.send_error(404, "Not Found")


def run_server(port: int = PORT) -> None:
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, AppRequestHandler)
    url = f"http://localhost:{port}"
    print("=" * 65)
    print(" ARCHITECTURAL SITE SELECTOR & BIM ANALYZER APP")
    print("=" * 65)
    print(f"Server is running at: {url}")
    print("Opening web interface in your default browser...")
    print("Press Ctrl+C in this terminal to stop the server.")
    print("=" * 65)
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()
        print("Server stopped cleanly.")


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(port_arg)
